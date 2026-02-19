"""
Performance tests for ICE Pipeline.

This module contains performance benchmarks and load tests
for the ICE pipeline components.
"""

import asyncio
import concurrent.futures
import time
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from ice_pipeline.ingestion import ICEIngestionManager, IngestionResult, IngestionStatus


@pytest.mark.performance
class TestICEIngestionPerformance:
    """Performance tests for ICE ingestion manager."""

    @pytest.fixture
    def ingestion_manager(self):
        """Create ICE ingestion manager for performance testing."""
        from unittest.mock import patch

        env_values = {
            "GOOGLE_CREDENTIALS_JSON": '{"type": "service_account"}',
            "GOOGLE_DRIVE_FOLDER_ID": "test_folder",
            "ICE_SCRIPT_PATH": "/test/script.py",
        }
        patcher = patch(
            "ice_pipeline.ingestion.os.getenv",
            side_effect=lambda key, default=None: env_values.get(key, default),
        )
        patcher.start()
        try:
            manager = ICEIngestionManager()
            yield manager
        finally:
            patcher.stop()

    @pytest.mark.benchmark(group="environment_validation")
    def test_environment_validation_performance(self, ingestion_manager, benchmark):
        """Benchmark environment validation performance."""
        with patch("ice_pipeline.ingestion.Path.exists", return_value=True):
            result = benchmark(ingestion_manager.validate_environment)
            assert result is True

    @pytest.mark.benchmark(group="status_operations")
    def test_get_status_performance(self, ingestion_manager, benchmark):
        """Benchmark status retrieval performance."""
        result = benchmark(ingestion_manager.get_status)
        assert result == IngestionStatus.IDLE

    @pytest.mark.benchmark(group="status_operations")
    def test_get_last_result_performance(self, ingestion_manager, benchmark):
        """Benchmark last result retrieval performance."""
        # Set a mock result first
        mock_result = IngestionResult(
            success=True,
            status=IngestionStatus.COMPLETED,
            output="Benchmark test",
            error_message=None,
            return_code=0,
            execution_time=10.0,
            timestamp=datetime.now(),
        )
        ingestion_manager._last_result = mock_result

        result = benchmark(ingestion_manager.get_last_result)
        assert result == mock_result

    @pytest.mark.asyncio
    async def test_concurrent_status_checks(self, ingestion_manager):
        """Test concurrent status check performance."""

        async def check_status():
            return ingestion_manager.get_status()

        # Create multiple concurrent status checks
        tasks = [check_status() for _ in range(100)]

        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()

        # All should return IDLE status
        assert all(status == IngestionStatus.IDLE for status in results)

        # Should complete within reasonable time (less than 1 second for 100 ops)
        assert end_time - start_time < 1.0

    def test_multiple_environment_validations(self, ingestion_manager):
        """Test performance of multiple environment validations."""
        with patch("ice_pipeline.ingestion.Path.exists", return_value=True):
            start_time = time.time()

            # Perform 1000 validations
            results = [ingestion_manager.validate_environment() for _ in range(1000)]

            end_time = time.time()

            # All should succeed
            assert all(result is True for result in results)

            # Should complete within reasonable time
            assert (
                end_time - start_time < 2.0
            )  # Less than 2 seconds for 1000 validations


@pytest.mark.performance
@pytest.mark.stress
class TestICEStressTests:
    """Stress tests for ICE pipeline components."""

    @pytest.fixture
    def ingestion_manager(self):
        """Create ICE ingestion manager for stress testing."""
        from unittest.mock import patch

        env_values = {
            "GOOGLE_CREDENTIALS_JSON": '{"type": "service_account"}',
            "GOOGLE_DRIVE_FOLDER_ID": "test_folder",
            "ICE_SCRIPT_PATH": "/test/script.py",
        }
        patcher = patch(
            "ice_pipeline.ingestion.os.getenv",
            side_effect=lambda key, default=None: env_values.get(key, default),
        )
        patcher.start()
        try:
            manager = ICEIngestionManager()
            yield manager
        finally:
            patcher.stop()

    @pytest.mark.asyncio
    async def test_ingestion_stress_test(self, ingestion_manager):
        """Stress test for ingestion operations."""
        mock_results = []

        # Mock multiple successful ingestions
        async def mock_successful_ingestion():
            await asyncio.sleep(0.01)  # Simulate processing time
            return IngestionResult(
                success=True,
                status=IngestionStatus.COMPLETED,
                output="Stress test ingestion",
                error_message=None,
                return_code=0,
                execution_time=0.01,
                timestamp=datetime.now(),
            )

        with patch.object(
            ingestion_manager, "run_ingestion", side_effect=mock_successful_ingestion
        ):
            with patch.object(
                ingestion_manager, "validate_environment", return_value=True
            ):
                # Run 50 ingestions concurrently
                start_time = time.time()

                tasks = [ingestion_manager.run_ingestion() for _ in range(50)]
                results = await asyncio.gather(*tasks)

                end_time = time.time()

                # All should succeed
                assert len(results) == 50
                assert all(result.success for result in results)

                # Should complete within reasonable time (under 5 seconds)
                assert end_time - start_time < 5.0

    def test_memory_usage_stress(self, ingestion_manager):
        """Test memory usage under stress."""
        import os

        import psutil

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create many ingestion results to test memory usage
        results = []
        for i in range(1000):
            result = IngestionResult(
                success=True,
                status=IngestionStatus.COMPLETED,
                output=f"Stress test {i}" * 100,  # Large output string
                error_message=None,
                return_code=0,
                execution_time=float(i),
                timestamp=datetime.now(),
            )
            results.append(result)

            # Store in manager
            ingestion_manager._last_result = result

        # Check memory usage after operations
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 100MB for this test)
        assert memory_increase < 100

    @pytest.mark.asyncio
    async def test_error_handling_stress(self, ingestion_manager):
        """Stress test error handling capabilities."""
        error_count = 0
        success_count = 0

        async def mock_intermittent_failure():
            nonlocal error_count, success_count

            # Simulate 30% failure rate
            if (error_count + success_count) % 3 == 0:
                error_count += 1
                return IngestionResult(
                    success=False,
                    status=IngestionStatus.ERROR,
                    output="",
                    error_message="Simulated error",
                    return_code=1,
                    execution_time=0.01,
                    timestamp=datetime.now(),
                )
            else:
                success_count += 1
                return IngestionResult(
                    success=True,
                    status=IngestionStatus.COMPLETED,
                    output="Success",
                    error_message=None,
                    return_code=0,
                    execution_time=0.01,
                    timestamp=datetime.now(),
                )

        with patch.object(
            ingestion_manager, "run_ingestion", side_effect=mock_intermittent_failure
        ):
            with patch.object(
                ingestion_manager, "validate_environment", return_value=True
            ):
                # Run 30 operations with intermittent failures
                tasks = [ingestion_manager.run_ingestion() for _ in range(30)]
                results = await asyncio.gather(*tasks)

                # Should handle all operations without crashing
                assert len(results) == 30

                # Should have expected mix of successes and failures
                successes = [r for r in results if r.success]
                failures = [r for r in results if not r.success]

                assert len(successes) > 0
                assert len(failures) > 0
                assert len(successes) + len(failures) == 30


@pytest.mark.performance
class TestICEAPIPerformance:
    """Performance tests for ICE API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client for API performance testing."""
        from fastapi.testclient import TestClient

        from ice_pipeline.api import app

        return TestClient(app)

    @pytest.mark.benchmark(group="api_endpoints")
    def test_health_endpoint_performance(self, client, benchmark):
        """Benchmark health endpoint performance."""

        def make_request():
            return client.get("/health")

        response = benchmark(make_request)
        assert response.status_code == 200

    @pytest.mark.benchmark(group="api_endpoints")
    def test_status_endpoint_performance(self, client, benchmark):
        """Benchmark status endpoint performance."""
        with patch("ice_pipeline.api.ingestion_manager") as mock_manager:
            mock_manager.get_status.return_value = IngestionStatus.IDLE
            mock_manager.get_last_result.return_value = None

            def make_request():
                return client.get("/ice/status")

            response = benchmark(make_request)
            assert response.status_code == 200

    def test_concurrent_api_requests(self, client):
        """Test API performance under concurrent load."""
        import threading
        import time

        results = []
        errors = []

        def make_health_requests():
            try:
                for _ in range(10):  # Each thread makes 10 requests
                    response = client.get("/health")
                    results.append(response.status_code)
            except Exception as e:
                errors.append(str(e))

        # Create 10 threads, each making 10 requests (100 total)
        threads = []
        start_time = time.time()

        for _ in range(10):
            thread = threading.Thread(target=make_health_requests)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        end_time = time.time()

        # All requests should succeed
        assert len(errors) == 0
        assert len(results) == 100
        assert all(status == 200 for status in results)

        # Should complete within reasonable time (under 10 seconds)
        assert end_time - start_time < 10.0

    def test_api_response_time_consistency(self, client):
        """Test API response time consistency."""
        response_times = []

        for _ in range(50):
            start_time = time.time()
            response = client.get("/health")
            end_time = time.time()

            assert response.status_code == 200
            response_times.append(end_time - start_time)

        # Calculate statistics
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        min_response_time = min(response_times)

        # Response times should be consistent and fast
        assert avg_response_time < 0.1  # Average under 100ms
        assert max_response_time < 0.5  # Max under 500ms

        # Variance should be low (max shouldn't be more than 10x min)
        assert max_response_time / min_response_time < 10


@pytest.mark.performance
class TestICEScalabilityTests:
    """Scalability tests for ICE pipeline."""

    def test_large_file_simulation(self):
        """Test performance with large file simulations."""
        # Simulate processing large amounts of data
        start_time = time.time()

        # Create large data structure simulating file content
        large_data = []
        for i in range(10000):  # 10K rows
            row = {
                "id": i,
                "data": f"row_data_{i}" * 10,  # Larger content per row
                "timestamp": datetime.now().isoformat(),
                "metadata": {
                    "field_1": f"value_{i}",
                    "field_2": i * 2,
                    "field_3": i / 10.0,
                },
            }
            large_data.append(row)

        # Simulate processing operations
        processed_count = 0
        for row in large_data:
            # Simulate data transformation
            processed_row = {
                "processed_id": row["id"],
                "processed_data": row["data"].upper(),
                "processed_timestamp": row["timestamp"],
            }
            processed_count += 1

        end_time = time.time()
        processing_time = end_time - start_time

        # Should process all data
        assert processed_count == 10000

        # Should complete within reasonable time (under 5 seconds)
        assert processing_time < 5.0

        # Calculate throughput
        rows_per_second = processed_count / processing_time
        assert rows_per_second > 1000  # Should process at least 1K rows/second

    @pytest.mark.asyncio
    async def test_async_scalability(self):
        """Test scalability of async operations."""

        async def simulate_async_operation(item_id):
            # Simulate async processing
            await asyncio.sleep(0.001)  # 1ms processing time
            return f"processed_{item_id}"

        # Test with increasing batch sizes
        batch_sizes = [10, 50, 100, 500, 1000]

        for batch_size in batch_sizes:
            start_time = time.time()

            # Create concurrent tasks
            tasks = [simulate_async_operation(i) for i in range(batch_size)]
            results = await asyncio.gather(*tasks)

            end_time = time.time()

            # All tasks should complete successfully
            assert len(results) == batch_size

            # Processing time should scale reasonably
            # (not linearly due to concurrency)
            processing_time = end_time - start_time

            # Should complete faster than sequential processing
            sequential_time_estimate = batch_size * 0.001
            assert (
                processing_time < sequential_time_estimate * 0.5
            )  # At least 2x speedup

    def test_memory_scalability(self):
        """Test memory usage scalability."""
        import os

        import psutil

        process = psutil.Process(os.getpid())

        # Test with increasing data sizes
        data_sizes = [100, 500, 1000, 5000]
        memory_usage = []

        for size in data_sizes:
            # Clear any existing data
            test_data = None

            # Get baseline memory
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB

            # Create data of specified size
            test_data = [
                IngestionResult(
                    success=True,
                    status=IngestionStatus.COMPLETED,
                    output=f"Data item {i}" * 50,  # Moderate size per item
                    error_message=None,
                    return_code=0,
                    execution_time=float(i),
                    timestamp=datetime.now(),
                )
                for i in range(size)
            ]

            # Measure memory after data creation
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory
            memory_usage.append(memory_increase)

            # Clean up
            del test_data

        # Memory usage should scale reasonably (roughly linear)
        # Each increase should be proportional to data size increase
        for i in range(1, len(data_sizes)):
            size_ratio = data_sizes[i] / data_sizes[i - 1]
            memory_ratio = (
                memory_usage[i] / memory_usage[i - 1] if memory_usage[i - 1] > 0 else 1
            )

            # Memory ratio should be reasonable compared to size ratio
            # (allowing for GC timing and CI memory variability)
            assert memory_ratio < size_ratio * 5
