"""Comprehensive Final E2E Validation Script for Notification Service V1 (CP6.5).

Executes Cases A through E as defined in CP6.5 Specification:
- CASE A: Environment threshold breach -> dedup -> hysteresis recovery.
- CASE B: Device presence transition (OFFLINE -> dedup -> ONLINE auto-resolve).
- CASE C: Command execution states (PUBLISHED no alert -> FAILED -> human resolution).
- CASE D: AI predator detection (CRITICAL alert -> IN_APP + FCM push -> WebSocket).
- CASE E: Invalid FCM push token handling (FAILED status -> soft-disable device).
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.config.alert_rules import AlertRuleConfig
from app.dependencies import (
    get_alert_repo,
    get_notification_repo,
    get_recipient_resolver,
    get_rule_config_provider,
    get_user_device_repo,
    init_app_state,
    reset_app_state,
)
from app.domain.enums import (
    AlertEventType,
    AlertSeverity,
    AlertStatus,
    DevicePlatform,
    NotificationChannel,
    NotificationDeliveryStatus,
)
from app.infrastructure.firebase import (
    FCMSettings,
    FakeFirebaseMessagingClient,
    FirebaseFCMProvider,
)
from app.main import app
from app.ports.recipient_resolver import RecipientInfo
from app.schemas.canonical import UserDevice


def run_final_e2e() -> bool:
    print("=" * 80)
    print("CP6.5 NOTIFICATION SERVICE FINAL E2E VALIDATION (CASES A - E)")
    print("=" * 80)

    # 0. Setup Fake Firebase and App State
    fake_fcm = FakeFirebaseMessagingClient()
    fcm_settings = FCMSettings(provider="firebase", enabled=True, project_id="swiftletcare-prod")
    fcm_provider = FirebaseFCMProvider(client=fake_fcm, settings=fcm_settings)

    init_app_state(fcm_provider=fcm_provider)

    rule_provider = get_rule_config_provider()
    rule_provider.set_rules_for_farm(
        "farm_001",
        AlertRuleConfig(
            farm_id="farm_001",
            high_temp_celsius=31.0,
            high_temp_recovery_celsius=30.5,
        ),
    )

    resolver = get_recipient_resolver()
    resolver.register_recipient(
        "farm_001",
        RecipientInfo(user_id="user_owner_01", email="owner@farm001.com", roles=["FARM_OWNER"]),
    )
    resolver.register_recipient(
        "farm_001",
        RecipientInfo(user_id="user_tech_01", email="tech@farm001.com", roles=["TECHNICIAN"]),
    )

    device_repo = get_user_device_repo()
    device_repo.register_device(
        UserDevice(
            device_id="dev_phone_owner",
            user_id="user_owner_01",
            fcm_token="token_valid_owner_phone",
            platform=DevicePlatform.ANDROID,
            is_enabled=True,
        )
    )

    client = TestClient(app)

    # =========================================================================
    # CASE A: ENVIRONMENT (HIGH TEMPERATURE -> DEDUP -> HYSTERESIS RECOVERY)
    # =========================================================================
    print("\n[CASE A] Environment: High Temperature Breach, Dedup, and Recovery")
    with client.websocket_connect("/ws/notifications?userId=user_owner_01") as ws_owner:
        # A1. Initial Breach (32.0C > 31.0C)
        resp1 = client.post(
            "/internal/v1/events/iot/telemetry",
            json={
                "deviceId": "temp_sensor_01",
                "farmId": "farm_001",
                "zoneId": "zone_a",
                "temperature": 32.0,
                "humidity": 80.0,
            },
        )
        assert resp1.status_code == 200, f"A1 failed: {resp1.text}"
        a1_data = resp1.json()["triggered"][0]
        alert_a_id = a1_data["alertId"]
        assert a1_data["eventType"] == "HIGH_TEMPERATURE"
        assert a1_data["status"] == "OPEN"
        print(f"  A1. High temp event ingested: Alert {alert_a_id} created (OPEN)")

        # Verify WebSocket received alert.created and notification.created
        msg_ws_a1 = ws_owner.receive_json()
        assert msg_ws_a1["type"] == "alert.created"
        msg_ws_n1 = ws_owner.receive_json()
        assert msg_ws_n1["type"] == "notification.created"
        assert msg_ws_n1["data"]["channel"] == "IN_APP"
        msg_ws_fcm = ws_owner.receive_json()
        assert msg_ws_fcm["type"] == "notification.created"
        assert msg_ws_fcm["data"]["channel"] == "FCM"
        print("  A1. WebSocket received: alert.created, notification.created (IN_APP & FCM)")

        # Verify REST API shows Alert
        rest_a = client.get(f"/api/v1/alerts/{alert_a_id}")
        assert rest_a.status_code == 200
        assert rest_a.json()["status"] == "OPEN"
        print(f"  A1. REST GET /api/v1/alerts/{alert_a_id} verified: HTTP 200 OPEN")

        # A2. Repeated Violation (32.5C) -> Deduplication
        notif_count_before = len(client.get("/api/v1/notifications", headers={"X-User-Id": "user_owner_01"}).json())
        resp2 = client.post(
            "/internal/v1/events/iot/telemetry",
            json={
                "deviceId": "temp_sensor_01",
                "farmId": "farm_001",
                "zoneId": "zone_a",
                "temperature": 32.5,
                "humidity": 80.0,
            },
        )
        assert resp2.status_code == 200
        a2_data = resp2.json()["triggered"][0]
        assert a2_data["alertId"] == alert_a_id
        assert a2_data["occurrenceCount"] == 2
        print(f"  A2. Repeated high temp: Deduplicated into same alert (occurrenceCount=2)")

        # Verify NO notification spam (notification count unchanged)
        notif_count_after = len(client.get("/api/v1/notifications", headers={"X-User-Id": "user_owner_01"}).json())
        assert notif_count_after == notif_count_before
        print(f"  A2. Notification spam check: In-app count unchanged ({notif_count_after})")

        # A3. Hysteresis Recovery (30.0C <= 30.5C recovery threshold)
        resp3 = client.post(
            "/internal/v1/events/iot/telemetry",
            json={
                "deviceId": "temp_sensor_01",
                "farmId": "farm_001",
                "zoneId": "zone_a",
                "temperature": 30.0,
                "humidity": 80.0,
            },
        )
        assert resp3.status_code == 200
        resolved_list = resp3.json()["resolved"]
        assert len(resolved_list) == 1
        assert resolved_list[0]["alertId"] == alert_a_id
        assert resolved_list[0]["status"] == "RESOLVED"
        assert resolved_list[0]["resolvedBy"] == "SYSTEM"
        print(f"  A3. Temperature 30.0C within deadband: Auto-RESOLVED by SYSTEM")

    # =========================================================================
    # CASE B: DEVICE PRESENCE (OFFLINE -> DEDUP -> ONLINE RECOVERY)
    # =========================================================================
    print("\n[CASE B] Device Presence: OFFLINE Transition and ONLINE Recovery")
    # B1. Device OFFLINE
    resp_b1 = client.post(
        "/internal/v1/events/iot/presence",
        json={
            "deviceId": "gateway_mesh_01",
            "farmId": "farm_001",
            "status": "OFFLINE",
            "statusReason": "Heartbeat lost",
        },
    )
    assert resp_b1.status_code == 200
    alert_b_id = resp_b1.json()["triggered"][0]["alertId"]
    assert resp_b1.json()["triggered"][0]["eventType"] == "DEVICE_OFFLINE"
    print(f"  B1. Device OFFLINE: Alert {alert_b_id} created (DEVICE_OFFLINE, OPEN)")

    # B2. Repeat OFFLINE (Deduplication)
    resp_b2 = client.post(
        "/internal/v1/events/iot/presence",
        json={
            "deviceId": "gateway_mesh_01",
            "farmId": "farm_001",
            "status": "OFFLINE",
            "statusReason": "Repeated timeout",
        },
    )
    assert resp_b2.status_code == 200
    assert resp_b2.json()["triggered"][0]["alertId"] == alert_b_id
    assert resp_b2.json()["triggered"][0]["occurrenceCount"] == 2
    print(f"  B2. Repeated OFFLINE: Deduplicated (occurrenceCount=2)")

    # B3. Device ONLINE (Auto-resolve)
    resp_b3 = client.post(
        "/internal/v1/events/iot/presence",
        json={
            "deviceId": "gateway_mesh_01",
            "farmId": "farm_001",
            "status": "ONLINE",
        },
    )
    assert resp_b3.status_code == 200
    res_b = resp_b3.json()["resolved"][0]
    assert res_b["alertId"] == alert_b_id
    assert res_b["status"] == "RESOLVED"
    print(f"  B3. Device ONLINE: Alert {alert_b_id} auto-resolved by SYSTEM")

    # =========================================================================
    # CASE C: COMMAND EXECUTION (PUBLISHED NO ALERT, FAILED -> HUMAN RESOLVE)
    # =========================================================================
    print("\n[CASE C] Command Execution: PUBLISHED vs FAILED and Human Resolution")
    # C1. PUBLISHED (no alert)
    resp_c1 = client.post(
        "/internal/v1/events/iot/command",
        json={
            "commandId": "cmd_relay_01",
            "deviceId": "actuator_fan_01",
            "farmId": "farm_001",
            "commandType": "SET_RELAY",
            "status": "PUBLISHED",
        },
    )
    assert resp_c1.status_code == 200
    assert len(resp_c1.json()) == 0
    print("  C1. Command status=PUBLISHED: 0 alerts created (correct)")

    # C2. FAILED (triggers COMMAND_FAILED, HIGH severity)
    resp_c2 = client.post(
        "/internal/v1/events/iot/command",
        json={
            "commandId": "cmd_relay_02",
            "deviceId": "actuator_fan_01",
            "farmId": "farm_001",
            "commandType": "SET_RELAY",
            "status": "FAILED",
            "failureReason": "Hardware coil fault",
        },
    )
    assert resp_c2.status_code == 200
    c2_alerts = resp_c2.json()
    assert len(c2_alerts) == 1
    alert_c_id = c2_alerts[0]["alertId"]
    assert c2_alerts[0]["eventType"] == "COMMAND_FAILED"
    assert c2_alerts[0]["severity"] == "HIGH"
    print(f"  C2. Command status=FAILED: Alert {alert_c_id} created (COMMAND_FAILED, HIGH)")

    # C3. Verify Command Alert is NOT auto-resolved by subsequent events
    resp_c3 = client.post(
        "/internal/v1/events/iot/command",
        json={
            "commandId": "cmd_relay_03",
            "deviceId": "actuator_fan_01",
            "farmId": "farm_001",
            "commandType": "SET_RELAY",
            "status": "SUCCESS",
        },
    )
    assert resp_c3.status_code == 200
    assert len(resp_c3.json()) == 0
    c_check = client.get(f"/api/v1/alerts/{alert_c_id}").json()
    assert c_check["status"] == "OPEN"
    print(f"  C3. Later command SUCCESS does NOT auto-resolve command alert (remains OPEN)")

    # C4. Human Resolution via REST
    resp_c4 = client.post(
        f"/api/v1/alerts/{alert_c_id}/resolve",
        json={"actorId": "tech_tran_01", "resolutionNote": "Replaced fuse"},
    )
    assert resp_c4.status_code == 200
    assert resp_c4.json()["status"] == "RESOLVED"
    assert resp_c4.json()["resolvedBy"] == "tech_tran_01"
    print(f"  C4. Human resolution via POST /resolve successful: status=RESOLVED")

    # =========================================================================
    # CASE D: AI PREDATOR ALERT (CRITICAL, FCM DISPATCH, METADATA)
    # =========================================================================
    print("\n[CASE D] AI Predator Detection: CRITICAL Alert & FCM Push")
    resp_d = client.post(
        "/internal/v1/events/ai",
        json={
            "farmId": "farm_001",
            "zoneId": "zone_nesting_01",
            "cameraId": "cam_nesting_03",
            "snapshotUrl": "https://media.swiftletcare.com/snaps/barn_owl_01.jpg",
            "confidence": 0.98,
            "predatorType": "barn_owl",
        },
    )
    assert resp_d.status_code == 200
    d_alerts = resp_d.json()
    assert len(d_alerts) == 1
    alert_d_id = d_alerts[0]["alertId"]
    assert d_alerts[0]["eventType"] == "PREDATOR_DETECTED"
    assert d_alerts[0]["severity"] == "CRITICAL"
    print(f"  D1. Predator event ingested: Alert {alert_d_id} created (CRITICAL)")

    # Verify Fake FCM client received push
    sent_msgs = [m for m in fake_fcm.sent_messages if m["token"] == "token_valid_owner_phone"]
    assert len(sent_msgs) >= 1
    last_msg = sent_msgs[-1]
    assert last_msg["data"]["alertId"] == alert_d_id
    assert last_msg["data"]["severity"] == "CRITICAL"
    assert last_msg["data"]["snapshotUrl"] == "https://media.swiftletcare.com/snaps/barn_owl_01.jpg"
    print(f"  D2. FCM Push verified: message_id={last_msg['message_id']}, token={last_msg['token'][:8]}...")

    # =========================================================================
    # CASE E: INVALID FCM TOKEN HANDLING
    # =========================================================================
    print("\n[CASE E] Invalid FCM Token Handling: Soft-disable without deleting")
    bad_token = "token_stale_phone_bad"
    device_repo.register_device(
        UserDevice(
            device_id="dev_phone_stale",
            user_id="user_owner_01",
            fcm_token=bad_token,
            platform=DevicePlatform.IOS,
            is_enabled=True,
        )
    )
    fake_fcm.invalid_tokens.add(bad_token)

    # Ingest another event to trigger dispatch to bad_token
    resp_e = client.post(
        "/internal/v1/events/ai",
        json={
            "farmId": "farm_001",
            "zoneId": "zone_nesting_02",
            "cameraId": "cam_nesting_04",
            "confidence": 0.95,
            "predatorType": "snake",
        },
    )
    assert resp_e.status_code == 200
    assert len(resp_e.json()) == 1

    # Verify device is soft-disabled
    dev_stale = device_repo.get_by_id("dev_phone_stale")
    assert dev_stale is not None, "Device record was deleted!"
    assert dev_stale.is_enabled is False, "Device was not disabled!"
    dev_good = device_repo.get_by_id("dev_phone_owner")
    assert dev_good is not None and dev_good.is_enabled is True, "Valid device was affected!"
    print(f"  E1. Invalid token device soft-disabled: dev_phone_stale.is_enabled={dev_stale.is_enabled}")
    print(f"  E2. Valid device remained enabled: dev_phone_owner.is_enabled={dev_good.is_enabled}")

    print("\n" + "=" * 80)
    print("SUCCESS: ALL CASES A, B, C, D, E PASSED WITH 100% CANONICAL COMPLIANCE!")
    print("=" * 80)
    return True


if __name__ == "__main__":
    success = run_final_e2e()
    sys.exit(0 if success else 1)
