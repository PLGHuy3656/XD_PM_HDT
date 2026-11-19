"""
Metrics contract and non-regression tests for Analytics Service (CP10-B2).
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_metrics_endpoint_exposes_prometheus_contract():
    """Verify /metrics returns 200 and emits expected Prometheus metrics after API traffic."""
    # Trigger a normal 200 API request and a 404 request
    res_ok = client.get("/api/v1/analytics/farms/farm-binh-an/summary?period=today")
    assert res_ok.status_code == 200

    res_404 = client.get("/api/v1/analytics/unmapped-path")
    assert res_404.status_code == 404

    # Trigger excluded handlers
    res_health = client.get("/health")
    assert res_health.status_code == 200

    # Scrape /metrics
    metrics_res = client.get("/metrics")
    assert metrics_res.status_code == 200
    assert "text/plain" in metrics_res.headers.get("content-type", "")

    body = metrics_res.text
    assert "http_requests_total" in body
    assert "http_request_duration_highr_seconds_bucket" in body
    assert 'handler="/api/v1/analytics/farms/{farm_id}/summary"' in body
    assert 'handler="none"' in body
    assert 'status="200"' in body
    assert 'status="404"' in body

    # Verify excluded_handlers are not recorded in http_requests_total
    for line in body.splitlines():
        if line.startswith("http_requests_total{"):
            assert 'handler="/metrics"' not in line
            assert 'handler="/health"' not in line
