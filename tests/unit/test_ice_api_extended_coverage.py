"""
Extended unit tests for ICE Pipeline API to improve code coverage.

Targets uncovered lines in ice_pipeline/api.py:
- process_excel_conversion() helper (lines 246-285)
- run_ingestion_background() helper (lines 290-295)
- cleanup_ingestion_resources() helper (lines 304-350)
- ValueError path in convert_excel endpoint (line 157)
- ExcelConversionResponse.validate_output_file validator (line 105)
"""

import asyncio
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pandas as pd
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from ice_pipeline.api import (
    ExcelConversionResponse,
    app,
    cleanup_ingestion_resources,
    process_excel_conversion,
    run_ingestion_background,
)
from ice_pipeline.ingestion import ICEIngestionManager, IngestionResult, IngestionStatus


@pytest.fixture
def client():
    """Create test client for FastAPI application."""
    return TestClient(app)


@pytest.fixture
def sample_excel_file():
    """Create a temporary Excel file for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test_data.xlsx"
        df = pd.DataFrame(
            {
                "name": ["Alice", "Bob", "Charlie"],
                "age": [30, 25, 35],
                "score": [95.5, 87.3, 92.1],
            }
        )
        df.to_excel(file_path, index=False)
        yield str(file_path)


# ─────────────────────────────────────────────────────────────────────────────
# Tests for process_excel_conversion() helper function
# ─────────────────────────────────────────────────────────────────────────────


class TestProcessExcelConversion:
    """Tests for the process_excel_conversion helper function."""

    def test_convert_to_csv(self, sample_excel_file):
        """Test actual CSV conversion with a real Excel file."""
        result = process_excel_conversion(
            file_path=sample_excel_file,
            output_format="csv",
            include_metadata=False,
        )

        assert result["success"] is True
        assert result["rows_processed"] == 3
        assert result["output_file"].endswith(".csv")
        assert result["metadata"] is None
        assert result["processing_time"] >= 0

        # Verify output file was created
        assert Path(result["output_file"]).exists()

    def test_convert_to_json(self, sample_excel_file):
        """Test actual JSON conversion with a real Excel file."""
        result = process_excel_conversion(
            file_path=sample_excel_file,
            output_format="json",
            include_metadata=False,
        )

        assert result["success"] is True
        assert result["rows_processed"] == 3
        assert result["output_file"].endswith(".json")

    @pytest.mark.skipif(
        not any(
            __import__("importlib").util.find_spec(pkg) is not None
            for pkg in ["pyarrow", "fastparquet"]
        ),
        reason="pyarrow or fastparquet required for parquet support",
    )
    def test_convert_to_parquet(self, sample_excel_file):
        """Test actual Parquet conversion with a real Excel file."""
        result = process_excel_conversion(
            file_path=sample_excel_file,
            output_format="parquet",
            include_metadata=False,
        )

        assert result["success"] is True
        assert result["rows_processed"] == 3
        assert result["output_file"].endswith(".parquet")

    def test_convert_with_metadata(self, sample_excel_file):
        """Test conversion with metadata collection enabled."""
        result = process_excel_conversion(
            file_path=sample_excel_file,
            output_format="csv",
            include_metadata=True,
        )

        assert result["success"] is True
        assert result["metadata"] is not None
        assert "columns" in result["metadata"]
        assert result["metadata"]["columns"] == 3
        assert "file_size" in result["metadata"]

    def test_file_not_found_raises(self):
        """Test that FileNotFoundError is raised for missing files."""
        with pytest.raises(FileNotFoundError, match="File not found"):
            process_excel_conversion(
                file_path="/nonexistent/path/file.xlsx",
                output_format="csv",
                include_metadata=False,
            )

    def test_invalid_output_format_raises(self, sample_excel_file):
        """Test that ValueError is raised for invalid output format."""
        with pytest.raises(ValueError, match="Invalid output format"):
            process_excel_conversion(
                file_path=sample_excel_file,
                output_format="xml",
                include_metadata=False,
            )

    def test_excel_processing_exception_propagates(self, sample_excel_file):
        """Test that exceptions during pandas processing are re-raised."""
        with patch("pandas.read_excel", side_effect=Exception("Corrupt file")):
            with pytest.raises(Exception, match="Excel processing failed"):
                process_excel_conversion(
                    file_path=sample_excel_file,
                    output_format="csv",
                    include_metadata=False,
                )


# ─────────────────────────────────────────────────────────────────────────────
# Tests for cleanup_ingestion_resources() helper function
# ─────────────────────────────────────────────────────────────────────────────


class TestCleanupIngestionResources:
    """Tests for the cleanup_ingestion_resources helper function."""

    def test_cleanup_with_no_temp_files(self):
        """Test cleanup when no ICE temp files exist."""
        result = cleanup_ingestion_resources()

        assert result["status"] == "completed"
        assert result["files_cleaned"] >= 0
        assert result["temp_dirs_removed"] >= 0
        assert result["cache_cleared"] is True

    def test_cleanup_removes_temp_files(self):
        """Test that cleanup removes ice_* temp files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fake ice_ temp files
            ice_file = Path(tmpdir) / "ice_test_file.tmp"
            ice_file.write_text("test content")

            with patch("tempfile.gettempdir", return_value=tmpdir):
                result = cleanup_ingestion_resources()

            assert result["status"] == "completed"
            assert result["files_cleaned"] >= 1
            assert not ice_file.exists()

    def test_cleanup_removes_temp_dirs(self):
        """Test that cleanup removes ice_* temp directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fake ice_ temp directory
            ice_dir = Path(tmpdir) / "ice_temp_dir"
            ice_dir.mkdir()
            (ice_dir / "some_file.txt").write_text("content")

            with patch("tempfile.gettempdir", return_value=tmpdir):
                result = cleanup_ingestion_resources()

            assert result["status"] == "completed"
            assert result["temp_dirs_removed"] >= 1
            assert not ice_dir.exists()

    def test_cleanup_handles_permission_error(self):
        """Test that cleanup handles permission errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ice_file = Path(tmpdir) / "ice_locked_file.tmp"
            ice_file.write_text("locked")

            with patch("tempfile.gettempdir", return_value=tmpdir):
                with patch.object(
                    Path, "unlink", side_effect=PermissionError("Locked")
                ):
                    result = cleanup_ingestion_resources()

            # Should complete with warnings, not raise
            assert result["status"] == "completed"
            assert result["warnings"] is not None
            assert len(result["warnings"]) > 0

    def test_cleanup_returns_space_freed(self):
        """Test that cleanup reports space freed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ice_file = Path(tmpdir) / "ice_big_file.tmp"
            ice_file.write_bytes(b"x" * 1024)  # 1 KB

            with patch("tempfile.gettempdir", return_value=tmpdir):
                result = cleanup_ingestion_resources()

            assert "space_freed_mb" in result
            assert result["space_freed_mb"] >= 0

    def test_cleanup_outer_exception_propagates(self):
        """Test that outer exceptions in cleanup are re-raised."""
        with patch("tempfile.gettempdir", side_effect=Exception("System error")):
            with pytest.raises(Exception, match="Cleanup operation failed"):
                cleanup_ingestion_resources()


# ─────────────────────────────────────────────────────────────────────────────
# Tests for run_ingestion_background() async helper
# ─────────────────────────────────────────────────────────────────────────────


class TestRunIngestionBackground:
    """Tests for the run_ingestion_background async helper."""

    @pytest.mark.asyncio
    async def test_background_ingestion_success(self):
        """Test successful background ingestion run."""
        mock_result = IngestionResult(
            success=True,
            status=IngestionStatus.COMPLETED,
            output="Done",
            error_message=None,
            return_code=0,
            execution_time=5.0,
            timestamp=datetime.now(),
        )

        mock_manager = AsyncMock()
        mock_manager.run_ingestion = AsyncMock(return_value=mock_result)

        with patch("ice_pipeline.api.ingestion_manager", mock_manager):
            # Should not raise
            await run_ingestion_background()
            mock_manager.run_ingestion.assert_called_once()

    @pytest.mark.asyncio
    async def test_background_ingestion_exception_is_caught(self):
        """Test that exceptions in background ingestion are caught and logged."""
        mock_manager = AsyncMock()
        mock_manager.run_ingestion = AsyncMock(
            side_effect=Exception("Ingestion crashed")
        )

        with patch("ice_pipeline.api.ingestion_manager", mock_manager):
            # Should NOT raise — exceptions must be caught internally
            await run_ingestion_background()

    @pytest.mark.asyncio
    async def test_background_ingestion_skipped_when_no_manager(self):
        """Test that background ingestion is skipped when manager is None."""
        with patch("ice_pipeline.api.ingestion_manager", None):
            # Should complete without error
            await run_ingestion_background()


# ─────────────────────────────────────────────────────────────────────────────
# Tests for endpoint ValueError path and model validators
# ─────────────────────────────────────────────────────────────────────────────


class TestAPIEndpointEdgeCases:
    """Tests for edge cases in API endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_convert_excel_raises_value_error(self, client):
        """Test that ValueError from process_excel_conversion returns 422."""
        request_data = {
            "file_path": "/test/path/example.xlsx",
            "output_format": "csv",
            "include_metadata": False,
        }

        with patch(
            "ice_pipeline.api.process_excel_conversion",
            side_effect=ValueError("Invalid data in file"),
        ):
            response = client.post("/convert-excel", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Invalid data in file" in response.json()["detail"]

    def test_convert_excel_raises_generic_exception(self, client):
        """Test that generic exceptions from process_excel_conversion return 500."""
        request_data = {
            "file_path": "/test/path/example.xlsx",
            "output_format": "csv",
            "include_metadata": False,
        }

        with patch(
            "ice_pipeline.api.process_excel_conversion",
            side_effect=RuntimeError("Unexpected failure"),
        ):
            response = client.post("/convert-excel", json=request_data)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Processing failed" in response.json()["detail"]

    def test_excel_response_output_file_validator_rejects_empty(self):
        """Test that ExcelConversionResponse rejects empty output_file."""
        with pytest.raises(Exception):
            ExcelConversionResponse(
                success=True,
                output_file="",
                rows_processed=0,
            )

    def test_excel_response_output_file_validator_strips_whitespace(self):
        """Test that ExcelConversionResponse strips whitespace from output_file."""
        response = ExcelConversionResponse(
            success=True,
            output_file="  /path/to/file.csv  ",
            rows_processed=5,
        )
        assert response.output_file == "/path/to/file.csv"

    def test_trigger_ingestion_unavailable_manager(self, client):
        """Test trigger endpoint when ingestion manager is None."""
        with patch("ice_pipeline.api.ingestion_manager", None):
            response = client.post("/ice/trigger")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "not available" in response.json()["detail"]

    def test_get_status_unavailable_manager(self, client):
        """Test status endpoint when ingestion manager is None."""
        with patch("ice_pipeline.api.ingestion_manager", None):
            response = client.get("/ice/status")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_cleanup_with_warnings_in_response(self, client):
        """Test cleanup endpoint returns warnings when present."""
        with patch("ice_pipeline.api.cleanup_ingestion_resources") as mock_cleanup:
            mock_cleanup.return_value = {
                "status": "completed",
                "files_cleaned": 1,
                "temp_dirs_removed": 0,
                "cache_cleared": True,
                "space_freed_mb": 0,
                "warnings": ["Could not remove /tmp/ice_locked: Permission denied"],
            }

            response = client.post("/ice/cleanup")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["warnings"] is not None
        assert len(data["warnings"]) == 1
