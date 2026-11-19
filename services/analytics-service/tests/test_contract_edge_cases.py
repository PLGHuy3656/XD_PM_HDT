"""
Contract and Serialization Edge-Case Tests for Analytics Service.

Validates:
1. Baseline = 0 entries -> change serialized as JSON null, NOT 0 or 100%.
2. Exits = 0 -> returnRate serialized as JSON null, NOT 100%.
3. Camera outage / unobserved intervals -> metrics serialized as null, hasDataGaps = True.
4. Continuous sensor absence -> score is null, status is 'unknown'.
5. Raw JSON wire serialization check (no coercion of null to 0).
"""
import json
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_baseline_zero_serializes_to_null():
    """
    farm-phu-an has baseline = 0 entries.
    change should be None, serializing to JSON null.
    """
    response = client.get("/api/v1/analytics/farms/farm-phu-an/summary?period=day")
    assert response.status_code == 200
    data = response.json()

    perf = data["birdPerformance"]
    assert perf["change"] is None

    # Inspect raw JSON wire bytes
    raw_json = json.loads(response.text)
    assert raw_json["birdPerformance"]["change"] is None
    assert '"change":null' in response.text.replace(" ", "")


def test_zero_exits_serializes_to_null_return_rate():
    """
    farm-zero-exits has entries = 50, exits = 0.
    returnRate must be None (JSON null), NOT 100%.
    """
    response = client.get("/api/v1/analytics/farms/farm-zero-exits/summary?period=day")
    assert response.status_code == 200
    data = response.json()

    perf = data["birdPerformance"]
    assert perf["entries"] == 50
    assert perf["exits"] == 0
    assert perf["returnRate"] is None

    # Raw wire inspection
    assert '"returnRate":null' in response.text.replace(" ", "")


def test_camera_outage_flags_gaps_and_nulls_events():
    """
    farm-camera-down simulates an AI camera outage.
    hasDataGaps must be True, and unobserved metrics must serialize as null.
    """
    # 1. Summary endpoint
    res_summary = client.get("/api/v1/analytics/farms/farm-camera-down/summary?period=day")
    assert res_summary.status_code == 200
    summary_data = res_summary.json()
    assert summary_data["hasDataGaps"] is True

    # Sensors are missing -> score is null, status is unknown
    assert len(summary_data["microClimateScores"]) == 1
    zone_score = summary_data["microClimateScores"][0]
    assert zone_score["score"] is None
    assert zone_score["status"] == "unknown"
    assert '"score":null' in res_summary.text.replace(" ", "")

    # 2. Trends endpoint
    res_trends = client.get("/api/v1/analytics/farms/farm-camera-down/trends?period=today")
    assert res_trends.status_code == 200
    trends_data = res_trends.json()
    assert trends_data["hasDataGaps"] is True

    # Outage hour slots must have entries: null, exits: null
    for item in trends_data["hourlyBirdActivity"]:
        assert item["entries"] is None
        assert item["exits"] is None

    assert '"entries":null' in res_trends.text.replace(" ", "")
    assert '"exits":null' in res_trends.text.replace(" ", "")


def test_missing_yield_data_serializes_as_null():
    """
    Farms without harvest records should serialize yieldSummary as JSON null.
    """
    response = client.get("/api/v1/analytics/farms/farm-phu-an/summary?period=day")
    assert response.status_code == 200
    data = response.json()
    assert data["yieldSummary"] is None
    assert '"yieldSummary":null' in response.text.replace(" ", "")


def test_zero_activity_farm():
    """
    farm-zero-activity has 0 entries, 0 exits, 0 alerts.
    """
    response = client.get("/api/v1/analytics/farms/farm-zero-activity/summary?period=day")
    assert response.status_code == 200
    data = response.json()

    perf = data["birdPerformance"]
    assert perf["entries"] == 0
    assert perf["exits"] == 0
    assert perf["difference"] == 0
    assert perf["returnRate"] is None  # exits == 0 -> null
    assert perf["change"] == 0.0  # 0 -> 0 is 0.0%
