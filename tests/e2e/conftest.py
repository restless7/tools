"""
E2E test fixtures for the ICE Pipeline.

These fixtures provide mocked external dependencies (Google Drive, subprocess)
while allowing real application components (FastAPI, IngestionManager) to interact
as they would in production.
"""

import json
import os
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ice_pipeline.api import app
from ice_pipeline.ingestion import ICEIngestionManager


@pytest.fixture
def dummy_ingestion_script():
    """
    Create a temporary Python script that simulates a successful ICE ingestion.

    The script checks env vars, simulates brief processing,
    outputs a JSON result to stdout, and exits 0.
    """
    script_content = """\
import json
import os
import sys
import time

time.sleep(0.2)

creds = os.environ.get("GOOGLE_CREDENTIALS_JSON")
if not creds:
    print("ERROR: Missing GOOGLE_CREDENTIALS_JSON", file=sys.stderr)
    sys.exit(1)

result = {
    "status": "success",
    "processed_files": 2,
    "details": ["student_app_001.pdf", "student_app_002.pdf"],
    "timestamp": "2026-02-19T10:00:00"
}
print(json.dumps(result))
sys.exit(0)
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, prefix="ice_e2e_"
    ) as f:
        f.write(script_content)
        path = f.name

    yield path

    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def failing_ingestion_script():
    """
    Create a temporary Python script that simulates a failed ICE ingestion.
    """
    script_content = """\
import sys

print("ERROR: Google Drive API connection failed", file=sys.stderr)
sys.exit(1)
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, prefix="ice_e2e_fail_"
    ) as f:
        f.write(script_content)
        path = f.name

    yield path

    try:
        os.unlink(path)
    except OSError:
        pass


def _make_env_vars(script_path):
    """Build a dict of environment variable overrides for tests."""
    return {
        "GOOGLE_CREDENTIALS_JSON": json.dumps(
            {"type": "service_account", "project_id": "ice-test"}
        ),
        "GOOGLE_DRIVE_FOLDER_ID": "test_folder_id_e2e",
        "ICE_SCRIPT_PATH": script_path,
        "LOG_LEVEL": "DEBUG",
    }


@pytest.fixture
def patched_client(dummy_ingestion_script):
    """
    Yield a (TestClient, ICEIngestionManager) tuple with env vars
    pointing to the *success* dummy script.

    The os.getenv patch stays active so that validate_environment()
    (called inside run_ingestion) resolves correctly.
    """
    env = _make_env_vars(dummy_ingestion_script)
    with patch(
        "ice_pipeline.ingestion.os.getenv",
        side_effect=lambda key, default=None: env.get(key, default),
    ):
        manager = ICEIngestionManager()
        with patch("ice_pipeline.api.ingestion_manager", manager):
            yield TestClient(app), manager


@pytest.fixture
def patched_client_failing(failing_ingestion_script):
    """
    Yield a (TestClient, ICEIngestionManager) tuple with env vars
    pointing to the *failing* dummy script.
    """
    env = _make_env_vars(failing_ingestion_script)
    with patch(
        "ice_pipeline.ingestion.os.getenv",
        side_effect=lambda key, default=None: env.get(key, default),
    ):
        manager = ICEIngestionManager()
        with patch("ice_pipeline.api.ingestion_manager", manager):
            yield TestClient(app), manager


@pytest.fixture
def patched_client_no_creds(dummy_ingestion_script):
    """
    Yield a (TestClient, ICEIngestionManager) tuple where
    GOOGLE_CREDENTIALS_JSON is missing, causing validation failure.
    """
    env = _make_env_vars(dummy_ingestion_script)
    env.pop("GOOGLE_CREDENTIALS_JSON")  # Remove credentials
    with patch(
        "ice_pipeline.ingestion.os.getenv",
        side_effect=lambda key, default=None: env.get(key, default),
    ):
        manager = ICEIngestionManager()
        with patch("ice_pipeline.api.ingestion_manager", manager):
            yield TestClient(app), manager
