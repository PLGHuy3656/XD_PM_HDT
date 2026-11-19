"""Unit tests for Gateway Health check endpoint."""
from fastapi.testclient import TestClient

from app.config import settings


def test_health_check_returns_ok_and_metadata(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["service"] == "api-gateway"
    assert data["version"] == settings.version
    assert "upstreams" in data

    upstreams = data["upstreams"]
    assert upstreams["management"] == settings.management_service_url
    assert upstreams["iot"] == settings.iot_service_url
    assert upstreams["ai"] == settings.ai_service_url
    assert upstreams["notification"] == settings.notification_service_url
    assert upstreams["analytics"] == settings.analytics_service_url


def test_health_check_includes_correlation_id(client: TestClient):
    response = client.get("/health")
    assert "X-Correlation-ID" in response.headers
    assert len(response.headers["X-Correlation-ID"]) > 10
