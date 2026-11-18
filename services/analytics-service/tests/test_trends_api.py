"""
API Contract and Integration tests for Analytics Trends endpoints.
Uses FastAPI TestClient in-memory (Zero DB, Zero Network).
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_farm_trends_success():
    response = client.get("/api/v1/analytics/farms/farm-binh-an/trends?period=today")
    assert response.status_code == 200
    data = response.json()

    assert data["farmId"] == "farm-binh-an"
    assert data["farmName"] == "Nhà yến Bình An"
    assert data["period"] == "today"
    assert not data["hasDataGaps"]

    # Hourly Bird Activity
    activity = data["hourlyBirdActivity"]
    assert len(activity) == 9
    assert activity[0]["label"] == "05h"
    assert activity[0]["entries"] == 184
    assert activity[0]["exits"] == 326

    # Environment Comparison
    env = data["environmentComparison"]
    assert len(env) == 9
    assert "zone-a" in env[0]["zones"]
    assert env[0]["zones"]["zone-a"]["temperature"] == 28.5
    assert env[0]["zones"]["zone-a"]["humidity"] == 86.0

    # Bird Trend Analytics
    bird_trends = data["birdTrendAnalytics"]
    assert len(bird_trends) == 7
    assert bird_trends[0]["label"] == "10/10"
    assert bird_trends[-1]["entries"] == 428

    # Alert Trend
    alert_trend = data["alertTrend"]
    assert len(alert_trend) == 7

    # Yield Trend
    yield_trend = data["yieldTrend"]
    assert len(yield_trend) == 6
    assert yield_trend[0]["label"] == "T5"
    assert yield_trend[-1]["value"] == 14.8


def test_get_global_trends_success():
    response = client.get("/api/v1/analytics/trends?period=today")
    assert response.status_code == 200
    data = response.json()

    assert data["farmId"] is None
    assert data["farmName"] is None
    assert data["period"] == "today"
    assert len(data["hourlyBirdActivity"]) > 0


def test_get_farm_trends_farm_not_found():
    response = client.get("/api/v1/analytics/farms/non-existent-farm/trends")
    assert response.status_code == 404
    err = response.json()["error"]
    assert err["code"] == "FARM_NOT_FOUND"


def test_get_global_trends_invalid_period():
    response = client.get("/api/v1/analytics/trends?period=millennium")
    assert response.status_code == 400
    err = response.json()["error"]
    assert err["code"] == "INVALID_PERIOD"
