"""
Unit tests for ICE Ingestion Manager.

This module tests the core functionality of the ICE ingestion system,
including environment validation, script execution, and error handling.
"""

import asyncio
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ice_pipeline.ingestion import ICEIngestionManager, IngestionResult, IngestionStatus


class TestICEIngestionManager:
    """Test suite for ICE Ingestion Manager."""

    @pytest.fixture
    def ingestion_manager(self):
        """Create ICE ingestion manager for testing."""
        with patch("ice_pipeline.ingestion.os.getenv") as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                "GOOGLE_CREDENTIALS_JSON": '{"type": "service_account"}',
                "GOOGLE_DRIVE_FOLDER_ID": "test_folder_id",
                "ICE_SCRIPT_PATH": "/test/path/script.py",
                "LOG_LEVEL": "INFO",
            }.get(key, default)

            return ICEIngestionManager()

    def test_initialization(self, ingestion_manager):
        """Test ICE ingestion manager initialization."""
        assert ingestion_manager is not None
        assert hasattr(ingestion_manager, "status")
        assert ingestion_manager.status == IngestionStatus.IDLE

    def test_environment_validation_success(self, ingestion_manager):
        """Test successful environment validation."""
        with patch("ice_pipeline.ingestion.os.getenv") as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                "GOOGLE_CREDENTIALS_JSON": '{"type": "service_account"}',
                "GOOGLE_DRIVE_FOLDER_ID": "test_folder_id",
                "ICE_SCRIPT_PATH": "/test/path/script.py",
            }.get(key, default)

            with patch("ice_pipeline.ingestion.Path.exists", return_value=True):
                result = ingestion_manager.validate_environment()
                assert result is True

    def test_environment_validation_missing_credentials(self, ingestion_manager):
        """Test environment validation with missing Google credentials."""
        with patch("ice_pipeline.ingestion.os.getenv") as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                "GOOGLE_DRIVE_FOLDER_ID": "test_folder_id",
                "ICE_SCRIPT_PATH": "/test/path/script.py",
            }.get(key, default)

            result = ingestion_manager.validate_environment()
            assert result is False

    def test_environment_validation_missing_folder_id(self, ingestion_manager):
        """Test environment validation with missing Google Drive folder ID."""
        with patch("ice_pipeline.ingestion.os.getenv") as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                "GOOGLE_CREDENTIALS_JSON": '{"type": "service_account"}',
                "ICE_SCRIPT_PATH": "/test/path/script.py",
            }.get(key, default)

            result = ingestion_manager.validate_environment()
            assert result is False

    def test_environment_validation_script_not_found(self, ingestion_manager):
        """Test environment validation with missing ICE script."""
        with patch("ice_pipeline.ingestion.os.getenv") as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                "GOOGLE_CREDENTIALS_JSON": '{"type": "service_account"}',
                "GOOGLE_DRIVE_FOLDER_ID": "test_folder_id",
                "ICE_SCRIPT_PATH": "/test/path/script.py",
            }.get(key, default)

            with patch("ice_pipeline.ingestion.Path.exists", return_value=False):
                result = ingestion_manager.validate_environment()
                assert result is False

    @pytest.mark.asyncio
    async def test_run_ingestion_success(self, ingestion_manager):
        """Test successful ingestion run."""
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"Success output", b"")

        with patch(
            "ice_pipeline.ingestion.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            with patch.object(
                ingestion_manager, "validate_environment", return_value=True
            ):
                result = await ingestion_manager.run_ingestion()

                assert isinstance(result, IngestionResult)
                assert result.success is True
                assert result.status == IngestionStatus.COMPLETED
                assert "Success output" in result.output

    @pytest.mark.asyncio
    async def test_run_ingestion_validation_failure(self, ingestion_manager):
        """Test ingestion run with environment validation failure."""
        with patch.object(
            ingestion_manager, "validate_environment", return_value=False
        ):
            result = await ingestion_manager.run_ingestion()

            assert isinstance(result, IngestionResult)
            assert result.success is False
            assert result.status == IngestionStatus.ERROR
            assert "Environment validation failed" in result.error_message

    @pytest.mark.asyncio
    async def test_run_ingestion_script_failure(self, ingestion_manager):
        """Test ingestion run with script execution failure."""
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"Error occurred", b"Script failed")

        with patch(
            "ice_pipeline.ingestion.asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            with patch.object(
                ingestion_manager, "validate_environment", return_value=True
            ):
                result = await ingestion_manager.run_ingestion()

                assert isinstance(result, IngestionResult)
                assert result.success is False
                assert result.status == IngestionStatus.ERROR
                assert result.return_code == 1

    @pytest.mark.asyncio
    async def test_run_ingestion_exception_handling(self, ingestion_manager):
        """Test ingestion run with exception handling."""
        with patch(
            "ice_pipeline.ingestion.asyncio.create_subprocess_exec",
            side_effect=Exception("Process creation failed"),
        ):
            with patch.object(
                ingestion_manager, "validate_environment", return_value=True
            ):
                result = await ingestion_manager.run_ingestion()

                assert isinstance(result, IngestionResult)
                assert result.success is False
                assert result.status == IngestionStatus.ERROR
                assert "Process creation failed" in result.error_message

    def test_get_status(self, ingestion_manager):
        """Test status getter."""
        assert ingestion_manager.get_status() == IngestionStatus.IDLE

        # Test status change
        ingestion_manager.status = IngestionStatus.RUNNING
        assert ingestion_manager.get_status() == IngestionStatus.RUNNING

    def test_get_last_result(self, ingestion_manager):
        """Test last result getter."""
        # Initially should be None
        assert ingestion_manager.get_last_result() is None

        # Set a result
        mock_result = IngestionResult(
            success=True,
            status=IngestionStatus.COMPLETED,
            output="Test output",
            error_message=None,
            return_code=0,
            execution_time=1.5,
            timestamp=datetime.now(),
        )

        ingestion_manager._last_result = mock_result
        assert ingestion_manager.get_last_result() == mock_result

    @pytest.mark.benchmark(group="ingestion")
    def test_environment_validation_performance(self, ingestion_manager, benchmark):
        """Benchmark environment validation performance."""
        with patch("ice_pipeline.ingestion.os.getenv") as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                "GOOGLE_CREDENTIALS_JSON": '{"type": "service_account"}',
                "GOOGLE_DRIVE_FOLDER_ID": "test_folder_id",
                "ICE_SCRIPT_PATH": "/test/path/script.py",
            }.get(key, default)

            with patch("ice_pipeline.ingestion.Path.exists", return_value=True):
                result = benchmark(ingestion_manager.validate_environment)
                assert result is True

    @pytest.mark.smoke
    def test_smoke_ingestion_manager_creation(self):
        """Smoke test for ICE ingestion manager creation."""
        with patch("ice_pipeline.ingestion.os.getenv") as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                "GOOGLE_CREDENTIALS_JSON": '{"type": "service_account"}',
                "GOOGLE_DRIVE_FOLDER_ID": "test_folder_id",
                "ICE_SCRIPT_PATH": "/test/path/script.py",
            }.get(key, default)

            manager = ICEIngestionManager()
            assert manager is not None
            assert manager.status == IngestionStatus.IDLE

    @pytest.mark.parametrize(
        "credentials,folder_id,script_path,expected",
        [
            ('{"type": "service_account"}', "folder_123", "/path/script.py", True),
            (None, "folder_123", "/path/script.py", False),
            ('{"type": "service_account"}', None, "/path/script.py", False),
            ('{"type": "service_account"}', "folder_123", None, False),
            ("invalid_json", "folder_123", "/path/script.py", False),
        ],
    )
    def test_environment_validation_parametrized(
        self, ingestion_manager, credentials, folder_id, script_path, expected
    ):
        """Test environment validation with various parameter combinations."""
        with patch("ice_pipeline.ingestion.os.getenv") as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                "GOOGLE_CREDENTIALS_JSON": credentials,
                "GOOGLE_DRIVE_FOLDER_ID": folder_id,
                "ICE_SCRIPT_PATH": script_path,
            }.get(key, default)

            with patch("ice_pipeline.ingestion.Path.exists", return_value=True):
                result = ingestion_manager.validate_environment()
                assert result == expected

    def test_ingestion_status_enum(self):
        """Test IngestionStatus enum values."""
        assert IngestionStatus.IDLE.value == "idle"
        assert IngestionStatus.RUNNING.value == "running"
        assert IngestionStatus.COMPLETED.value == "completed"
        assert IngestionStatus.ERROR.value == "error"

    def test_ingestion_result_dataclass(self):
        """Test IngestionResult dataclass structure."""
        timestamp = datetime.now()
        result = IngestionResult(
            success=True,
            status=IngestionStatus.COMPLETED,
            output="Test output",
            error_message=None,
            return_code=0,
            execution_time=2.5,
            timestamp=timestamp,
        )

        assert result.success is True
        assert result.status == IngestionStatus.COMPLETED
        assert result.output == "Test output"
        assert result.error_message is None
        assert result.return_code == 0
        assert result.execution_time == 2.5
        assert result.timestamp == timestamp


@pytest.mark.integration
class TestICEIngestionIntegration:
    """Integration tests for ICE ingestion system."""

    @pytest.mark.asyncio
    async def test_full_ingestion_cycle_mock(self):
        """Test complete ingestion cycle with mocked dependencies."""
        with patch("ice_pipeline.ingestion.os.getenv") as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                "GOOGLE_CREDENTIALS_JSON": '{"type": "service_account"}',
                "GOOGLE_DRIVE_FOLDER_ID": "test_folder_id",
                "ICE_SCRIPT_PATH": "/test/path/script.py",
            }.get(key, default)

            with patch("ice_pipeline.ingestion.Path.exists", return_value=True):
                manager = ICEIngestionManager()

                # Mock successful process execution
                mock_process = AsyncMock()
                mock_process.returncode = 0
                mock_process.communicate.return_value = (
                    b"Ingestion completed successfully",
                    b"",
                )

                with patch(
                    "ice_pipeline.ingestion.asyncio.create_subprocess_exec",
                    return_value=mock_process,
                ):

                    # Test the complete cycle
                    assert manager.get_status() == IngestionStatus.IDLE

                    result = await manager.run_ingestion()

                    assert result.success is True
                    assert result.status == IngestionStatus.COMPLETED
                    assert manager.get_status() == IngestionStatus.IDLE
                    assert manager.get_last_result() is not None
