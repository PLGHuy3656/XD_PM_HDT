"""
API Contract and Integration tests for Farm Analytics Summary endpoint.
Uses FastAPI TestClient in-memory (Zero DB, Zero Network).
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "analytics-service"
    assert data["version"] == "0.1.0"


def test_get_farm_summary_full_data():
    response = client.get("/api/v1/analytics/farms/farm-binh-an/summary?period=day")
    assert response.status_code == 200
    data = response.json()

    assert data["farmId"] == "farm-binh-an"
    assert data["farmName"] == "Nhà yến Bình An"
    assert data["period"] == "day"
    assert not data["hasDataGaps"]

    # Bird Performance: aggregated sum of buckets (entries=2441, exits=1791)
    perf = data["birdPerformance"]
    assert perf["entries"] == 2441
    assert perf["exits"] == 1791
    assert perf["difference"] == 650  # 2441 - 1791
    assert perf["returnRate"] == 100.0  # 2441 > 1791, clamped at 100.0%
    assert perf["change"] == round(((2441 - 2251) / 2251) * 100, 2)  # +8.44%

    # Microclimate Scores [PROPOSED]
    scores = data["microClimateScores"]
    assert len(scores) == 3
    assert scores[0]["id"] == "zone-a"
    assert scores[0]["status"] == "optimal"
    assert scores[0]["score"] == 100.0

    # Alert Distribution
    alerts = data["alertDistribution"]
    assert len(alerts) == 4
    counts_map = {item["severity"]: item["count"] for item in alerts}
    assert counts_map["CRITICAL"] == 2
    assert counts_map["HIGH"] == 4
    assert counts_map["MEDIUM"] == 7
    assert counts_map["LOW"] == 3

    # Yield Summary [PROPOSED]
    y = data["yieldSummary"]
    assert y is not None
    assert y["totalNests"] == 1268
    assert y["harvestedNests"] == 184
    assert y["currentYield"] == 14.8
    assert y["previousYield"] == 13.2
    assert y["yieldChange"] == round(((14.8 - 13.2) / 13.2) * 100, 2)


def test_get_farm_summary_not_found():
    response = client.get("/api/v1/analytics/farms/unknown-farm-999/summary")
    assert response.status_code == 404
    err = response.json()["error"]
    assert err["code"] == "FARM_NOT_FOUND"
    assert "unknown-farm-999" in err["message"]


def test_get_farm_summary_invalid_period():
    response = client.get("/api/v1/analytics/farms/farm-binh-an/summary?period=invalid_era")
    assert response.status_code == 400
    err = response.json()["error"]
    assert err["code"] == "INVALID_PERIOD"
    assert "invalid_era" in err["message"]
