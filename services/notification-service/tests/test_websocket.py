"""WebSocket realtime transport tests for Alert & Notification Service (CP6.3 Tests 29-38)."""
import threading
import time
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_notification_service, get_ws_manager


def test_29_websocket_connect_disconnect(client: TestClient):
    ws_manager = get_ws_manager()
    initial_count = ws_manager.active_count

    with client.websocket_connect("/ws/notifications?userId=USER-TEST") as ws:
        assert ws_manager.active_count == initial_count + 1
        assert ws_manager.user_active_count("USER-TEST") == 1
        ws.send_text("ping")
        assert ws.receive_text() == "pong"

    # After exiting context, client is disconnected
    assert ws_manager.active_count == initial_count


def test_30_alert_created_event_dispatched(client: TestClient):
    with client.websocket_connect("/ws/notifications?userId=USER-01") as ws:
        client.post(
            "/internal/v1/events/ai",
            json={
                "cameraId": "cam_01",
                "farmId": "farm_001",
                "predatorType": "owl",
                "confidence": 0.95,
            },
        )
        # First message received is alert.created
        msg1 = ws.receive_json()
        assert msg1["type"] == "alert.created"
        assert msg1["data"]["eventType"] == "PREDATOR_DETECTED"
        assert msg1["data"]["severity"] == "CRITICAL"


def test_31_alert_updated_event_dispatched_on_acknowledge(client: TestClient):
    # Trigger alert first
    r = client.post(
        "/internal/v1/events/ai",
        json={
            "cameraId": "cam_01",
            "farmId": "farm_001",
            "predatorType": "owl",
            "confidence": 0.95,
        },
    )
    alert_id = r.json()[0]["alertId"]

    with client.websocket_connect("/ws/notifications?userId=USER-01") as ws:
        # Acknowledge the alert
        client.post(f"/api/v1/alerts/{alert_id}/acknowledge", json={"actorId": "USER-01"})
        msg = ws.receive_json()
        assert msg["type"] == "alert.updated"
        assert msg["data"]["alertId"] == alert_id
        assert msg["data"]["status"] == "ACKNOWLEDGED"


def test_32_notification_created_event_dispatched(client: TestClient):
    with client.websocket_connect("/ws/notifications?userId=USER-01") as ws:
        client.post(
            "/internal/v1/events/iot/telemetry",
            json={
                "deviceId": "SWC-NODE-001",
                "farmId": "farm_001",
                "temperature": 32.5,
                "humidity": 75.0,
            },
        )
        # Message 1 is alert.created
        msg1 = ws.receive_json()
        assert msg1["type"] == "alert.created"

        # Message 2 is notification.created (sent to USER-01)
        msg2 = ws.receive_json()
        assert msg2["type"] == "notification.created"
        assert msg2["data"]["userId"] == "USER-01"
        assert msg2["data"]["channel"] == "IN_APP"


def test_33_notification_updated_event_dispatched_on_read(client: TestClient):
    # Create an alert to generate notification for USER-01
    client.post(
        "/internal/v1/events/iot/telemetry",
        json={
            "deviceId": "SWC-NODE-001",
            "farmId": "farm_001",
            "temperature": 32.5,
            "humidity": 75.0,
        },
    )
    notifs = client.get("/api/v1/notifications?userId=USER-01").json()
    notif_id = notifs[0]["notificationId"]

    with client.websocket_connect("/ws/notifications?userId=USER-01") as ws:
        client.post(f"/api/v1/notifications/{notif_id}/read", json={"userId": "USER-01"})
        msg = ws.receive_json()
        assert msg["type"] == "notification.updated"
        assert msg["data"]["notificationId"] == notif_id
        assert msg["data"]["readAt"] is not None


def test_34_and_35_user_scoped_routing_prevents_leaks(client: TestClient):
    # Connect as USER-02 (who is NOT configured as recipient for farm_001)
    with client.websocket_connect("/ws/notifications?userId=USER-OTHER") as ws_other:
        client.post(
            "/internal/v1/events/ai",
            json={
                "cameraId": "cam_01",
                "farmId": "farm_001",
                "predatorType": "snake",
                "confidence": 0.90,
            },
        )
        # USER-OTHER receives the broadcast alert.created
        msg1 = ws_other.receive_json()
        assert msg1["type"] == "alert.created"

        # Ping-pong check: verify NO notification.created was queued or sent to USER-OTHER
        ws_other.send_text("ping")
        assert ws_other.receive_text() == "pong"


def test_36_multiple_connections_for_same_user(client: TestClient):
    with client.websocket_connect("/ws/notifications?userId=USER-01") as ws1:
        with client.websocket_connect("/ws/notifications?userId=USER-01") as ws2:
            client.post(
                "/internal/v1/events/ai",
                json={
                    "cameraId": "cam_01",
                    "farmId": "farm_001",
                    "predatorType": "owl",
                    "confidence": 0.91,
                },
            )
            # Both connections receive alert.created
            m1_a = ws1.receive_json()
            m2_a = ws2.receive_json()
            assert m1_a["type"] == "alert.created"
            assert m2_a["type"] == "alert.created"

            # Both connections receive notification.created
            m1_n = ws1.receive_json()
            m2_n = ws2.receive_json()
            assert m1_n["type"] == "notification.created"
            assert m2_n["type"] == "notification.created"


def test_37_disconnected_client_does_not_break_dispatch(client: TestClient):
    ws_manager = get_ws_manager()

    # Open and close a client
    with client.websocket_connect("/ws/notifications?userId=USER-TEMP") as ws:
        pass

    # Open another healthy client
    with client.websocket_connect("/ws/notifications?userId=USER-HEALTHY") as ws_healthy:
        client.post(
            "/internal/v1/events/ai",
            json={
                "cameraId": "cam_01",
                "farmId": "farm_001",
                "predatorType": "owl",
                "confidence": 0.88,
            },
        )
        msg = ws_healthy.receive_json()
        assert msg["type"] == "alert.created"


def test_38_sync_domain_to_async_websocket_bridge_safety(client: TestClient):
    service = get_notification_service()

    with client.websocket_connect("/ws/notifications?userId=USER-01") as ws:
        # Call domain service from a separate OS worker thread
        def worker_trigger():
            from app.schemas.events import AIAlertInputEvent
            service.handle_ai_event(
                AIAlertInputEvent(
                    camera_id="cam_thread_safe",
                    farm_id="farm_001",
                    predator_type="rat",
                    confidence=0.89,
                )
            )

        t = threading.Thread(target=worker_trigger)
        t.start()
        t.join(timeout=3.0)

        # Ensure WebSocket on main thread receives the event dispatched from worker thread
        msg = ws.receive_json()
        assert msg["type"] == "alert.created"
        assert msg["data"]["cameraId"] == "cam_thread_safe"
