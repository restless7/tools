"""
Comprehensive API endpoint coverage tests for ICE Pipeline.

This module adds missing test scenarios to achieve better endpoint coverage
and includes advanced API testing patterns.
"""

import pytest
import json
import asyncio
import time
from unittest.mock import patch, Mock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import status
from datetime import datetime, timedelta
import threading

from ice_pipeline.api import app
from ice_pipeline.ingestion import IngestionStatus, IngestionResult


@pytest.mark.api_coverage
class TestICEAPIEndpointCoverage:
    """Comprehensive API endpoint coverage tests."""
    
    @pytest.fixture
    def client(self):
        """Create test client for comprehensive API testing."""
        return TestClient(app)
    
    # Health Endpoint Advanced Scenarios
    def test_health_endpoint_detailed_response(self, client):
        """Test detailed health endpoint response structure."""
        response = client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify all required fields
        required_fields = ["status", "timestamp", "version", "services"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify timestamp format
        timestamp = datetime.fromisoformat(data["timestamp"])
        assert isinstance(timestamp, datetime)
        
        # Verify services status
        assert "ice_ingestion" in data["services"]
        assert data["services"]["ice_ingestion"] in ["active", "unavailable"]
    
    def test_health_endpoint_multiple_calls(self, client):
        """Test health endpoint consistency across multiple calls."""
        responses = []
        for _ in range(5):
            response = client.get("/health")
            responses.append(response)
        
        # All should succeed
        for response in responses:
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "healthy"
    
    def test_health_endpoint_concurrent_access(self, client):
        """Test health endpoint under concurrent access."""
        results = []
        
        def make_health_request():
            response = client.get("/health")
            results.append(response.status_code)
        
        # Create multiple concurrent requests
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_health_request)
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # All should succeed
        assert len(results) == 10
        assert all(status_code == 200 for status_code in results)
    
    # Excel Conversion Advanced Scenarios
    def test_excel_conversion_all_formats(self, client):
        """Test Excel conversion with all supported formats."""
        formats = ["csv", "json", "parquet"]
        
        for output_format in formats:
            with patch('ice_pipeline.api.process_excel_conversion') as mock_process:
                mock_process.return_value = {
                    "success": True,
                    "output_file": f"/test/output.{output_format}",
                    "rows_processed": 100,
                    "metadata": {"format": output_format},
                    "processing_time": 2.5
                }
                
                request_data = {
                    "file_path": f"/test/input_{output_format}.xlsx",
                    "output_format": output_format,
                    "include_metadata": True
                }
                
                response = client.post("/convert-excel", json=request_data)
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["success"] is True
                assert data["output_file"].endswith(f".{output_format}")
                assert data["metadata"]["format"] == output_format
    
    def test_excel_conversion_with_without_metadata(self, client):
        """Test Excel conversion with and without metadata."""
        test_cases = [
            {"include_metadata": True, "expected_metadata": {"sheets": ["Sheet1"]}},
            {"include_metadata": False, "expected_metadata": None}
        ]
        
        for test_case in test_cases:
            with patch('ice_pipeline.api.process_excel_conversion') as mock_process:
                mock_process.return_value = {
                    "success": True,
                    "output_file": "/test/output.csv",
                    "rows_processed": 50,
                    "metadata": test_case["expected_metadata"],
                    "processing_time": 1.0
                }
                
                request_data = {
                    "file_path": "/test/input.xlsx",
                    "output_format": "csv",
                    "include_metadata": test_case["include_metadata"]
                }
                
                response = client.post("/convert-excel", json=request_data)
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["metadata"] == test_case["expected_metadata"]
    
    def test_excel_conversion_various_file_sizes(self, client):
        """Test Excel conversion with various file sizes."""
        file_sizes = [
            {"name": "small", "rows": 10},
            {"name": "medium", "rows": 1000},
            {"name": "large", "rows": 100000}
        ]
        
        for file_size in file_sizes:
            with patch('ice_pipeline.api.process_excel_conversion') as mock_process:
                mock_process.return_value = {
                    "success": True,
                    "output_file": f"/test/{file_size['name']}.csv",
                    "rows_processed": file_size["rows"],
                    "processing_time": file_size["rows"] / 10000  # Simulate processing time
                }
                
                request_data = {
                    "file_path": f"/test/{file_size['name']}.xlsx",
                    "output_format": "csv"
                }
                
                response = client.post("/convert-excel", json=request_data)
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["rows_processed"] == file_size["rows"]
    
    # ICE Status Endpoint Advanced Scenarios
    def test_ice_status_all_possible_states(self, client):
        """Test ICE status endpoint with all possible ingestion states."""
        states = [
            IngestionStatus.IDLE,
            IngestionStatus.RUNNING,
            IngestionStatus.COMPLETED,
            IngestionStatus.ERROR
        ]
        
        for state in states:
            with patch('ice_pipeline.api.ingestion_manager') as mock_manager:
                mock_manager.get_status.return_value = state
                mock_manager.get_last_result.return_value = None
                
                response = client.get("/ice/status")
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["status"] == state.value
                assert "timestamp" in data
    
    def test_ice_status_with_various_results(self, client):
        """Test ICE status endpoint with various last results."""
        test_results = [
            {
                "success": True,
                "status": IngestionStatus.COMPLETED,
                "output": "Success message",
                "error_message": None,
                "execution_time": 30.5
            },
            {
                "success": False,
                "status": IngestionStatus.ERROR,
                "output": "",
                "error_message": "Test error",
                "execution_time": 5.2
            }
        ]
        
        for test_result in test_results:
            mock_result = IngestionResult(
                success=test_result["success"],
                status=test_result["status"],
                output=test_result["output"],
                error_message=test_result["error_message"],
                return_code=0 if test_result["success"] else 1,
                execution_time=test_result["execution_time"],
                timestamp=datetime.now()
            )
            
            with patch('ice_pipeline.api.ingestion_manager') as mock_manager:
                mock_manager.get_status.return_value = IngestionStatus.IDLE
                mock_manager.get_last_result.return_value = mock_result
                
                response = client.get("/ice/status")
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["last_result"]["success"] == test_result["success"]
                assert data["last_result"]["execution_time"] == test_result["execution_time"]
    
    # ICE Trigger Endpoint Advanced Scenarios
    def test_ice_trigger_various_conditions(self, client):
        """Test ICE trigger endpoint under various conditions."""
        conditions = [
            {"status": IngestionStatus.IDLE, "should_succeed": True},
            {"status": IngestionStatus.COMPLETED, "should_succeed": True},
            {"status": IngestionStatus.ERROR, "should_succeed": True},
            {"status": IngestionStatus.RUNNING, "should_succeed": False}
        ]
        
        for condition in conditions:
            with patch('ice_pipeline.api.ingestion_manager') as mock_manager:
                mock_manager.get_status.return_value = condition["status"]
                
                async def mock_run_ingestion():
                    return IngestionResult(
                        success=True,
                        status=IngestionStatus.COMPLETED,
                        output="Mock ingestion",
                        error_message=None,
                        return_code=0,
                        execution_time=10.0,
                        timestamp=datetime.now()
                    )
                
                mock_manager.run_ingestion = mock_run_ingestion
                
                response = client.post("/ice/trigger")
                
                if condition["should_succeed"]:
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    assert data["status"] == "triggered"
                else:
                    assert response.status_code == status.HTTP_409_CONFLICT
    
    def test_ice_trigger_background_task_simulation(self, client):
        """Test ICE trigger background task behavior."""
        with patch('ice_pipeline.api.ingestion_manager') as mock_manager:
            mock_manager.get_status.return_value = IngestionStatus.IDLE
            
            # Track if background task was added
            background_task_added = False
            
            def mock_add_task(task):
                nonlocal background_task_added
                background_task_added = True
            
            # Mock the background tasks
            with patch('ice_pipeline.api.BackgroundTasks') as mock_bg_tasks_class:
                mock_bg_tasks = Mock()
                mock_bg_tasks.add_task = mock_add_task
                mock_bg_tasks_class.return_value = mock_bg_tasks
                
                # Mock the endpoint's background_tasks parameter
                response = client.post("/ice/trigger")
                
                assert response.status_code == status.HTTP_200_OK
                # Note: In actual FastAPI, background tasks are handled differently
                # This tests the endpoint logic, not the actual background execution
    
    # ICE Cleanup Endpoint Advanced Scenarios
    def test_ice_cleanup_various_scenarios(self, client):
        """Test ICE cleanup endpoint with various cleanup scenarios."""
        cleanup_scenarios = [
            {
                "name": "minimal_cleanup",
                "result": {
                    "status": "completed",
                    "files_cleaned": 0,
                    "temp_dirs_removed": 0,
                    "cache_cleared": True,
                    "space_freed_mb": 0
                }
            },
            {
                "name": "moderate_cleanup",
                "result": {
                    "status": "completed",
                    "files_cleaned": 15,
                    "temp_dirs_removed": 3,
                    "cache_cleared": True,
                    "space_freed_mb": 256
                }
            },
            {
                "name": "extensive_cleanup",
                "result": {
                    "status": "completed",
                    "files_cleaned": 100,
                    "temp_dirs_removed": 10,
                    "cache_cleared": True,
                    "space_freed_mb": 2048,
                    "warnings": ["Some files could not be removed due to permissions"]
                }
            }
        ]
        
        for scenario in cleanup_scenarios:
            with patch('ice_pipeline.api.cleanup_ingestion_resources') as mock_cleanup:
                mock_cleanup.return_value = scenario["result"]
                
                response = client.post("/ice/cleanup")
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                for key, expected_value in scenario["result"].items():
                    assert data[key] == expected_value
    
    def test_ice_cleanup_partial_failures(self, client):
        """Test ICE cleanup with partial failures."""
        with patch('ice_pipeline.api.cleanup_ingestion_resources') as mock_cleanup:
            mock_cleanup.return_value = {
                "status": "completed",
                "files_cleaned": 8,
                "temp_dirs_removed": 2,
                "cache_cleared": False,  # Partial failure
                "space_freed_mb": 128,
                "warnings": [
                    "Could not clear Redis cache: Connection refused",
                    "Permission denied for file: /tmp/locked_file"
                ]
            }
            
            response = client.post("/ice/cleanup")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            # Should still return success even with warnings
            assert data["status"] == "completed"
            assert data["cache_cleared"] is False
            assert len(data["warnings"]) == 2
    
    # Response Format and Headers Testing
    def test_api_response_headers(self, client):
        """Test API response headers across endpoints."""
        endpoints = [
            ("GET", "/health"),
            ("GET", "/ice/status"),
        ]
        
        for method, endpoint in endpoints:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint)
            
            # Check content type
            assert "content-type" in response.headers
            assert "application/json" in response.headers["content-type"]
            
            # Check CORS headers (if configured)
            # These would depend on the specific CORS configuration
    
    def test_api_response_consistency(self, client):
        """Test API response format consistency."""
        # Test that all successful responses have consistent structure
        with patch('ice_pipeline.api.process_excel_conversion') as mock_process:
            mock_process.return_value = {
                "success": True,
                "output_file": "/test/output.csv",
                "rows_processed": 100,
                "processing_time": 2.0
            }
            
            response = client.post("/convert-excel", json={
                "file_path": "/test/input.xlsx",
                "output_format": "csv"
            })
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            # All responses should have consistent field types
            assert isinstance(data["success"], bool)
            assert isinstance(data["output_file"], str)
            assert isinstance(data["rows_processed"], int)
    
    # Performance and Load Testing
    def test_api_sequential_requests_performance(self, client):
        """Test API performance with sequential requests."""
        start_time = time.time()
        
        # Make 20 sequential health check requests
        for _ in range(20):
            response = client.get("/health")
            assert response.status_code == status.HTTP_200_OK
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Should complete within reasonable time (adjust based on requirements)
        assert total_time < 5.0  # 20 requests in under 5 seconds
        
        # Calculate average response time
        avg_response_time = total_time / 20
        assert avg_response_time < 0.25  # Each request under 250ms on average
    
    def test_api_mixed_endpoint_requests(self, client):
        """Test mixed endpoint requests for realistic usage patterns."""
        endpoints = [
            ("GET", "/health"),
            ("GET", "/ice/status"),
        ]
        
        # Mock dependencies for status endpoint
        with patch('ice_pipeline.api.ingestion_manager') as mock_manager:
            mock_manager.get_status.return_value = IngestionStatus.IDLE
            mock_manager.get_last_result.return_value = None
            
            for i in range(10):
                method, endpoint = endpoints[i % len(endpoints)]
                
                if method == "GET":
                    response = client.get(endpoint)
                
                assert response.status_code == status.HTTP_200_OK
    
    # Edge Cases in API Usage
    def test_api_request_size_limits(self, client):
        """Test API behavior with various request sizes."""
        # Test very small request
        minimal_request = {
            "file_path": "/a.xlsx",
            "output_format": "csv"
        }
        
        with patch('ice_pipeline.api.process_excel_conversion') as mock_process:
            mock_process.return_value = {
                "success": True,
                "output_file": "/a.csv",
                "rows_processed": 1,
                "processing_time": 0.1
            }
            
            response = client.post("/convert-excel", json=minimal_request)
            assert response.status_code == status.HTTP_200_OK
        
        # Test request with maximum allowed data
        large_request = {
            "file_path": "/test/" + "a" * 500 + ".xlsx",  # Large but valid path
            "output_format": "csv",
            "include_metadata": True
        }
        
        with patch('ice_pipeline.api.process_excel_conversion') as mock_process:
            mock_process.return_value = {
                "success": True,
                "output_file": "/test/output.csv",
                "rows_processed": 1000,
                "processing_time": 5.0
            }
            
            response = client.post("/convert-excel", json=large_request)
            # Should handle large requests appropriately
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY]
    
    def test_api_content_negotiation(self, client):
        """Test API content negotiation and Accept headers."""
        # Test with explicit JSON accept header
        headers = {"Accept": "application/json"}
        response = client.get("/health", headers=headers)
        
        assert response.status_code == status.HTTP_200_OK
        assert "application/json" in response.headers.get("content-type", "")
        
        # Verify JSON content
        data = response.json()
        assert isinstance(data, dict)


@pytest.mark.api_integration
class TestICEAPIIntegrationScenarios:
    """Advanced API integration scenarios."""
    
    @pytest.fixture
    def client(self):
        """Create test client for integration testing."""
        return TestClient(app)
    
    def test_complete_workflow_simulation(self, client):
        """Test complete workflow from health check to cleanup."""
        # Step 1: Health check
        health_response = client.get("/health")
        assert health_response.status_code == status.HTTP_200_OK
        
        # Step 2: Check ICE status
        with patch('ice_pipeline.api.ingestion_manager') as mock_manager:
            mock_manager.get_status.return_value = IngestionStatus.IDLE
            mock_manager.get_last_result.return_value = None
            
            status_response = client.get("/ice/status")
            assert status_response.status_code == status.HTTP_200_OK
            assert status_response.json()["status"] == "idle"
        
        # Step 3: Excel conversion
        with patch('ice_pipeline.api.process_excel_conversion') as mock_process:
            mock_process.return_value = {
                "success": True,
                "output_file": "/test/workflow.csv",
                "rows_processed": 200,
                "processing_time": 3.0
            }
            
            convert_response = client.post("/convert-excel", json={
                "file_path": "/test/workflow.xlsx",
                "output_format": "csv"
            })
            assert convert_response.status_code == status.HTTP_200_OK
        
        # Step 4: ICE ingestion trigger
        with patch('ice_pipeline.api.ingestion_manager') as mock_manager:
            mock_manager.get_status.return_value = IngestionStatus.IDLE
            
            async def mock_run_ingestion():
                return IngestionResult(
                    success=True,
                    status=IngestionStatus.COMPLETED,
                    output="Workflow test completed",
                    error_message=None,
                    return_code=0,
                    execution_time=45.0,
                    timestamp=datetime.now()
                )
            
            mock_manager.run_ingestion = mock_run_ingestion
            
            trigger_response = client.post("/ice/trigger")
            assert trigger_response.status_code == status.HTTP_200_OK
        
        # Step 5: Final status check
        with patch('ice_pipeline.api.ingestion_manager') as mock_manager:
            mock_result = IngestionResult(
                success=True,
                status=IngestionStatus.COMPLETED,
                output="Workflow completed",
                error_message=None,
                return_code=0,
                execution_time=45.0,
                timestamp=datetime.now()
            )
            
            mock_manager.get_status.return_value = IngestionStatus.IDLE
            mock_manager.get_last_result.return_value = mock_result
            
            final_status = client.get("/ice/status")
            assert final_status.status_code == status.HTTP_200_OK
            assert final_status.json()["last_result"]["success"] is True
        
        # Step 6: Cleanup
        with patch('ice_pipeline.api.cleanup_ingestion_resources') as mock_cleanup:
            mock_cleanup.return_value = {
                "status": "completed",
                "files_cleaned": 5,
                "temp_dirs_removed": 1,
                "cache_cleared": True,
                "space_freed_mb": 64
            }
            
            cleanup_response = client.post("/ice/cleanup")
            assert cleanup_response.status_code == status.HTTP_200_OK
            assert cleanup_response.json()["files_cleaned"] == 5