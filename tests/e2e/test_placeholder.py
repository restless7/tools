"""Placeholder E2E tests for ICE Pipeline."""
import pytest
from fastapi.testclient import TestClient
from ice_pipeline.api import app

@pytest.fixture
def client():
    return TestClient(app)

def test_e2e_health_check(client):
    """Basic E2E check to ensure the API is reachable."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
