"""Prometheus metrics contract tests for API Gateway (CP10-B2)."""
from fastapi.testclient import TestClient

from app.main import create_gateway_app


def test_gateway_metrics_endpoint_contract():
    """Verify /metrics returns HTTP 200, emits verified metrics, and excludes /metrics and /health."""
    app_instance = create_gateway_app()
    client = TestClient(app_instance)

    # Trigger health check (excluded) and an unmapped route (404, handler="none")
    res_health = client.get("/health")
    assert res_health.status_code == 200

    res_404 = client.get("/api/unmapped-metrics-test")
    assert res_404.status_code == 404

    # Scrape /metrics
    metrics_res = client.get("/metrics")
    assert metrics_res.status_code == 200
    assert "text/plain" in metrics_res.headers.get("content-type", "")

    body = metrics_res.text
    assert "http_requests_total" in body
    assert "http_request_duration_highr_seconds_bucket" in body
    assert 'handler="none"' in body
    assert 'status="404"' in body

    for line in body.splitlines():
        if line.startswith("http_requests_total{"):
            assert 'handler="/metrics"' not in line
            assert 'handler="/health"' not in line
