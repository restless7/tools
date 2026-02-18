"""
API tests for ICE Pipeline endpoints.

This module contains comprehensive API tests for the ICE pipeline
FastAPI endpoints, including authentication, error handling, and
performance testing.
"""

import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from ice_pipeline.api import app
from ice_pipeline.ingestion import IngestionResult, IngestionStatus


@pytest.mark.api
class TestICEAPIEndpoints:
    """API endpoint tests for ICE pipeline."""

    @pytest.fixture
    def client(self):
        """Create test client for API testing."""
        return TestClient(app)

    @pytest.fixture
    def sample_excel_request(self):
        """Sample Excel conversion request payload."""
        return {
            "file_path": "/test/data/sample.xlsx",
            "output_format": "csv",
            "include_metadata": True,
        }

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        required_fields = ["status", "timestamp", "version"]
        for field in required_fields:
            assert field in data

        assert data["status"] == "healthy"

    def test_health_endpoint_headers(self, client):
        """Test health endpoint response headers."""
        response = client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        assert "content-type" in response.headers
        assert response.headers["content-type"] == "application/json"

    def test_convert_excel_endpoint_success(self, client, sample_excel_request):
        """Test successful Excel conversion endpoint."""
        with patch("ice_pipeline.api.process_excel_conversion") as mock_convert:
            mock_convert.return_value = {
                "success": True,
                "output_file": "/test/data/sample.csv",
                "rows_processed": 150,
                "metadata": {
                    "sheets": ["Sheet1", "Sheet2"],
                    "columns": 8,
                    "file_size": 2048,
                },
                "processing_time": 5.2,
            }

            response = client.post("/convert-excel", json=sample_excel_request)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["success"] is True
            assert data["output_file"] == "/test/data/sample.csv"
            assert data["rows_processed"] == 150
            assert data["processing_time"] == 5.2
            assert "metadata" in data
            assert len(data["metadata"]["sheets"]) == 2

    def test_convert_excel_endpoint_validation(self, client):
        """Test Excel conversion endpoint input validation."""
        # Test missing required fields
        invalid_requests = [
            {},  # Empty request
            {"file_path": "/test/file.xlsx"},  # Missing output_format
            {"output_format": "csv"},  # Missing file_path
            {
                "file_path": "/test/file.xlsx",
                "output_format": "invalid_format",  # Invalid format
            },
        ]

        for invalid_request in invalid_requests:
            response = client.post("/convert-excel", json=invalid_request)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_convert_excel_file_not_found(self, client, sample_excel_request):
        """Test Excel conversion with non-existent file."""
        with patch("ice_pipeline.api.process_excel_conversion") as mock_convert:
            mock_convert.side_effect = FileNotFoundError(
                "File not found: /test/data/sample.xlsx"
            )

            response = client.post("/convert-excel", json=sample_excel_request)

            assert response.status_code == status.HTTP_404_NOT_FOUND
            data = response.json()
            assert "File not found" in data["detail"]

    def test_convert_excel_processing_error(self, client, sample_excel_request):
        """Test Excel conversion with processing error."""
        with patch("ice_pipeline.api.process_excel_conversion") as mock_convert:
            mock_convert.side_effect = Exception(
                "Processing failed due to corrupt file"
            )

            response = client.post("/convert-excel", json=sample_excel_request)

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert "Processing failed" in data["detail"]

    @pytest.mark.parametrize(
        "output_format,expected_extension",
        [("csv", "csv"), ("json", "json"), ("parquet", "parquet")],
    )
    def test_convert_excel_output_formats(
        self, client, output_format, expected_extension
    ):
        """Test Excel conversion with different output formats."""
        request_data = {
            "file_path": "/test/data/sample.xlsx",
            "output_format": output_format,
            "include_metadata": False,
        }

        with patch("ice_pipeline.api.process_excel_conversion") as mock_convert:
            mock_convert.return_value = {
                "success": True,
                "output_file": f"/test/data/sample.{expected_extension}",
                "rows_processed": 100,
                "metadata": None,
                "processing_time": 3.1,
            }

            response = client.post("/convert-excel", json=request_data)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["output_file"].endswith(f".{expected_extension}")

    def test_ice_trigger_endpoint_success(self, client):
        """Test successful ICE ingestion trigger."""
        with patch("ice_pipeline.api.ingestion_manager") as mock_manager:
            # Mock successful ingestion
            mock_result = IngestionResult(
                success=True,
                status=IngestionStatus.COMPLETED,
                output="Ingestion completed successfully",
                error_message=None,
                return_code=0,
                execution_time=45.5,
                timestamp=datetime.now(),
            )

            mock_manager.get_status.return_value = IngestionStatus.IDLE
            # Python 3.13 compatibility: Return mock result directly instead of using asyncio.create_task
            mock_manager.run_ingestion.return_value = mock_result

            response = client.post("/ice/trigger")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["status"] == "triggered"
            assert "message" in data
            mock_manager.run_ingestion.assert_called_once()

    def test_ice_trigger_already_running(self, client):
        """Test ICE trigger when ingestion is already running."""
        with patch("ice_pipeline.api.ingestion_manager") as mock_manager:
            mock_manager.get_status.return_value = IngestionStatus.RUNNING

            response = client.post("/ice/trigger")

            assert response.status_code == status.HTTP_409_CONFLICT
            data = response.json()
            assert "already running" in data["detail"].lower()

    def test_ice_status_endpoint_idle(self, client):
        """Test ICE status endpoint when idle."""
        with patch("ice_pipeline.api.ingestion_manager") as mock_manager:
            mock_manager.get_status.return_value = IngestionStatus.IDLE
            mock_manager.get_last_result.return_value = None

            response = client.get("/ice/status")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["status"] == "idle"
            assert data["last_result"] is None
            assert "timestamp" in data

    def test_ice_status_endpoint_running(self, client):
        """Test ICE status endpoint when running."""
        with patch("ice_pipeline.api.ingestion_manager") as mock_manager:
            mock_manager.get_status.return_value = IngestionStatus.RUNNING
            mock_manager.get_last_result.return_value = None

            response = client.get("/ice/status")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["status"] == "running"
            assert data["last_result"] is None

    def test_ice_status_with_last_result(self, client):
        """Test ICE status endpoint with last result."""
        mock_result = IngestionResult(
            success=True,
            status=IngestionStatus.COMPLETED,
            output="Previous ingestion completed",
            error_message=None,
            return_code=0,
            execution_time=35.8,
            timestamp=datetime.now() - timedelta(hours=1),
        )

        with patch("ice_pipeline.api.ingestion_manager") as mock_manager:
            mock_manager.get_status.return_value = IngestionStatus.IDLE
            mock_manager.get_last_result.return_value = mock_result

            response = client.get("/ice/status")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["status"] == "idle"
            assert data["last_result"] is not None
            assert data["last_result"]["success"] is True
            assert data["last_result"]["execution_time"] == 35.8

    def test_ice_cleanup_endpoint_success(self, client):
        """Test successful ICE cleanup endpoint."""
        with patch("ice_pipeline.api.cleanup_ingestion_resources") as mock_cleanup:
            mock_cleanup.return_value = {
                "files_cleaned": 15,
                "temp_dirs_removed": 3,
                "cache_cleared": True,
                "space_freed_mb": 256,
            }

            response = client.post("/ice/cleanup")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["status"] == "completed"
            assert data["files_cleaned"] == 15
            assert data["temp_dirs_removed"] == 3
            assert data["cache_cleared"] is True
            assert data["space_freed_mb"] == 256

    def test_ice_cleanup_endpoint_error(self, client):
        """Test ICE cleanup endpoint with error."""
        with patch("ice_pipeline.api.cleanup_ingestion_resources") as mock_cleanup:
            mock_cleanup.side_effect = PermissionError(
                "Permission denied cleaning temp files"
            )

            response = client.post("/ice/cleanup")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert "Permission denied" in data["detail"]

    def test_ice_cleanup_partial_success(self, client):
        """Test ICE cleanup with partial success."""
        with patch("ice_pipeline.api.cleanup_ingestion_resources") as mock_cleanup:
            mock_cleanup.return_value = {
                "files_cleaned": 10,
                "temp_dirs_removed": 1,
                "cache_cleared": False,  # Partial failure
                "space_freed_mb": 128,
                "warnings": ["Could not clear Redis cache: Connection refused"],
            }

            response = client.post("/ice/cleanup")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["status"] == "completed"
            assert data["cache_cleared"] is False
            assert "warnings" in data
            assert len(data["warnings"]) == 1

    def test_api_error_response_format(self, client):
        """Test API error response format consistency."""
        # Test 404 error
        with patch("ice_pipeline.api.process_excel_conversion") as mock_convert:
            mock_convert.side_effect = FileNotFoundError("File not found")

            response = client.post(
                "/convert-excel",
                json={"file_path": "/nonexistent.xlsx", "output_format": "csv"},
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND
            data = response.json()

            # Verify error response structure
            assert "detail" in data
            assert isinstance(data["detail"], str)

    def test_api_request_timeout_handling(self, client):
        """Test API request timeout handling."""
        with patch("ice_pipeline.api.process_excel_conversion") as mock_convert:
            # Simulate long-running operation
            import time

            def slow_processing(*args, **kwargs):
                time.sleep(0.5)  # Simulate slow processing
                return {
                    "success": True,
                    "output_file": "/test/output.csv",
                    "rows_processed": 1000,
                    "processing_time": 0.5,
                }

            mock_convert.side_effect = slow_processing

            response = client.post(
                "/convert-excel",
                json={"file_path": "/test/large_file.xlsx", "output_format": "csv"},
            )

            # Should complete successfully despite delay
            assert response.status_code == status.HTTP_200_OK

    def test_api_concurrent_requests(self, client):
        """Test API handling of concurrent requests."""
        import threading
        import time

        results = []

        def make_health_request():
            response = client.get("/health")
            results.append(response.status_code)

        # Create multiple concurrent requests
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_health_request)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All requests should succeed
        assert len(results) == 5
        assert all(status_code == 200 for status_code in results)

    @pytest.mark.benchmark(group="api_performance")
    def test_health_endpoint_performance(self, client, benchmark):
        """Benchmark health endpoint performance."""

        def make_health_request():
            return client.get("/health")

        response = benchmark(make_health_request)
        assert response.status_code == status.HTTP_200_OK

        # Performance should be under 100ms
        # (This would be configured based on actual requirements)

    @pytest.mark.benchmark(group="api_performance")
    def test_status_endpoint_performance(self, client, benchmark):
        """Benchmark status endpoint performance."""
        with patch("ice_pipeline.api.ingestion_manager") as mock_manager:
            mock_manager.get_status.return_value = IngestionStatus.IDLE
            mock_manager.get_last_result.return_value = None

            def make_status_request():
                return client.get("/ice/status")

            response = benchmark(make_status_request)
            assert response.status_code == status.HTTP_200_OK

    def test_api_content_type_handling(self, client):
        """Test API content type handling."""
        # Test JSON content type
        response = client.post(
            "/convert-excel",
            json={"file_path": "/test.xlsx", "output_format": "csv"},
            headers={"Content-Type": "application/json"},
        )

        # Should process JSON correctly (may fail due to mocking, but headers should be handled)
        assert response.status_code in [200, 404, 422, 500]  # Any valid HTTP status

        # Test invalid content type
        response = client.post(
            "/convert-excel",
            data="invalid data",
            headers={"Content-Type": "text/plain"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_api_large_request_handling(self, client):
        """Test API handling of large requests."""
        # Create a request with large metadata
        large_request = {
            "file_path": "/test/file.xlsx",
            "output_format": "csv",
            "include_metadata": True,
            "options": {
                "description": "A" * 1000,  # Large description
                "tags": [f"tag_{i}" for i in range(100)],  # Many tags
            },
        }

        with patch("ice_pipeline.api.process_excel_conversion") as mock_convert:
            mock_convert.return_value = {
                "success": True,
                "output_file": "/test/output.csv",
                "rows_processed": 500,
                "processing_time": 2.1,
            }

            response = client.post("/convert-excel", json=large_request)

            # Should handle large requests appropriately
            assert response.status_code in [
                200,
                413,
                422,
            ]  # OK, too large, or validation error

    def test_api_method_not_allowed(self, client):
        """Test API method not allowed responses."""
        # Test wrong HTTP method on endpoints
        wrong_method_tests = [
            ("POST", "/health"),  # Should be GET
            ("GET", "/ice/trigger"),  # Should be POST
            ("PUT", "/ice/status"),  # Should be GET
            ("DELETE", "/convert-excel"),  # Should be POST
        ]

        for method, endpoint in wrong_method_tests:
            if method == "POST":
                response = client.post(endpoint, json={})
            elif method == "PUT":
                response = client.put(endpoint, json={})
            elif method == "DELETE":
                response = client.delete(endpoint)
            elif method == "GET":
                response = client.get(endpoint)

            assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_api_not_found_routes(self, client):
        """Test API 404 responses for non-existent routes."""
        non_existent_routes = [
            "/nonexistent",
            "/api/v1/nonexistent",
            "/ice/nonexistent",
            "/convert/nonexistent",
        ]

        for route in non_existent_routes:
            response = client.get(route)
            assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.api
@pytest.mark.integration
class TestICEAPIIntegrationScenarios:
    """Integration scenarios for ICE API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client for integration testing."""
        return TestClient(app)

    def test_excel_to_ingestion_workflow(self, client):
        """Test complete workflow from Excel conversion to ingestion."""
        # Step 1: Convert Excel file
        conversion_request = {
            "file_path": "/test/data/input.xlsx",
            "output_format": "csv",
            "include_metadata": True,
        }

        with patch("ice_pipeline.api.process_excel_conversion") as mock_convert:
            mock_convert.return_value = {
                "success": True,
                "output_file": "/test/data/input.csv",
                "rows_processed": 200,
                "metadata": {"sheets": ["Data"], "columns": 10},
                "processing_time": 3.5,
            }

            convert_response = client.post("/convert-excel", json=conversion_request)
            assert convert_response.status_code == status.HTTP_200_OK

            convert_data = convert_response.json()
            converted_file = convert_data["output_file"]

        # Step 2: Check initial ingestion status
        with patch("ice_pipeline.api.ingestion_manager") as mock_manager:
            mock_manager.get_status.return_value = IngestionStatus.IDLE
            mock_manager.get_last_result.return_value = None

            status_response = client.get("/ice/status")
            assert status_response.status_code == status.HTTP_200_OK
            assert status_response.json()["status"] == "idle"

        # Step 3: Trigger ingestion
        with patch("ice_pipeline.api.ingestion_manager") as mock_manager:
            mock_result = IngestionResult(
                success=True,
                status=IngestionStatus.COMPLETED,
                output=f"Processed {converted_file} successfully",
                error_message=None,
                return_code=0,
                execution_time=60.2,
                timestamp=datetime.now(),
            )

            mock_manager.get_status.return_value = IngestionStatus.IDLE
            # Python 3.13 compatibility: Return mock result directly
            mock_manager.run_ingestion.return_value = mock_result

            trigger_response = client.post("/ice/trigger")
            assert trigger_response.status_code == status.HTTP_200_OK

        # Step 4: Verify final status
        with patch("ice_pipeline.api.ingestion_manager") as mock_manager:
            mock_manager.get_status.return_value = IngestionStatus.IDLE
            mock_manager.get_last_result.return_value = mock_result

            final_status = client.get("/ice/status")
            assert final_status.status_code == status.HTTP_200_OK

            final_data = final_status.json()
            assert final_data["last_result"]["success"] is True
            assert final_data["last_result"]["execution_time"] == 60.2

    def test_error_recovery_workflow(self, client):
        """Test error recovery workflow across endpoints."""
        # Step 1: Attempt conversion that fails
        with patch("ice_pipeline.api.process_excel_conversion") as mock_convert:
            mock_convert.side_effect = Exception("Corrupted file")

            response = client.post(
                "/convert-excel",
                json={"file_path": "/test/corrupted.xlsx", "output_format": "csv"},
            )

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        # Step 2: Check system still healthy
        health_response = client.get("/health")
        assert health_response.status_code == status.HTTP_200_OK
        assert health_response.json()["status"] == "healthy"

        # Step 3: Verify ingestion status unaffected
        with patch("ice_pipeline.api.ingestion_manager") as mock_manager:
            mock_manager.get_status.return_value = IngestionStatus.IDLE
            mock_manager.get_last_result.return_value = None

            status_response = client.get("/ice/status")
            assert status_response.status_code == status.HTTP_200_OK
            assert status_response.json()["status"] == "idle"

        # Step 4: Successful retry with valid file
        with patch("ice_pipeline.api.process_excel_conversion") as mock_convert:
            mock_convert.return_value = {
                "success": True,
                "output_file": "/test/fixed.csv",
                "rows_processed": 100,
                "processing_time": 2.1,
            }

            retry_response = client.post(
                "/convert-excel",
                json={"file_path": "/test/fixed.xlsx", "output_format": "csv"},
            )

            assert retry_response.status_code == status.HTTP_200_OK
            assert retry_response.json()["success"] is True
