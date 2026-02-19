"""
End-to-end tests for the ICE Pipeline.

These tests verify the full request lifecycle through the FastAPI application,
exercising the interaction between API endpoints and the IngestionManager
with mocked external dependencies (Google Drive, subprocess scripts).
"""

import pytest

from ice_pipeline.ingestion import IngestionStatus


# ──────────────────────────────────────────────
# 1. Health & Status baseline
# ──────────────────────────────────────────────


class TestHealthAndStatus:
    """Smoke tests that verify basic API availability."""

    def test_health_endpoint_returns_healthy(self, patched_client):
        client, _ = patched_client
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"

    def test_status_endpoint_idle_before_trigger(self, patched_client):
        client, _ = patched_client
        resp = client.get("/ice/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == IngestionStatus.IDLE.value
        assert body["last_result"] is None


# ──────────────────────────────────────────────
# 2. Full ingestion workflow (happy path)
# ──────────────────────────────────────────────


class TestFullIngestionWorkflow:
    """
    Verify the complete lifecycle:
      POST /ice/trigger  →  background execution  →  GET /ice/status  →  completed
    """

    def test_trigger_returns_success(self, patched_client):
        """Trigger should return 200 with status 'triggered'."""
        client, _ = patched_client
        resp = client.post("/ice/trigger")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["status"] == "triggered"

    def test_status_after_trigger_is_completed(self, patched_client):
        """
        After trigger + background execution (synchronous in TestClient),
        status should be completed with a successful last_result.
        """
        client, _ = patched_client

        # Trigger
        resp = client.post("/ice/trigger")
        assert resp.status_code == 200

        # Check status — background task already ran in TestClient
        resp = client.get("/ice/status")
        assert resp.status_code == 200
        body = resp.json()
        assert (
            body["status"] == IngestionStatus.IDLE.value
        )  # returns to idle after completion

        # Verify last_result
        result = body["last_result"]
        assert result is not None
        assert result["success"] is True
        assert result["status"] == IngestionStatus.COMPLETED.value
        assert result["return_code"] == 0
        assert result["execution_time"] > 0
        # Dummy script outputs JSON with processed_files: 2
        assert "processed_files" in result["output"]

    def test_trigger_then_cleanup(self, patched_client):
        """Trigger ingestion, then verify cleanup endpoint works."""
        client, _ = patched_client

        # Trigger ingestion first
        resp = client.post("/ice/trigger")
        assert resp.status_code == 200

        # Now clean up
        resp = client.post("/ice/cleanup")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body


# ──────────────────────────────────────────────
# 3. Error handling
# ──────────────────────────────────────────────


class TestErrorHandling:
    """Verify the system handles failures gracefully."""

    def test_failed_ingestion_script(self, patched_client_failing):
        """
        When the ingestion script exits with code 1,
        the status should report an error.
        """
        client, _ = patched_client_failing

        # Trigger
        resp = client.post("/ice/trigger")
        assert resp.status_code == 200

        # Check status
        resp = client.get("/ice/status")
        assert resp.status_code == 200
        body = resp.json()

        result = body["last_result"]
        assert result is not None
        assert result["success"] is False
        assert result["status"] == IngestionStatus.ERROR.value
        assert result["return_code"] != 0
        assert result["error_message"] is not None
        assert "Google Drive API connection failed" in result["error_message"]

    def test_missing_credentials_causes_validation_error(self, patched_client_no_creds):
        """
        When GOOGLE_CREDENTIALS_JSON is missing,
        validate_environment() fails and ingestion returns an error.
        """
        client, _ = patched_client_no_creds

        # Trigger
        resp = client.post("/ice/trigger")
        assert resp.status_code == 200

        # Check status
        resp = client.get("/ice/status")
        assert resp.status_code == 200
        body = resp.json()

        result = body["last_result"]
        assert result is not None
        assert result["success"] is False
        assert "Environment validation failed" in result["error_message"]


# ──────────────────────────────────────────────
# 4. Concurrency protection
# ──────────────────────────────────────────────


class TestConcurrencyProtection:
    """Verify that only one ingestion can run at a time."""

    def test_duplicate_trigger_returns_409(self, patched_client):
        """
        If the manager status is RUNNING, a second trigger should get 409.

        Note: In TestClient, background tasks run synchronously,
        so we manually set the manager status to RUNNING to simulate
        a concurrent request.
        """
        client, manager = patched_client

        # Simulate a running ingestion
        manager.status = IngestionStatus.RUNNING

        # Second trigger should be rejected
        resp = client.post("/ice/trigger")
        assert resp.status_code == 409
        assert "already running" in resp.json()["detail"].lower()

        # Reset for cleanliness
        manager.status = IngestionStatus.IDLE


# ──────────────────────────────────────────────
# 5. API validation
# ──────────────────────────────────────────────


class TestAPIValidation:
    """Verify API input validation on conversion endpoint."""

    def test_convert_excel_invalid_extension(self, patched_client):
        """Submitting a non-Excel file extension returns 422."""
        client, _ = patched_client
        resp = client.post(
            "/convert-excel",
            json={"file_path": "/test/file.txt", "output_format": "csv"},
        )
        assert resp.status_code == 422

    def test_convert_excel_invalid_format(self, patched_client):
        """Submitting an invalid output format returns 422."""
        client, _ = patched_client
        resp = client.post(
            "/convert-excel",
            json={"file_path": "/test/file.xlsx", "output_format": "xml"},
        )
        assert resp.status_code == 422

    def test_convert_excel_empty_path(self, patched_client):
        """Submitting an empty file_path returns 422."""
        client, _ = patched_client
        resp = client.post("/convert-excel", json={"file_path": ""})
        assert resp.status_code == 422


# ──────────────────────────────────────────────
# 6. Full lifecycle integration
# ──────────────────────────────────────────────


class TestFullLifecycle:
    """Verify a complete lifecycle: health → trigger → status → cleanup."""

    def test_complete_lifecycle(self, patched_client):
        """Run through the entire API in order."""
        client, _ = patched_client

        # 1. Health check
        resp = client.get("/health")
        assert resp.status_code == 200

        # 2. Initial status is idle
        resp = client.get("/ice/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == IngestionStatus.IDLE.value

        # 3. Trigger ingestion
        resp = client.post("/ice/trigger")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # 4. Status after completion
        resp = client.get("/ice/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["last_result"] is not None
        assert body["last_result"]["success"] is True

        # 5. Cleanup
        resp = client.post("/ice/cleanup")
        assert resp.status_code == 200

        # 6. Health still good
        resp = client.get("/health")
        assert resp.status_code == 200
