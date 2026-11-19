"""End-to-End local demonstration for Alert & Notification Service (CP6.3).

Demonstrates:
1. Connecting a realtime WebSocket client scoped to user 'USER-01'.
2. Ingesting a high-temperature event -> creates alert.created + notification.created (IN_APP & FCM).
3. Repeating violating telemetry -> deduplicates into existing alert -> alert.updated (occurrenceCount=2), NO notification storm.
4. Ingesting recovery telemetry (within hysteresis) -> auto-resolves alert -> alert.updated (status=RESOLVED, resolvedBy=SYSTEM).
5. Ingesting PREDATOR_DETECTED AI event -> creates CRITICAL alert + multi-channel notifications.
6. Querying REST API for alerts and notifications.
7. Marking notification as read -> sets readAt, preserves delivery status (SENT).
"""
import sys
from fastapi.testclient import TestClient

from app.config.alert_rules import AlertRuleConfig
from app.dependencies import (
    get_recipient_resolver,
    get_rule_config_provider,
    get_user_device_repo,
    reset_app_state,
)
from app.domain.enums import DevicePlatform
from app.main import app
from app.ports.recipient_resolver import RecipientInfo
from app.schemas.canonical import UserDevice


def run_demo() -> None:
    print("=" * 70)
    print("CP6.3 ALERT & NOTIFICATION SERVICE LOCAL E2E DEMO")
    print("=" * 70)

    # 1. Setup in-memory config and recipient
    reset_app_state()
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
        RecipientInfo(user_id="USER-01", email="operator@farm001.com", roles=["OPERATOR"]),
    )
    device_repo = get_user_device_repo()
    device_repo.register_device(
        UserDevice(
            device_id="dev_pixel_01",
            user_id="USER-01",
            fcm_token="token_fcm_pixel_01",
            platform=DevicePlatform.ANDROID,
            is_enabled=True,
        )
    )
    print("[1] Initialized state: farm_001 rule (threshold 31.0C, recovery 30.5C), recipient USER-01 registered with Android FCM device.")

    client = TestClient(app)

    with client.websocket_connect("/ws/notifications?userId=USER-01") as ws:
        print("[2] WebSocket client connected: /ws/notifications?userId=USER-01")

        # Step 1: Ingest High Temperature Event
        print("\n--- STEP 1: Ingest High-Temperature Telemetry (32.0°C) ---")
        r1 = client.post(
            "/internal/v1/events/iot/telemetry",
            json={
                "deviceId": "SWC-NODE-001",
                "farmId": "farm_001",
                "temperature": 32.0,
                "humidity": 75.0,
            },
        )
        assert r1.status_code == 200
        alert_id = r1.json()["triggered"][0]["alertId"]
        print(f"  -> HTTP POST /internal/v1/events/iot/telemetry returned 200 OK. Alert ID: {alert_id}")

        msg_alert = ws.receive_json()
        print(f"  -> WS received: type='{msg_alert['type']}', severity='{msg_alert['data']['severity']}', status='{msg_alert['data']['status']}'")
        assert msg_alert["type"] == "alert.created"

        # IN_APP notification
        msg_notif1 = ws.receive_json()
        print(f"  -> WS received: type='{msg_notif1['type']}', channel='{msg_notif1['data']['channel']}', status='{msg_notif1['data']['deliveryStatus']}'")
        assert msg_notif1["type"] == "notification.created"

        # FCM push delivery record
        msg_notif2 = ws.receive_json()
        print(f"  -> WS received: type='{msg_notif2['type']}', channel='{msg_notif2['data']['channel']}', status='{msg_notif2['data']['deliveryStatus']}'")
        assert msg_notif2["type"] == "notification.created"

        # Step 2: Repeat High Temperature Event (Deduplication)
        print("\n--- STEP 2: Ingest Repeated High-Temperature Telemetry (32.2°C) ---")
        r2 = client.post(
            "/internal/v1/events/iot/telemetry",
            json={
                "deviceId": "SWC-NODE-001",
                "farmId": "farm_001",
                "temperature": 32.2,
                "humidity": 75.0,
            },
        )
        assert r2.status_code == 200
        data2 = r2.json()["triggered"][0]
        assert data2["alertId"] == alert_id
        assert data2["occurrenceCount"] == 2
        print(f"  -> Deduplicated into existing Alert: occurrenceCount={data2['occurrenceCount']}")

        msg_update = ws.receive_json()
        print(f"  -> WS received: type='{msg_update['type']}', occurrenceCount={msg_update['data']['occurrenceCount']}")
        assert msg_update["type"] == "alert.updated"
        print("  -> Verified: NO duplicate notification storm was generated.")

        # Step 3: Ingest Recovery Telemetry (Hysteresis Auto-Recovery)
        print("\n--- STEP 3: Ingest Recovery Telemetry (30.4°C <= 30.5°C threshold) ---")
        r3 = client.post(
            "/internal/v1/events/iot/telemetry",
            json={
                "deviceId": "SWC-NODE-001",
                "farmId": "farm_001",
                "temperature": 30.4,
                "humidity": 75.0,
            },
        )
        assert r3.status_code == 200
        resolved_list = r3.json()["resolved"]
        assert len(resolved_list) == 1
        res_alert = resolved_list[0]
        print(f"  -> Alert auto-resolved: status='{res_alert['status']}', resolvedBy='{res_alert['resolvedBy']}'")
        print(f"     Note: {res_alert['resolutionNote']}")

        msg_res = ws.receive_json()
        print(f"  -> WS received: type='{msg_res['type']}', status='{msg_res['data']['status']}'")
        assert msg_res["type"] == "alert.updated"
        assert msg_res["data"]["status"] == "RESOLVED"

        # Step 4: Ingest PREDATOR_DETECTED Event
        print("\n--- STEP 4: Ingest AI PREDATOR_DETECTED Event ---")
        r4 = client.post(
            "/internal/v1/events/ai",
            json={
                "cameraId": "cam_east_01",
                "farmId": "farm_001",
                "predatorType": "owl",
                "confidence": 0.94,
                "snapshotUrl": "http://127.0.0.1:8003/api/v1/ai/snapshots/snap_demo.jpg",
            },
        )
        assert r4.status_code == 200
        pred_alert = r4.json()[0]
        print(f"  -> Alert created: {pred_alert['alertId']}, severity='{pred_alert['severity']}', snapshotUrl='{pred_alert['snapshotUrl']}'")
        assert pred_alert["severity"] == "CRITICAL"

        msg_pred_alert = ws.receive_json()
        print(f"  -> WS received: type='{msg_pred_alert['type']}', severity='{msg_pred_alert['data']['severity']}'")
        msg_pred_notif1 = ws.receive_json()
        print(f"  -> WS received: type='{msg_pred_notif1['type']}', channel='{msg_pred_notif1['data']['channel']}'")
        msg_pred_notif2 = ws.receive_json()
        print(f"  -> WS received: type='{msg_pred_notif2['type']}', channel='{msg_pred_notif2['data']['channel']}'")

        # Step 5: Query REST API for user notifications & mark read
        print("\n--- STEP 5: REST API Inbox & Read-State Verification ---")
        notifs_resp = client.get("/api/v1/notifications?userId=USER-01")
        assert notifs_resp.status_code == 200
        notifs = notifs_resp.json()
        print(f"  -> GET /api/v1/notifications?userId=USER-01 returned {len(notifs)} notification records.")

        target_notif_id = notifs[0]["notificationId"]
        read_resp = client.post(f"/api/v1/notifications/{target_notif_id}/read", json={"userId": "USER-01"})
        assert read_resp.status_code == 200
        read_data = read_resp.json()
        print(f"  -> POST /api/v1/notifications/{target_notif_id}/read returned 200 OK.")
        print(f"     readAt: {read_data['readAt']}")
        print(f"     deliveryStatus preserved as: {read_data['deliveryStatus']} (NOT mutated to READ)")
        assert read_data["readAt"] is not None
        assert read_data["deliveryStatus"] == "SENT"

    print("\n" + "=" * 70)
    print("CP6.3 E2E DEMONSTRATION SUCCESSFUL")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
