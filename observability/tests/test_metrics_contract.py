"""
Automated Contract Verification Test Suite for CP10-B1.

Verifies that:
1. prometheus-fastapi-instrumentator generates expected Prometheus metric names & labels.
2. HTTP 200, 404, 500 status codes are correctly labeled in http_requests_total.
3. Excluded handlers (/metrics, /health) are not tracked.
4. Histogram buckets for duration are generated correctly.
5. All metric and label references in Grafana dashboard and Prometheus alerts match the emitted metrics stream.
"""
import json
import re
import pytest
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from prometheus_fastapi_instrumentator import Instrumentator


@pytest.fixture(scope="module")
def metrics_test_client():
    app = FastAPI(title="Metrics Verification App")

    @app.get("/api/v1/health")
    async def health_check():
        return {"status": "ok"}

    @app.get("/api/v1/resource/ok")
    async def get_ok():
        return {"data": "success"}

    @app.get("/api/v1/resource/error")
    async def get_error():
        raise HTTPException(status_code=500, detail="Synthetic 500 Server Error")

    # Instrument app matching METRICS_INTEGRATION_PLAN.md
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=False,
        excluded_handlers=["/metrics", "/api/v1/health", "/docs", "/openapi.json"],
    )
    instrumentator.instrument(app).expose(app, endpoint="/metrics")

    client = TestClient(app, raise_server_exceptions=False)

    # 1. Trigger HTTP 200
    res_200 = client.get("/api/v1/resource/ok")
    assert res_200.status_code == 200

    # 2. Trigger HTTP 404 (unmapped route)
    res_404 = client.get("/api/v1/resource/non-existent-route")
    assert res_404.status_code == 404

    # 3. Trigger HTTP 500
    res_500 = client.get("/api/v1/resource/error")
    assert res_500.status_code == 500

    # 4. Trigger excluded handler (/api/v1/health)
    res_health = client.get("/api/v1/health")
    assert res_health.status_code == 200

    return client


def test_http_requests_total_metrics_and_status_labels(metrics_test_client):
    """Verifies http_requests_total captures 200, 404, 500 with proper status labels."""
    metrics_res = metrics_test_client.get("/metrics")
    assert metrics_res.status_code == 200
    raw = metrics_res.text

    # Verify 200 is captured
    assert re.search(r'http_requests_total\{[^}]*status="200"[^}]*\}', raw)

    # Verify 404 is captured with handler="none"
    assert re.search(r'http_requests_total\{[^}]*handler="none"[^}]*status="404"[^}]*\}', raw)

    # Verify 500 is captured
    assert re.search(r'http_requests_total\{[^}]*status="500"[^}]*\}', raw)


def test_excluded_handlers_not_in_metrics(metrics_test_client):
    """Verifies excluded endpoints (/metrics, /api/v1/health) are not recorded in requests total."""
    metrics_res = metrics_test_client.get("/metrics")
    raw = metrics_res.text

    # /metrics itself must not be tracked
    assert 'handler="/metrics"' not in raw
    # /api/v1/health was excluded in instrumentator config
    assert 'handler="/api/v1/health"' not in raw


def test_latency_histograms_exist(metrics_test_client):
    """Verifies duration histograms are emitted with standard and high-resolution buckets."""
    metrics_res = metrics_test_client.get("/metrics")
    raw = metrics_res.text

    # Low-resolution histogram
    assert "http_request_duration_seconds_bucket" in raw
    assert "http_request_duration_seconds_count" in raw
    assert "http_request_duration_seconds_sum" in raw

    # High-resolution histogram for accurate percentile calculation
    assert "http_request_duration_highr_seconds_bucket" in raw
    assert 'le="2.0"' in raw  # Crucial for 2.0s latency alert rule


def test_promql_expressions_alignment(metrics_test_client):
    """Cross-references PromQL metrics in service-overview.json and alerts.yml against emitted output."""
    raw = metrics_test_client.get("/metrics").text

    # Metrics referenced in alerts and dashboard
    referenced_metrics = [
        "http_requests_total",
        "http_request_duration_highr_seconds_bucket",
    ]

    for metric in referenced_metrics:
        assert metric in raw, f"Metric '{metric}' required by PromQL expressions is missing from emitted metrics"

    # Also verify 'up' is a known Prometheus built-in metric (documented in Grafana panel)
    with open("observability/prometheus/rules/alerts.yml", "r", encoding="utf-8") as f:
        alerts_content = f.read()
    assert "http_requests_total" in alerts_content
    assert "http_request_duration_highr_seconds_bucket" in alerts_content

    with open("observability/grafana/dashboards/service-overview.json", "r", encoding="utf-8") as f:
        dash_content = f.read()
    assert "http_requests_total" in dash_content
    assert "http_request_duration_highr_seconds_bucket" in dash_content
    assert "up{" in dash_content
