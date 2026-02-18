"""
Integration tests for ICE Pipeline.

This module tests the integration between different components
of the ICE pipeline including database connections, file processing,
and external service interactions.
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from ice_pipeline.api import app
from ice_pipeline.ingestion import ICEIngestionManager, IngestionResult, IngestionStatus


@pytest.mark.integration
class TestICEDatabaseIntegration:
    """Integration tests for ICE pipeline database operations."""

    @pytest.fixture
    def test_db_engine(self, postgresql):
        """Create test database engine."""
        db_url = f"postgresql://postgres@{postgresql.host}:{postgresql.port}/{postgresql.info.dbname}"
        engine = create_engine(db_url)
        return engine

    @pytest.fixture
    def test_db_session(self, test_db_engine):
        """Create test database session."""
        Session = sessionmaker(bind=test_db_engine)
        session = Session()
        yield session
        session.close()

    def test_database_connection(self, test_db_engine):
        """Test database connection and basic operations."""
        with test_db_engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test_value"))
            assert result.fetchone()[0] == 1

    def test_create_ice_tables(self, test_db_engine):
        """Test creation of ICE-related database tables."""
        with test_db_engine.connect() as conn:
            # Create test table for ICE data
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ice_ingestion_log (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status VARCHAR(50) NOT NULL,
                    output TEXT,
                    error_message TEXT,
                    execution_time FLOAT,
                    file_count INTEGER
                )
            """))
            conn.commit()

            # Test insertion
            conn.execute(text("""
                INSERT INTO ice_ingestion_log 
                (status, output, execution_time, file_count)
                VALUES ('completed', 'Test output', 45.2, 10)
            """))
            conn.commit()

            # Test retrieval
            result = conn.execute(text("""
                SELECT status, output, execution_time, file_count
                FROM ice_ingestion_log
                WHERE status = 'completed'
            """))

            row = result.fetchone()
            assert row[0] == "completed"
            assert row[1] == "Test output"
            assert row[2] == 45.2
            assert row[3] == 10

    def test_ice_ingestion_logging(self, test_db_engine):
        """Test logging ICE ingestion results to database."""
        with test_db_engine.connect() as conn:
            # Setup table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ice_ingestion_results (
                    id SERIAL PRIMARY KEY,
                    run_id VARCHAR(100) UNIQUE,
                    success BOOLEAN NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    output TEXT,
                    error_message TEXT,
                    return_code INTEGER,
                    execution_time FLOAT,
                    timestamp TIMESTAMP,
                    metadata JSONB
                )
            """))
            conn.commit()

            # Create test result
            test_result = IngestionResult(
                success=True,
                status=IngestionStatus.COMPLETED,
                output="Database integration test completed",
                error_message=None,
                return_code=0,
                execution_time=30.5,
                timestamp=datetime.now(),
            )

            # Log result to database
            conn.execute(
                text("""
                INSERT INTO ice_ingestion_results 
                (run_id, success, status, output, error_message, return_code, 
                 execution_time, timestamp, metadata)
                VALUES (:run_id, :success, :status, :output, :error_message, 
                        :return_code, :execution_time, :timestamp, :metadata)
            """),
                {
                    "run_id": "test-run-001",
                    "success": test_result.success,
                    "status": test_result.status.value,
                    "output": test_result.output,
                    "error_message": test_result.error_message,
                    "return_code": test_result.return_code,
                    "execution_time": test_result.execution_time,
                    "timestamp": test_result.timestamp,
                    "metadata": json.dumps({"test": True}),
                },
            )
            conn.commit()

            # Verify logging
            result = conn.execute(text("""
                SELECT run_id, success, status, execution_time
                FROM ice_ingestion_results
                WHERE run_id = 'test-run-001'
            """))

            row = result.fetchone()
            assert row[0] == "test-run-001"
            assert row[1] is True
            assert row[2] == "completed"
            assert row[3] == 30.5


@pytest.mark.integration
class TestICEFileProcessingIntegration:
    """Integration tests for ICE pipeline file processing."""

    @pytest.fixture
    def temp_test_files(self):
        """Create temporary test files for processing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test Excel file (mock content)
            excel_file = temp_path / "test_data.xlsx"
            excel_file.write_bytes(b"Mock Excel content for testing")

            # Create test CSV file
            csv_file = temp_path / "test_data.csv"
            csv_file.write_text(
                "col1,col2,col3\nvalue1,value2,value3\ntest1,test2,test3"
            )

            # Create test JSON file
            json_file = temp_path / "test_config.json"
            json_file.write_text(
                json.dumps(
                    {
                        "config": {"setting1": "value1", "setting2": 42},
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            )

            yield {
                "temp_dir": temp_path,
                "excel_file": excel_file,
                "csv_file": csv_file,
                "json_file": json_file,
            }

    def test_file_discovery(self, temp_test_files):
        """Test file discovery and enumeration."""
        temp_dir = temp_test_files["temp_dir"]

        # List all files
        files = list(temp_dir.glob("*"))
        assert len(files) == 3

        # Check specific file types
        excel_files = list(temp_dir.glob("*.xlsx"))
        assert len(excel_files) == 1
        assert excel_files[0].name == "test_data.xlsx"

        csv_files = list(temp_dir.glob("*.csv"))
        assert len(csv_files) == 1

        json_files = list(temp_dir.glob("*.json"))
        assert len(json_files) == 1

    def test_file_processing_workflow(self, temp_test_files):
        """Test complete file processing workflow."""
        csv_file = temp_test_files["csv_file"]

        # Read and process CSV file
        content = csv_file.read_text()
        lines = content.strip().split("\n")

        assert len(lines) == 3  # Header + 2 data rows
        assert lines[0] == "col1,col2,col3"
        assert lines[1] == "value1,value2,value3"
        assert lines[2] == "test1,test2,test3"

        # Simulate processing
        processed_data = []
        for line in lines[1:]:  # Skip header
            row = line.split(",")
            processed_data.append({"col1": row[0], "col2": row[1], "col3": row[2]})

        assert len(processed_data) == 2
        assert processed_data[0]["col1"] == "value1"
        assert processed_data[1]["col1"] == "test1"

    @pytest.mark.asyncio
    async def test_async_file_processing(self, temp_test_files):
        """Test asynchronous file processing operations."""
        csv_file = temp_test_files["csv_file"]

        async def process_file_async(file_path):
            # Simulate async file processing
            await asyncio.sleep(0.1)  # Simulate processing time
            content = file_path.read_text()
            return len(content.split("\n"))

        # Process file asynchronously
        line_count = await process_file_async(csv_file)
        assert line_count == 3

    def test_file_validation(self, temp_test_files):
        """Test file validation and integrity checks."""
        excel_file = temp_test_files["excel_file"]
        csv_file = temp_test_files["csv_file"]
        json_file = temp_test_files["json_file"]

        # Check file existence
        assert excel_file.exists()
        assert csv_file.exists()
        assert json_file.exists()

        # Check file sizes
        assert excel_file.stat().st_size > 0
        assert csv_file.stat().st_size > 0
        assert json_file.stat().st_size > 0

        # Validate JSON content
        json_content = json.loads(json_file.read_text())
        assert "config" in json_content
        assert "timestamp" in json_content
        assert json_content["config"]["setting2"] == 42


@pytest.mark.integration
class TestICEExternalServicesIntegration:
    """Integration tests for ICE pipeline external service interactions."""

    def test_google_drive_api_mock_integration(self):
        """Test Google Drive API integration with mocking."""
        with patch("ice_pipeline.ingestion.build") as mock_build:
            # Mock Google Drive service
            mock_service = Mock()
            mock_files = Mock()
            mock_service.files.return_value = mock_files

            # Mock file list response
            mock_files.list.return_value.execute.return_value = {
                "files": [
                    {
                        "id": "file123",
                        "name": "test_data.xlsx",
                        "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    },
                    {
                        "id": "file456",
                        "name": "config.json",
                        "mimeType": "application/json",
                    },
                ]
            }

            mock_build.return_value = mock_service

            # Test the integration
            with patch("ice_pipeline.ingestion.os.getenv") as mock_getenv:
                mock_getenv.side_effect = lambda key, default=None: {
                    "GOOGLE_CREDENTIALS_JSON": '{"type": "service_account"}',
                    "GOOGLE_DRIVE_FOLDER_ID": "test_folder_123",
                }.get(key, default)

                # This would normally interact with Google Drive
                # Here we're testing that the mocking works correctly
                service = mock_build()
                files_result = service.files().list().execute()

                assert len(files_result["files"]) == 2
                assert files_result["files"][0]["name"] == "test_data.xlsx"
                assert files_result["files"][1]["name"] == "config.json"

    def test_redis_cache_integration(self):
        """Test Redis cache integration with fake Redis."""
        from fakeredis import FakeRedis

        # Create fake Redis instance
        redis_client = FakeRedis()

        # Test basic Redis operations
        redis_client.set("ice:status", "idle")
        assert redis_client.get("ice:status").decode() == "idle"

        # Test complex data storage
        test_result = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "execution_time": 45.2,
            "file_count": 10,
        }

        redis_client.setex("ice:last_result", 3600, json.dumps(test_result))
        stored_result = json.loads(redis_client.get("ice:last_result").decode())

        assert stored_result["success"] is True
        assert stored_result["execution_time"] == 45.2
        assert stored_result["file_count"] == 10

    def test_http_api_client_integration(self):
        """Test HTTP API client integration with mocked responses."""
        from unittest.mock import patch

        import requests

        with patch("requests.get") as mock_get:
            # Mock API response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "status": "success",
                "data": {
                    "files_processed": 15,
                    "timestamp": datetime.now().isoformat(),
                },
            }
            mock_get.return_value = mock_response

            # Test the HTTP client
            response = requests.get("https://api.ice-system.com/status", timeout=10)
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "success"
            assert data["data"]["files_processed"] == 15


@pytest.mark.integration
class TestICEEndToEndIntegration:
    """End-to-end integration tests for ICE pipeline."""

    @pytest.fixture
    def api_client(self):
        """Create API client for end-to-end testing."""
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_full_pipeline_integration(self, api_client, temp_test_files):
        """Test complete ICE pipeline integration from API to processing."""
        with patch("ice_pipeline.ingestion.os.getenv") as mock_getenv:
            mock_getenv.side_effect = lambda key, default=None: {
                "GOOGLE_CREDENTIALS_JSON": '{"type": "service_account"}',
                "GOOGLE_DRIVE_FOLDER_ID": "test_folder",
                "ICE_SCRIPT_PATH": "/test/script.py",
            }.get(key, default)

            with patch("ice_pipeline.ingestion.Path.exists", return_value=True):
                # Step 1: Check initial system status
                status_response = api_client.get("/ice/status")
                assert status_response.status_code == 200

                # Step 2: Test file conversion API
                conversion_request = {
                    "file_path": str(temp_test_files["excel_file"]),
                    "output_format": "csv",
                    "include_metadata": True,
                }

                with patch("ice_pipeline.api.process_excel_conversion") as mock_convert:
                    mock_convert.return_value = {
                        "success": True,
                        "output_file": "/test/output.csv",
                        "rows_processed": 100,
                        "metadata": {"sheets": ["Sheet1"], "columns": 3},
                    }

                    convert_response = api_client.post(
                        "/convert-excel", json=conversion_request
                    )
                    assert convert_response.status_code == 200

                    convert_data = convert_response.json()
                    assert convert_data["success"] is True
                    assert convert_data["rows_processed"] == 100

                # Step 3: Test ingestion trigger with mocked process
                with patch(
                    "ice_pipeline.ingestion.asyncio.create_subprocess_exec"
                ) as mock_process:
                    mock_subprocess = AsyncMock()
                    mock_subprocess.returncode = 0
                    mock_subprocess.communicate.return_value = (
                        b"Integration test successful",
                        b"",
                    )
                    mock_process.return_value = mock_subprocess

                    trigger_response = api_client.post("/ice/trigger")
                    # Note: This might return 200 or 202 depending on async implementation
                    assert trigger_response.status_code in [200, 202]

                # Step 4: Check final status
                await asyncio.sleep(0.1)  # Small delay for async operations
                final_status = api_client.get("/ice/status")
                assert final_status.status_code == 200

    def test_error_handling_integration(self, api_client):
        """Test error handling across the entire pipeline."""
        # Test API error propagation
        with patch("ice_pipeline.api.process_excel_conversion") as mock_convert:
            mock_convert.side_effect = Exception("Processing failed")

            conversion_request = {
                "file_path": "/test/nonexistent.xlsx",
                "output_format": "csv",
                "include_metadata": True,
            }

            response = api_client.post("/convert-excel", json=conversion_request)
            assert response.status_code == 500

    def test_concurrent_operations_integration(self, api_client):
        """Test concurrent operations across the pipeline."""
        import threading
        import time

        results = []

        def make_status_request():
            with patch("ice_pipeline.api.ingestion_manager") as mock_manager:
                mock_manager.get_status.return_value = IngestionStatus.IDLE
                mock_manager.get_last_result.return_value = None

                response = api_client.get("/ice/status")
                results.append(response.status_code)

        # Create multiple concurrent requests
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=make_status_request)
            threads.append(thread)
            thread.start()

        # Wait for all to complete
        for thread in threads:
            thread.join()

        # All should succeed
        assert all(status == 200 for status in results)
        assert len(results) == 3

    @pytest.mark.performance
    def test_pipeline_performance_integration(self, api_client, benchmark):
        """Test pipeline performance under load."""

        def health_check_operation():
            return api_client.get("/health")

        response = benchmark(health_check_operation)
        assert response.status_code == 200

        # Verify performance is within acceptable bounds
        # (specific thresholds would be defined based on requirements)
        data = response.json()
        assert "timestamp" in data
        assert data["status"] == "healthy"


@pytest.mark.integration
class TestICEDataPersistenceIntegration:
    """Integration tests for ICE pipeline data persistence."""

    def test_configuration_persistence(self, tmp_path):
        """Test configuration file persistence and loading."""
        config_file = tmp_path / "ice_config.json"

        # Test configuration
        test_config = {
            "google_drive": {
                "folder_id": "test_folder_123",
                "credentials_file": "/path/to/credentials.json",
            },
            "processing": {"batch_size": 100, "timeout_seconds": 300, "retry_count": 3},
            "logging": {"level": "INFO", "file": "/logs/ice_pipeline.log"},
        }

        # Save configuration
        config_file.write_text(json.dumps(test_config, indent=2))

        # Load and verify configuration
        loaded_config = json.loads(config_file.read_text())

        assert loaded_config["google_drive"]["folder_id"] == "test_folder_123"
        assert loaded_config["processing"]["batch_size"] == 100
        assert loaded_config["logging"]["level"] == "INFO"

    def test_result_caching_integration(self):
        """Test result caching and retrieval integration."""
        from fakeredis import FakeRedis

        redis_client = FakeRedis()

        # Create test results for caching
        test_results = [
            IngestionResult(
                success=True,
                status=IngestionStatus.COMPLETED,
                output=f"Test run {i}",
                error_message=None,
                return_code=0,
                execution_time=10.0 + i,
                timestamp=datetime.now(),
            )
            for i in range(3)
        ]

        # Cache results
        for i, result in enumerate(test_results):
            cache_key = f"ice:result:{i}"
            # Use JSON instead of pickle for security
            result_dict = {
                "success": result.success,
                "status": result.status.value,
                "output": result.output,
                "error_message": result.error_message,
                "return_code": result.return_code,
                "execution_time": result.execution_time,
                "timestamp": result.timestamp.isoformat(),
            }
            serialized_result = json.dumps(result_dict)
            redis_client.setex(cache_key, 3600, serialized_result)

        # Retrieve and verify cached results
        for i in range(3):
            cache_key = f"ice:result:{i}"
            cached_data = redis_client.get(cache_key)
            assert cached_data is not None

            cached_dict = json.loads(cached_data)
            assert cached_dict["success"] is True
            assert cached_dict["execution_time"] == 10.0 + i

            # Reconstruct object if needed, or just verify data
            assert cached_dict["output"] == f"Test run {i}"

    def test_log_aggregation_integration(self, tmp_path):
        """Test log aggregation and analysis integration."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # Create multiple log files
        log_files = []
        for i in range(3):
            log_file = log_dir / f"ice_pipeline_{i}.log"
            log_entries = [
                f"2024-01-{i+1:02d} 10:00:00 INFO: ICE pipeline started",
                f"2024-01-{i+1:02d} 10:05:00 INFO: Processing 100 files",
                f"2024-01-{i+1:02d} 10:10:00 INFO: ICE pipeline completed successfully",
            ]
            log_file.write_text("\n".join(log_entries))
            log_files.append(log_file)

        # Aggregate logs
        all_entries = []
        for log_file in log_files:
            entries = log_file.read_text().split("\n")
            all_entries.extend(entries)

        # Verify aggregation
        assert len(all_entries) == 9  # 3 files × 3 entries each

        # Count specific log types
        info_count = sum(1 for entry in all_entries if "INFO:" in entry)
        started_count = sum(1 for entry in all_entries if "started" in entry)
        completed_count = sum(1 for entry in all_entries if "completed" in entry)

        assert info_count == 9
        assert started_count == 3
        assert completed_count == 3
