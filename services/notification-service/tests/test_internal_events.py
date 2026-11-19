"""Internal test harness event ingestion tests (CP6.3 Tests 21-28)."""
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.domain.enums import AlertEventType, AlertSeverity, AlertStatus


def test_21_internal_predator_event_creates_alert(client: TestClient):
    resp = client.post(
        "/internal/v1/events/ai",
        json={
            "cameraId": "cam_north_01",
            "farmId": "farm_001",
            "zoneId": "zone_01",
            "eventType": "PREDATOR_DETECTED",
            "predatorType": "owl",
            "confidence": 0.96,
            "snapshotUrl": "http://127.0.0.1:8003/api/v1/ai/snapshots/snap_owl.jpg",
        },
    )
    assert resp.status_code == 200
    alerts = resp.json()
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["eventType"] == "PREDATOR_DETECTED"
    assert alert["severity"] == "CRITICAL"
    assert alert["status"] == "OPEN"
    assert alert["source"] == "AI"
    assert alert["snapshotUrl"] == "http://127.0.0.1:8003/api/v1/ai/snapshots/snap_owl.jpg"


def test_22_internal_high_temperature_event_creates_alert(client: TestClient):
    resp = client.post(
        "/internal/v1/events/iot/telemetry",
        json={
            "deviceId": "SWC-NODE-001",
            "farmId": "farm_001",
            "zoneId": "zone_01",
            "temperature": 32.5,
            "humidity": 75.0,
            "audioHealthy": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["triggered"]) == 1
    trig = data["triggered"][0]
    assert trig["eventType"] == "HIGH_TEMPERATURE"
    assert trig["severity"] == "HIGH"
    assert trig["status"] == "OPEN"
    assert trig["occurrenceCount"] == 1


def test_23_internal_repeated_high_temperature_increments_occurrence(client: TestClient):
    body = {
        "deviceId": "SWC-NODE-001",
        "farmId": "farm_001",
        "zoneId": "zone_01",
        "temperature": 32.5,
        "humidity": 75.0,
    }
    r1 = client.post("/internal/v1/events/iot/telemetry", json=body)
    assert r1.status_code == 200
    alert_id = r1.json()["triggered"][0]["alertId"]

    # Send second violating reading
    r2 = client.post("/internal/v1/events/iot/telemetry", json=body)
    assert r2.status_code == 200
    data2 = r2.json()
    assert len(data2["triggered"]) == 1
    assert data2["triggered"][0]["alertId"] == alert_id
    assert data2["triggered"][0]["occurrenceCount"] == 2


def test_24_internal_recovery_telemetry_resolves_alert(client: TestClient):
    # 1. Trigger high temperature alert
    client.post(
        "/internal/v1/events/iot/telemetry",
        json={
            "deviceId": "SWC-NODE-001",
            "farmId": "farm_001",
            "zoneId": "zone_01",
            "temperature": 32.5,
            "humidity": 75.0,
        },
    )

    # 2. Temperature drops to 30.2C (<= 30.5C recovery threshold configured for farm_001)
    rec_resp = client.post(
        "/internal/v1/events/iot/telemetry",
        json={
            "deviceId": "SWC-NODE-001",
            "farmId": "farm_001",
            "zoneId": "zone_01",
            "temperature": 30.2,
            "humidity": 75.0,
        },
    )
    assert rec_resp.status_code == 200
    data = rec_resp.json()
    assert len(data["resolved"]) == 1
    res_alert = data["resolved"][0]
    assert res_alert["status"] == "RESOLVED"
    assert res_alert["resolvedBy"] == "SYSTEM"
    assert "auto-recovered" in res_alert["resolutionNote"].lower()


def test_25_internal_device_offline_creates_alert(client: TestClient):
    resp = client.post(
        "/internal/v1/events/iot/presence",
        json={
            "deviceId": "SWC-NODE-001",
            "farmId": "farm_001",
            "zoneId": "zone_01",
            "status": "OFFLINE",
            "statusReason": "Heartbeat missed",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["triggered"]) == 1
    trig = data["triggered"][0]
    assert trig["eventType"] == "DEVICE_OFFLINE"
    assert trig["severity"] == "CRITICAL"


def test_26_internal_device_online_auto_resolves_offline_alert(client: TestClient):
    # Go OFFLINE
    client.post(
        "/internal/v1/events/iot/presence",
        json={
            "deviceId": "SWC-NODE-001",
            "farmId": "farm_001",
            "zoneId": "zone_01",
            "status": "OFFLINE",
        },
    )

    # Come back ONLINE -> auto-resolves
    rec = client.post(
        "/internal/v1/events/iot/presence",
        json={
            "deviceId": "SWC-NODE-001",
            "farmId": "farm_001",
            "zoneId": "zone_01",
            "status": "ONLINE",
        },
    )
    assert rec.status_code == 200
    data = rec.json()
    assert len(data["resolved"]) == 1
    assert data["resolved"][0]["status"] == "RESOLVED"
    assert data["resolved"][0]["resolvedBy"] == "SYSTEM"


def test_27_internal_command_failed_creates_alert(client: TestClient):
    resp = client.post(
        "/internal/v1/events/iot/command",
        json={
            "commandId": "cmd_fail_01",
            "deviceId": "SWC-NODE-001",
            "farmId": "farm_001",
            "zoneId": "zone_01",
            "commandType": "SET_RELAY",
            "status": "FAILED",
            "failureReason": "Hardware pin shorted",
        },
    )
    assert resp.status_code == 200
    alerts = resp.json()
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["eventType"] == "COMMAND_FAILED"
    assert alert["severity"] == "HIGH"
    assert "Hardware pin shorted" in alert["message"]


def test_28_internal_command_success_creates_no_alert(client: TestClient):
    resp = client.post(
        "/internal/v1/events/iot/command",
        json={
            "commandId": "cmd_ok_01",
            "deviceId": "SWC-NODE-001",
            "farmId": "farm_001",
            "commandType": "SET_RELAY",
            "status": "SUCCESS",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == []
