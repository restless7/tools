"""
Enterprise Test Configuration - conftest.py
==========================================

Centralized pytest configuration and fixtures for enterprise-level testing.
This module provides reusable fixtures, test utilities, and configuration
that can be shared across all test modules in the testing suite.

Features:
- Centralized fixture management
- Database test fixtures
- Mocking utilities
- Test data factories
- Performance monitoring
- Enterprise logging
"""

import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, Optional
from unittest.mock import Mock, patch

# Import testing utilities
import pandas as pd
import pytest
from faker import Faker
from pytest_postgresql import factories

# Import project modules
# Note: These imports should be adjusted based on your actual project structure
# from ice_pipeline.config import Config
# from ice_pipeline.database import DatabaseManager
# from ice_pipeline.logger import Logger


# =============================================================================
# Test Configuration
# =============================================================================


@dataclass
class TestConfig:
    """Enterprise test configuration."""

    test_db_url: str = "postgresql://test_user:test_pass@localhost:5432/ice_test"
    redis_url: str = "redis://localhost:6379/0"
    google_drive_mock: bool = True
    enable_performance_monitoring: bool = True
    test_data_dir: str = "tests/fixtures/data"
    reports_dir: str = "reports"
    log_level: str = "DEBUG"


# Global test configuration
TEST_CONFIG = TestConfig()


# =============================================================================
# Database Fixtures
# =============================================================================

# PostgreSQL test database factory
postgresql_proc = factories.postgresql_proc(port=None, unixsocketdir=tempfile.gettempdir())
postgresql = factories.postgresql("postgresql_proc")


@pytest.fixture(scope="session")
def test_database_url():
    """Provide test database URL for the session."""
    return TEST_CONFIG.test_db_url


@pytest.fixture
def db_connection(postgresql):
    """Provide database connection for tests."""
    # This would be replaced with your actual database manager
    # return DatabaseManager(connection_string=postgresql.info.dsn)
    return postgresql


@pytest.fixture
def clean_database(db_connection):
    """Provide a clean database for each test."""
    # Clean all tables before test
    yield db_connection
    # Clean all tables after test
    # This should be implemented based on your database schema


# =============================================================================
# File System Fixtures
# =============================================================================


@pytest.fixture
def temp_dir():
    """Provide temporary directory for test file operations."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def test_data_dir():
    """Provide test data directory."""
    data_dir = Path(__file__).parent / "fixtures" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture
def sample_csv_file(temp_dir):
    """Create a sample CSV file for testing."""
    csv_path = temp_dir / "sample.csv"

    # Generate sample data
    fake = Faker()
    data = []

    for _ in range(100):
        data.append(
            {
                "id": fake.unique.random_int(min=1, max=10000),
                "name": fake.name(),
                "email": fake.email(),
                "phone": fake.phone_number(),
                "address": fake.address().replace("\n", ", "),
                "birthdate": fake.date_of_birth(),
                "program_type": fake.random_element(["WAT", "H2B", "J1", "F1"]),
                "application_date": fake.date_this_year(),
                "status": fake.random_element(["pending", "approved", "rejected"]),
                "amount": fake.random_int(min=1000, max=50000),
            }
        )

    df = pd.DataFrame(data)
    df.to_csv(csv_path, index=False)

    return csv_path


@pytest.fixture
def sample_excel_file(temp_dir):
    """Create a sample Excel file for testing."""
    excel_path = temp_dir / "sample.xlsx"

    # Generate sample data
    fake = Faker()
    data = []

    for _ in range(50):
        data.append(
            {
                "Student_ID": fake.unique.random_int(min=1, max=10000),
                "Full_Name": fake.name(),
                "Email_Address": fake.email(),
                "Phone_Number": fake.phone_number(),
                "Program": fake.random_element(
                    ["Work and Travel", "H2B", "J1 Intern", "F1 Student"]
                ),
                "Start_Date": fake.date_this_year(),
                "End_Date": fake.date_this_year(),
                "Sponsor": fake.company(),
                "Fee_Amount": fake.random_int(min=500, max=5000),
            }
        )

    df = pd.DataFrame(data)
    df.to_excel(excel_path, index=False, sheet_name="Students")

    return excel_path


# =============================================================================
# Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_google_drive():
    """Mock Google Drive service for testing."""
    with patch(
        "ice_pipeline.integrations.google_drive.GoogleDriveService"
    ) as mock_service:
        mock_instance = Mock()
        mock_service.return_value = mock_instance

        # Mock common Google Drive operations
        mock_instance.list_files.return_value = [
            {"id": "file1", "name": "test1.csv", "mimeType": "text/csv"},
            {
                "id": "file2",
                "name": "test2.xlsx",
                "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            },
        ]

        mock_instance.download_file.return_value = b"mock,file,content\n1,test,data"
        mock_instance.upload_file.return_value = {"id": "uploaded_file_id"}

        yield mock_instance


@pytest.fixture
def mock_email_service():
    """Mock email service for testing."""
    with patch("ice_pipeline.notifications.email.EmailService") as mock_service:
        mock_instance = Mock()
        mock_service.return_value = mock_instance

        mock_instance.send_email.return_value = {"status": "sent", "id": "msg_123"}
        mock_instance.send_bulk_email.return_value = {"sent": 5, "failed": 0}

        yield mock_instance


@pytest.fixture
def mock_database():
    """Mock database operations for isolated testing."""
    with patch("ice_pipeline.database.DatabaseManager") as mock_db:
        mock_instance = Mock()
        mock_db.return_value = mock_instance

        # Mock common database operations
        mock_instance.execute_query.return_value = []
        mock_instance.insert_batch.return_value = {"inserted": 10, "errors": 0}
        mock_instance.update_records.return_value = {"updated": 5}
        mock_instance.delete_records.return_value = {"deleted": 3}

        yield mock_instance


# =============================================================================
# Performance and Monitoring Fixtures
# =============================================================================


@pytest.fixture
def performance_monitor():
    """Performance monitoring fixture for test execution."""
    import time

    import psutil

    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.start_memory = None
            self.start_cpu = None

        def start(self):
            self.start_time = time.time()
            self.start_memory = psutil.virtual_memory().used
            self.start_cpu = psutil.cpu_percent()

        def stop(self):
            end_time = time.time()
            end_memory = psutil.virtual_memory().used
            end_cpu = psutil.cpu_percent()

            return {
                "duration": end_time - self.start_time if self.start_time else 0,
                "memory_delta": (
                    end_memory - self.start_memory if self.start_memory else 0
                ),
                "cpu_usage": (self.start_cpu + end_cpu) / 2 if self.start_cpu else 0,
            }

    return PerformanceMonitor()


@pytest.fixture(autouse=True)
def test_performance_logging(request, performance_monitor):
    """Automatically log performance metrics for all tests."""
    if TEST_CONFIG.enable_performance_monitoring:
        performance_monitor.start()
        yield

        metrics = performance_monitor.stop()

        # Log performance metrics
        logger = logging.getLogger("test_performance")
        logger.info(
            f"Test {request.node.name} completed in {metrics['duration']:.3f}s "
            f"(Memory: {metrics['memory_delta'] / 1024 / 1024:.1f}MB, "
            f"CPU: {metrics['cpu_usage']:.1f}%)"
        )
    else:
        yield


# =============================================================================
# Data Generation Fixtures
# =============================================================================


@pytest.fixture
def faker_instance():
    """Provide configured Faker instance for test data generation."""
    fake = Faker(["en_US"])
    Faker.seed(12345)  # For reproducible test data
    return fake


@pytest.fixture
def ice_test_data_generator(faker_instance):
    """Generate ICE-specific test data."""
    from tests.fixtures.test_data import ICETestDataGenerator

    return ICETestDataGenerator(faker=faker_instance)


@pytest.fixture
def sample_student_applications(ice_test_data_generator):
    """Generate sample student application data."""
    return ice_test_data_generator.generate_applications(count=10)


@pytest.fixture
def sample_wat_program_data(ice_test_data_generator):
    """Generate sample Work and Travel program data."""
    return ice_test_data_generator.generate_wat_applications(count=20)


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture
def test_config():
    """Provide test configuration."""
    return TEST_CONFIG


@pytest.fixture
def mock_config():
    """Mock application configuration for testing."""
    config_data = {
        "database": {
            "url": TEST_CONFIG.test_db_url,
            "pool_size": 5,
            "max_overflow": 10,
        },
        "google_drive": {
            "credentials_file": "test_credentials.json",
            "folder_id": "test_folder_id",
        },
        "logging": {
            "level": "DEBUG",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
        "processing": {"batch_size": 100, "max_retries": 3, "timeout": 300},
    }

    with patch("ice_pipeline.config.Config") as mock_config_class:
        mock_instance = Mock()
        mock_config_class.return_value = mock_instance

        # Set up configuration access
        for section, values in config_data.items():
            setattr(mock_instance, section, values)

        yield mock_instance


# =============================================================================
# Logging Fixtures
# =============================================================================


@pytest.fixture
def test_logger():
    """Provide configured test logger."""
    logger = logging.getLogger("ice_pipeline_test")
    logger.setLevel(logging.DEBUG)

    # Add console handler if not already present
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


@pytest.fixture
def capture_logs():
    """Capture log messages during test execution."""
    import io

    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)

    # Add handler to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    yield log_capture

    # Clean up
    root_logger.removeHandler(handler)


# =============================================================================
# API Testing Fixtures
# =============================================================================


@pytest.fixture
def api_client():
    """Provide API test client."""
    from fastapi.testclient import TestClient

    # from ice_pipeline.api.main import app  # Adjust import based on your API structure
    # For now, return a mock client
    # return TestClient(app)
    return Mock()


@pytest.fixture
def authenticated_api_client(api_client):
    """Provide authenticated API client with test token."""
    # Mock authentication
    test_token = "test_jwt_token_12345"
    api_client.headers = {"Authorization": f"Bearer {test_token}"}
    return api_client


# =============================================================================
# Async Testing Support
# =============================================================================


@pytest.fixture
def event_loop():
    """Provide event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_database_session():
    """Provide async database session for async tests."""
    # This would be implemented based on your async database setup
    # For example, with SQLAlchemy async:
    # from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    # engine = create_async_engine(TEST_CONFIG.test_db_url)
    # async with AsyncSession(engine) as session:
    #     yield session

    # For now, return a mock
    yield Mock()


# =============================================================================
# Error Handling and Edge Cases
# =============================================================================


@pytest.fixture
def corrupted_csv_file(temp_dir):
    """Create a corrupted CSV file for error testing."""
    corrupted_path = temp_dir / "corrupted.csv"

    # Write malformed CSV content
    with open(corrupted_path, "w", encoding="utf-8") as f:
        f.write("header1,header2,header3\n")
        f.write("value1,value2\n")  # Missing column
        f.write("value3,value4,value5,value6\n")  # Extra column
        f.write('value7,"unclosed quote,value8\n')  # Unclosed quote

    return corrupted_path


@pytest.fixture
def large_test_file(temp_dir):
    """Create a large test file for performance testing."""
    large_file_path = temp_dir / "large_file.csv"

    # Generate large dataset
    fake = Faker()

    with open(large_file_path, "w", encoding="utf-8") as f:
        # Write header
        f.write("id,name,email,phone,address,program,date,amount\n")

        # Write large number of rows
        for i in range(10000):
            f.write(f"{i},{fake.name()},{fake.email()},{fake.phone_number()},")
            f.write(
                f"{fake.address().replace(',', ';')},{fake.random_element(['WAT', 'H2B'])},"
            )
            f.write(f"{fake.date()},{fake.random_int(1000, 5000)}\n")

    return large_file_path


# =============================================================================
# Enterprise Compliance Fixtures
# =============================================================================


@pytest.fixture
def compliance_checker():
    """Provide compliance checking utilities."""

    class ComplianceChecker:
        @staticmethod
        def check_pii_handling(data):
            """Check if PII data is handled correctly."""
            pii_fields = ["ssn", "social_security", "passport", "license"]
            for field in pii_fields:
                if field in str(data).lower():
                    return {"compliant": False, "reason": f"PII field {field} detected"}
            return {"compliant": True}

        @staticmethod
        def check_data_retention(data, retention_days=365):
            """Check data retention compliance."""
            # This would check if data is older than retention period
            return {"compliant": True, "retention_days": retention_days}

    return ComplianceChecker()


# =============================================================================
# Test Session Hooks
# =============================================================================


@pytest.fixture(scope="session", autouse=True)
def test_session_setup():
    """Set up test session environment."""
    # Create reports directory
    Path(TEST_CONFIG.reports_dir).mkdir(exist_ok=True)

    # Set up test logging
    logging.basicConfig(
        level=getattr(logging, TEST_CONFIG.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Log session start
    logger = logging.getLogger("test_session")
    logger.info(f"Starting test session at {datetime.now()}")

    yield

    # Log session end
    logger.info(f"Test session completed at {datetime.now()}")


def pytest_configure(config):
    """Configure pytest with enterprise settings."""
    # Add custom markers
    config.addinivalue_line("markers", "enterprise: Enterprise-specific tests")
    config.addinivalue_line("markers", "compliance: Compliance validation tests")
    config.addinivalue_line("markers", "pii: Tests involving PII data")

    # Set up test environment variables
    os.environ["TESTING"] = "true"
    os.environ["LOG_LEVEL"] = TEST_CONFIG.log_level


def pytest_sessionstart(session):
    """Called after Session object has been created."""
    print(f"\n🏢 Starting Enterprise Test Suite for ICE Pipeline")
    print(f"📊 Test Configuration: {TEST_CONFIG}")
    print(f"🕒 Session started at: {datetime.now()}")


def pytest_sessionfinish(session, exitstatus):
    """Called after whole test run finished."""
    print(f"\n✅ Enterprise Test Suite completed")
    print(f"🕒 Session finished at: {datetime.now()}")
    print(f"📋 Exit status: {exitstatus}")


def pytest_runtest_setup(item):
    """Called before each test item is executed."""
    # Log test start for performance monitoring
    if hasattr(item, "performance_start_time"):
        item.performance_start_time = datetime.now()


def pytest_runtest_teardown(item, nextitem):
    """Called after each test item is executed."""
    # Log test completion for performance monitoring
    if hasattr(item, "performance_start_time"):
        duration = datetime.now() - item.performance_start_time
        if duration.total_seconds() > 10:  # Log slow tests
            logger = logging.getLogger("slow_tests")
            logger.warning(
                f"Slow test detected: {item.name} took {duration.total_seconds():.2f}s"
            )


# =============================================================================
# Custom Assertions
# =============================================================================


def assert_valid_ice_application(application_data):
    """Custom assertion for validating ICE application data structure."""
    required_fields = [
        "student_id",
        "name",
        "email",
        "program_type",
        "application_date",
    ]

    for field in required_fields:
        assert field in application_data, f"Missing required field: {field}"

    assert application_data["program_type"] in [
        "WAT",
        "H2B",
        "J1",
        "F1",
    ], f"Invalid program type: {application_data['program_type']}"


def assert_performance_within_threshold(duration_seconds, threshold_seconds=30):
    """Custom assertion for performance thresholds."""
    assert (
        duration_seconds <= threshold_seconds
    ), f"Performance test failed: {duration_seconds:.2f}s > {threshold_seconds}s threshold"


def assert_no_pii_exposed(data):
    """Custom assertion to ensure no PII is exposed in logs or outputs."""
    pii_patterns = ["ssn", "social_security", "passport", "driver_license"]
    data_str = str(data).lower()

    for pattern in pii_patterns:
        assert pattern not in data_str, f"PII pattern '{pattern}' found in data: {data}"


# Add custom assertions to pytest namespace
pytest.assert_valid_ice_application = assert_valid_ice_application
pytest.assert_performance_within_threshold = assert_performance_within_threshold
pytest.assert_no_pii_exposed = assert_no_pii_exposed
