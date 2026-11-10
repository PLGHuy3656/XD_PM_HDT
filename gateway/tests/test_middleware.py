"""Unit tests for Correlation ID middleware."""
import uuid
from fastapi.testclient import TestClient


def test_generates_new_correlation_id_when_missing(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    cid = response.headers.get("X-Correlation-ID")
    assert cid is not None
    # Validate it's a valid UUID
    parsed = uuid.UUID(cid)
    assert str(parsed) == cid


def test_preserves_existing_x_correlation_id(client: TestClient):
    custom_cid = "swc-trace-9876543210"
    response = client.get("/health", headers={"X-Correlation-ID": custom_cid})
    assert response.status_code == 200
    assert response.headers.get("X-Correlation-ID") == custom_cid


def test_maps_x_request_id_to_x_correlation_id(client: TestClient):
    req_id = "req-custom-alpha-001"
    response = client.get("/health", headers={"X-Request-ID": req_id})
    assert response.status_code == 200
    assert response.headers.get("X-Correlation-ID") == req_id
