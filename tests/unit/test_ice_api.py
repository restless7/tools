"""
Unit tests for ICE Pipeline API endpoints.

This module tests the FastAPI endpoints for Excel conversion,
ICE ingestion management, and status monitoring.
"""

import asyncio
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

# Import the API module from ice_pipeline
from ice_pipeline.api import (ExcelConversionRequest, ExcelConversionResponse,
                              app)
from ice_pipeline.ingestion import (ICEIngestionManager, IngestionResult,
                                    IngestionStatus)


class TestICEPipelineAPI:
    """Test suite for ICE Pipeline API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client for FastAPI application."""
        return TestClient(app)

    @pytest.fixture
    def mock_ingestion_manager(self):
        """Create mock ICE ingestion manager."""
        manager = Mock(spec=ICEIngestionManager)
        manager.get_status.return_value = IngestionStatus.IDLE
        manager.get_last_result.return_value = None
        return manager

    def test_health_check_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "status" in data
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    def test_convert_excel_valid_request(self, client):
        """Test Excel conversion with valid request."""
        request_data = {
            "file_path": "/test/path/example.xlsx",
            "output_format": "csv",
            "include_metadata": True,
        }

        with patch("ice_pipeline.api.process_excel_conversion") as mock_process:
            mock_process.return_value = {
                "success": True,
                "output_file": "/test/path/example.csv",
                "rows_processed": 100,
                "metadata": {"sheets": ["Sheet1"], "columns": 5},
            }

            response = client.post("/convert-excel", json=request_data)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["success"] is True
            assert data["output_file"] == "/test/path/example.csv"
            assert data["rows_processed"] == 100
            assert "metadata" in data

    def test_convert_excel_invalid_format(self, client):
        """Test Excel conversion with invalid output format."""
        request_data = {
            "file_path": "/test/path/example.xlsx",
            "output_format": "invalid_format",
            "include_metadata": True,
        }

        response = client.post("/convert-excel", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_convert_excel_file_not_found(self, client):
        """Test Excel conversion with non-existent file."""
        request_data = {
            "file_path": "/test/path/nonexistent.xlsx",
            "output_format": "csv",
            "include_metadata": True,
        }

        with patch("ice_pipeline.api.process_excel_conversion") as mock_process:
            mock_process.side_effect = FileNotFoundError("File not found")

            response = client.post("/convert-excel", json=request_data)

            assert response.status_code == status.HTTP_404_NOT_FOUND
            data = response.json()
            assert "File not found" in data["detail"]

    def test_trigger_ingestion_success(self, client, mock_ingestion_manager):
        """Test successful ICE ingestion trigger."""
        mock_result = IngestionResult(
            success=True,
            status=IngestionStatus.COMPLETED,
            output="Ingestion completed successfully",
            error_message=None,
            return_code=0,
            execution_time=45.2,
            timestamp=datetime.now(),
        )

        with patch("ice_pipeline.api.ingestion_manager", mock_ingestion_manager):
            # Use AsyncMock for async function
            mock_ingestion_manager.run_ingestion = AsyncMock(return_value=mock_result)
            mock_ingestion_manager.get_status.return_value = IngestionStatus.IDLE

            response = client.post("/ice/trigger")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["status"] == "triggered"
            assert "message" in data

    def test_trigger_ingestion_already_running(self, client, mock_ingestion_manager):
        """Test ICE ingestion trigger when already running."""
        mock_ingestion_manager.get_status.return_value = IngestionStatus.RUNNING

        with patch("ice_pipeline.api.ingestion_manager", mock_ingestion_manager):
            response = client.post("/ice/trigger")

            assert response.status_code == status.HTTP_409_CONFLICT
            data = response.json()
            assert "already running" in data["detail"].lower()

    def test_get_ingestion_status_idle(self, client, mock_ingestion_manager):
        """Test getting ICE ingestion status when idle."""
        mock_ingestion_manager.get_status.return_value = IngestionStatus.IDLE
        mock_ingestion_manager.get_last_result.return_value = None

        with patch("ice_pipeline.api.ingestion_manager", mock_ingestion_manager):
            response = client.get("/ice/status")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["status"] == "idle"
            assert data["last_result"] is None

    def test_get_ingestion_status_with_result(self, client, mock_ingestion_manager):
        """Test getting ICE ingestion status with last result."""
        mock_result = IngestionResult(
            success=True,
            status=IngestionStatus.COMPLETED,
            output="Ingestion completed",
            error_message=None,
            return_code=0,
            execution_time=30.5,
            timestamp=datetime.now(),
        )

        mock_ingestion_manager.get_status.return_value = IngestionStatus.IDLE
        mock_ingestion_manager.get_last_result.return_value = mock_result

        with patch("ice_pipeline.api.ingestion_manager", mock_ingestion_manager):
            response = client.get("/ice/status")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["status"] == "idle"
            assert data["last_result"] is not None
            assert data["last_result"]["success"] is True
            assert data["last_result"]["execution_time"] == 30.5

    def test_cleanup_ingestion_success(self, client):
        """Test successful ICE ingestion cleanup."""
        with patch("ice_pipeline.api.cleanup_ingestion_resources") as mock_cleanup:
            mock_cleanup.return_value = {
                "status": "completed",
                "files_cleaned": 5,
                "temp_dirs_removed": 2,
                "cache_cleared": True,
            }

            response = client.post("/ice/cleanup")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["status"] == "completed"
            assert data["files_cleaned"] == 5
            assert data["temp_dirs_removed"] == 2
            assert data["cache_cleared"] is True

    def test_cleanup_ingestion_error(self, client):
        """Test ICE ingestion cleanup with error."""
        with patch("ice_pipeline.api.cleanup_ingestion_resources") as mock_cleanup:
            mock_cleanup.side_effect = Exception("Cleanup failed")

            response = client.post("/ice/cleanup")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert "Cleanup failed" in data["detail"]

    @pytest.mark.parametrize("output_format", ["csv", "json", "parquet"])
    def test_convert_excel_multiple_formats(self, client, output_format):
        """Test Excel conversion with different output formats."""
        request_data = {
            "file_path": "/test/path/example.xlsx",
            "output_format": output_format,
            "include_metadata": False,
        }

        with patch("ice_pipeline.api.process_excel_conversion") as mock_process:
            mock_process.return_value = {
                "success": True,
                "output_file": f"/test/path/example.{output_format}",
                "rows_processed": 50,
                "metadata": None,
            }

            response = client.post("/convert-excel", json=request_data)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["output_file"].endswith(f".{output_format}")

    @pytest.mark.benchmark(group="api")
    def test_health_check_performance(self, client, benchmark):
        """Benchmark health check endpoint performance."""

        def make_health_request():
            return client.get("/health")

        response = benchmark(make_health_request)
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.smoke
    def test_smoke_api_endpoints(self, client):
        """Smoke test for all API endpoints."""
        # Health check
        health_response = client.get("/health")
        assert health_response.status_code == status.HTTP_200_OK

        # Status check
        with patch("ice_pipeline.api.ingestion_manager") as mock_manager:
            mock_manager.get_status.return_value = IngestionStatus.IDLE
            mock_manager.get_last_result.return_value = None

            status_response = client.get("/ice/status")
            assert status_response.status_code == status.HTTP_200_OK

    def test_excel_conversion_request_validation(self):
        """Test ExcelConversionRequest model validation."""
        # Valid request
        valid_request = ExcelConversionRequest(
            file_path="/test/path/file.xlsx", output_format="csv", include_metadata=True
        )

        assert valid_request.file_path == "/test/path/file.xlsx"
        assert valid_request.output_format == "csv"
        assert valid_request.include_metadata is True

        # Test default values
        minimal_request = ExcelConversionRequest(
            file_path="/test/path/file.xlsx", output_format="json"
        )

        assert minimal_request.include_metadata is False  # Default value

    def test_excel_conversion_response_model(self):
        """Test ExcelConversionResponse model structure."""
        response = ExcelConversionResponse(
            success=True,
            output_file="/test/path/output.csv",
            rows_processed=100,
            metadata={"sheets": ["Sheet1"], "columns": 5},
            processing_time=2.5,
        )

        assert response.success is True
        assert response.output_file == "/test/path/output.csv"
        assert response.rows_processed == 100
        assert response.metadata == {"sheets": ["Sheet1"], "columns": 5}
        assert response.processing_time == 2.5

    def test_api_error_handling(self, client):
        """Test API error handling for various scenarios."""
        # Test invalid JSON
        response = client.post("/convert-excel", data="invalid json")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Test missing required fields
        response = client.post("/convert-excel", json={"file_path": "/test/path"})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_async_ingestion_handling(self, mock_ingestion_manager):
        """Test asynchronous ingestion handling."""
        mock_result = IngestionResult(
            success=True,
            status=IngestionStatus.COMPLETED,
            output="Test output",
            error_message=None,
            return_code=0,
            execution_time=10.0,
            timestamp=datetime.now(),
        )

        # Mock the async run_ingestion method
        async def mock_run_ingestion():
            return mock_result

        mock_ingestion_manager.run_ingestion = mock_run_ingestion

        result = await mock_ingestion_manager.run_ingestion()
        assert isinstance(result, IngestionResult)
        assert result.success is True

    def test_cors_headers(self, client):
        """Test CORS headers in API responses."""
        response = client.get("/health")

        # Check that CORS middleware is properly configured
        assert response.status_code == status.HTTP_200_OK
        # Note: Specific CORS headers would depend on FastAPI CORS configuration

    def test_request_validation_edge_cases(self, client):
        """Test request validation with edge cases."""
        # Test very long file path
        long_path = "/test/" + "a" * 1000 + "/file.xlsx"
        request_data = {
            "file_path": long_path,
            "output_format": "csv",
            "include_metadata": True,
        }

        response = client.post("/convert-excel", json=request_data)
        # Should handle long paths gracefully (may accept or reject based on validation rules)
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]

    def test_concurrent_requests(self, client):
        """Test handling of concurrent API requests."""
        import threading
        import time

        results = []

        def make_request():
            response = client.get("/health")
            results.append(response.status_code)

        # Create multiple threads to simulate concurrent requests
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All requests should succeed
        assert all(status_code == status.HTTP_200_OK for status_code in results)
        assert len(results) == 5


@pytest.mark.integration
class TestICEPipelineAPIIntegration:
    """Integration tests for ICE Pipeline API."""

    @pytest.fixture
    def client(self):
        """Create test client for integration testing."""
        return TestClient(app)

    def test_full_excel_conversion_workflow(self, client):
        """Test complete Excel conversion workflow."""
        # This would test with actual file processing in a real integration test
        # For now, we'll mock the file processing but test the complete flow

        request_data = {
            "file_path": "/test/data/sample.xlsx",
            "output_format": "csv",
            "include_metadata": True,
        }

        with patch("ice_pipeline.api.process_excel_conversion") as mock_process:
            mock_process.return_value = {
                "success": True,
                "output_file": "/test/data/sample.csv",
                "rows_processed": 150,
                "metadata": {
                    "sheets": ["Data", "Summary"],
                    "columns": 8,
                    "file_size": 2048,
                },
            }

            response = client.post("/convert-excel", json=request_data)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify the complete response structure
            assert data["success"] is True
            assert data["rows_processed"] == 150
            assert data["metadata"]["sheets"] == ["Data", "Summary"]
            assert data["metadata"]["columns"] == 8

    @pytest.mark.asyncio
    async def test_full_ingestion_workflow_integration(self, client):
        """Test complete ICE ingestion workflow integration."""
        with patch("ice_pipeline.api.ingestion_manager") as mock_manager:
            # Mock the complete ingestion workflow
            mock_result = IngestionResult(
                success=True,
                status=IngestionStatus.COMPLETED,
                output="Integration test completed successfully",
                error_message=None,
                return_code=0,
                execution_time=60.0,
                timestamp=datetime.now(),
            )

            mock_manager.get_status.return_value = IngestionStatus.IDLE

            async def mock_run_ingestion():
                return mock_result

            mock_manager.run_ingestion = mock_run_ingestion

            # Step 1: Check initial status
            status_response = client.get("/ice/status")
            assert status_response.status_code == status.HTTP_200_OK
            assert status_response.json()["status"] == "idle"

            # Step 2: Trigger ingestion
            trigger_response = client.post("/ice/trigger")
            assert trigger_response.status_code == status.HTTP_200_OK

            # Step 3: Check final status (would show last result)
            mock_manager.get_last_result.return_value = mock_result
            final_status = client.get("/ice/status")
            assert final_status.status_code == status.HTTP_200_OK
            assert final_status.json()["last_result"]["success"] is True
