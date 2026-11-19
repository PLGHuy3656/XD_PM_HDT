"""REST API V1 tests for Alert & Notification Service (CP6.3 Tests 1-20)."""
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.domain.enums import AlertEventType, AlertSeverity, AlertSource, AlertStatus, DevicePlatform, NotificationChannel, NotificationDeliveryStatus
from app.dependencies import get_alert_repo, get_notification_repo
from app.schemas.canonical import Alert, Notification


def test_01_health_check(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "notification-service"
    assert data["status"] == "ok"


def test_02_empty_alert_list(client: TestClient):
    resp = client.get("/api/v1/alerts")
    assert resp.status_code == 200
    assert resp.json() == []


def test_03_alert_list_filters(client: TestClient):
    alert_repo = get_alert_repo()
    now = datetime.now(timezone.utc)

    a1 = Alert(
        alert_id="alt_filter_01",
        farm_id="farm_001",
        zone_id="zone_A",
        device_id="dev_01",
        event_type=AlertEventType.HIGH_TEMPERATURE,
        severity=AlertSeverity.HIGH,
        status=AlertStatus.OPEN,
        source=AlertSource.IOT_ENVIRONMENT,
        title="High Temp",
        message="Temp 32C",
        created_at=now,
        updated_at=now,
        last_occurred_at=now,
    )
    a2 = Alert(
        alert_id="alt_filter_02",
        farm_id="farm_001",
        zone_id="zone_B",
        camera_id="cam_01",
        event_type=AlertEventType.PREDATOR_DETECTED,
        severity=AlertSeverity.CRITICAL,
        status=AlertStatus.OPEN,
        source=AlertSource.AI,
        title="Predator Detected",
        message="Owl detected",
        created_at=now,
        updated_at=now,
        last_occurred_at=now,
    )
    a3 = Alert(
        alert_id="alt_filter_03",
        farm_id="farm_002",
        zone_id="zone_A",
        device_id="dev_02",
        event_type=AlertEventType.LOW_TEMPERATURE,
        severity=AlertSeverity.LOW,
        status=AlertStatus.RESOLVED,
        source=AlertSource.IOT_ENVIRONMENT,
        title="Low Temp",
        message="Temp 26C",
        created_at=now,
        updated_at=now,
        last_occurred_at=now,
    )
    alert_repo.save(a1)
    alert_repo.save(a2)
    alert_repo.save(a3)

    # Filter by farmId
    r_farm = client.get("/api/v1/alerts?farmId=farm_001")
    assert r_farm.status_code == 200
    assert len(r_farm.json()) == 2

    # Filter by severity
    r_sev = client.get("/api/v1/alerts?severity=CRITICAL")
    assert r_sev.status_code == 200
    assert len(r_sev.json()) == 1
    assert r_sev.json()[0]["alertId"] == "alt_filter_02"

    # Filter by status
    r_status = client.get("/api/v1/alerts?status=RESOLVED")
    assert r_status.status_code == 200
    assert len(r_status.json()) == 1
    assert r_status.json()[0]["alertId"] == "alt_filter_03"

    # Pagination: limit=1
    r_page = client.get("/api/v1/alerts?limit=1&offset=0")
    assert r_page.status_code == 200
    assert len(r_page.json()) == 1


def test_04_alert_detail(client: TestClient):
    alert_repo = get_alert_repo()
    now = datetime.now(timezone.utc)
    alert = Alert(
        alert_id="alt_detail_01",
        farm_id="farm_001",
        zone_id="zone_A",
        device_id="dev_01",
        event_type=AlertEventType.AUDIO_FAULT,
        severity=AlertSeverity.HIGH,
        status=AlertStatus.OPEN,
        source=AlertSource.IOT_DEVICE,
        title="Audio Fault",
        message="Sensor mic error",
        created_at=now,
        updated_at=now,
        last_occurred_at=now,
    )
    alert_repo.save(alert)

    resp = client.get("/api/v1/alerts/alt_detail_01")
    assert resp.status_code == 200
    data = resp.json()
    assert data["alertId"] == "alt_detail_01"
    assert data["eventType"] == "AUDIO_FAULT"
    assert data["severity"] == "HIGH"


def test_05_unknown_alert_detail(client: TestClient):
    resp = client.get("/api/v1/alerts/non_existent_alert_id")
    assert resp.status_code == 404
    err = resp.json()
    assert err["detail"]["code"] == "ALERT_NOT_FOUND"


def test_06_acknowledge_alert(client: TestClient):
    alert_repo = get_alert_repo()
    now = datetime.now(timezone.utc)
    alert = Alert(
        alert_id="alt_ack_01",
        farm_id="farm_001",
        device_id="dev_01",
        event_type=AlertEventType.HIGH_TEMPERATURE,
        severity=AlertSeverity.HIGH,
        status=AlertStatus.OPEN,
        source=AlertSource.IOT_ENVIRONMENT,
        title="High Temp",
        message="Temp 32C",
        created_at=now,
        updated_at=now,
        last_occurred_at=now,
    )
    alert_repo.save(alert)

    resp = client.post("/api/v1/alerts/alt_ack_01/acknowledge", json={"actorId": "USER-01"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ACKNOWLEDGED"
    assert data["acknowledgedBy"] == "USER-01"
    assert data["acknowledgedAt"] is not None


def test_07_invalid_acknowledge_transition(client: TestClient):
    alert_repo = get_alert_repo()
    now = datetime.now(timezone.utc)
    alert = Alert(
        alert_id="alt_ack_fail",
        farm_id="farm_001",
        device_id="dev_01",
        event_type=AlertEventType.HIGH_TEMPERATURE,
        severity=AlertSeverity.HIGH,
        status=AlertStatus.ACKNOWLEDGED,
        source=AlertSource.IOT_ENVIRONMENT,
        title="High Temp",
        message="Temp 32C",
        acknowledged_by="USER-01",
        acknowledged_at=now,
        created_at=now,
        updated_at=now,
        last_occurred_at=now,
    )
    alert_repo.save(alert)

    # Re-acknowledging already ACKNOWLEDGED alert -> 409 ALERT_INVALID_TRANSITION
    resp = client.post("/api/v1/alerts/alt_ack_fail/acknowledge", json={"actorId": "USER-02"})
    assert resp.status_code == 409
    err = resp.json()
    assert err["detail"]["code"] == "ALERT_INVALID_TRANSITION"


def test_08_resolve_open_alert(client: TestClient):
    alert_repo = get_alert_repo()
    now = datetime.now(timezone.utc)
    alert = Alert(
        alert_id="alt_res_open",
        farm_id="farm_001",
        device_id="dev_01",
        event_type=AlertEventType.COMMAND_FAILED,
        severity=AlertSeverity.HIGH,
        status=AlertStatus.OPEN,
        source=AlertSource.IOT_DEVICE,
        title="Command Failed",
        message="Relay timeout",
        created_at=now,
        updated_at=now,
        last_occurred_at=now,
    )
    alert_repo.save(alert)

    resp = client.post(
        "/api/v1/alerts/alt_res_open/resolve",
        json={"actorId": "USER-01", "resolutionNote": "Manually verified relay operation"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "RESOLVED"
    assert data["resolvedBy"] == "USER-01"
    assert data["resolutionNote"] == "Manually verified relay operation"
    assert data["resolvedAt"] is not None


def test_09_resolve_acknowledged_alert(client: TestClient):
    alert_repo = get_alert_repo()
    now = datetime.now(timezone.utc)
    alert = Alert(
        alert_id="alt_res_ack",
        farm_id="farm_001",
        device_id="dev_01",
        event_type=AlertEventType.AUDIO_FAULT,
        severity=AlertSeverity.HIGH,
        status=AlertStatus.ACKNOWLEDGED,
        source=AlertSource.IOT_DEVICE,
        title="Audio Fault",
        message="Microphone failure",
        acknowledged_by="USER-01",
        acknowledged_at=now,
        created_at=now,
        updated_at=now,
        last_occurred_at=now,
    )
    alert_repo.save(alert)

    resp = client.post(
        "/api/v1/alerts/alt_res_ack/resolve",
        json={"actorId": "USER-01", "resolutionNote": "Replaced mic module"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "RESOLVED"


def test_10_invalid_resolution(client: TestClient):
    alert_repo = get_alert_repo()
    now = datetime.now(timezone.utc)
    alert = Alert(
        alert_id="alt_res_twice",
        farm_id="farm_001",
        device_id="dev_01",
        event_type=AlertEventType.DEVICE_OFFLINE,
        severity=AlertSeverity.CRITICAL,
        status=AlertStatus.RESOLVED,
        source=AlertSource.IOT_DEVICE,
        title="Device Offline",
        message="Device offline",
        resolved_by="USER-01",
        resolved_at=now,
        created_at=now,
        updated_at=now,
        last_occurred_at=now,
    )
    alert_repo.save(alert)

    # Resolving an already RESOLVED alert -> 409 ALERT_INVALID_TRANSITION
    resp = client.post(
        "/api/v1/alerts/alt_res_twice/resolve",
        json={"actorId": "USER-01", "resolutionNote": "Try resolve again"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "ALERT_INVALID_TRANSITION"


def test_11_notification_list_by_user(client: TestClient):
    notif_repo = get_notification_repo()
    now = datetime.now(timezone.utc)
    n1 = Notification(
        notification_id="ntf_usr01_1",
        alert_id="alt_01",
        user_id="USER-01",
        channel=NotificationChannel.IN_APP,
        title="Alert 1",
        body="Body 1",
        delivery_status=NotificationDeliveryStatus.SENT,
        created_at=now,
    )
    n2 = Notification(
        notification_id="ntf_usr02_1",
        alert_id="alt_01",
        user_id="USER-02",
        channel=NotificationChannel.IN_APP,
        title="Alert 1",
        body="Body 1",
        delivery_status=NotificationDeliveryStatus.SENT,
        created_at=now,
    )
    notif_repo.save(n1)
    notif_repo.save(n2)

    resp = client.get("/api/v1/notifications?userId=USER-01")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["notificationId"] == "ntf_usr01_1"


def test_12_unread_read_filtering(client: TestClient):
    notif_repo = get_notification_repo()
    now = datetime.now(timezone.utc)
    n1 = Notification(
        notification_id="ntf_read_01",
        alert_id="alt_01",
        user_id="USER-01",
        channel=NotificationChannel.IN_APP,
        title="Unread Notif",
        body="Body",
        delivery_status=NotificationDeliveryStatus.SENT,
        created_at=now,
        read_at=None,
    )
    n2 = Notification(
        notification_id="ntf_read_02",
        alert_id="alt_01",
        user_id="USER-01",
        channel=NotificationChannel.IN_APP,
        title="Read Notif",
        body="Body",
        delivery_status=NotificationDeliveryStatus.SENT,
        created_at=now,
        read_at=now,
    )
    notif_repo.save(n1)
    notif_repo.save(n2)

    # Filter unread
    r_unread = client.get("/api/v1/notifications?userId=USER-01&isRead=false")
    assert r_unread.status_code == 200
    assert len(r_unread.json()) == 1
    assert r_unread.json()[0]["notificationId"] == "ntf_read_01"

    # Filter read
    r_read = client.get("/api/v1/notifications?userId=USER-01&isRead=true")
    assert r_read.status_code == 200
    assert len(r_read.json()) == 1
    assert r_read.json()[0]["notificationId"] == "ntf_read_02"


def test_13_mark_one_notification_read(client: TestClient):
    notif_repo = get_notification_repo()
    now = datetime.now(timezone.utc)
    n = Notification(
        notification_id="ntf_mark_read_01",
        alert_id="alt_01",
        user_id="USER-01",
        channel=NotificationChannel.IN_APP,
        title="Mark Read",
        body="Body",
        delivery_status=NotificationDeliveryStatus.SENT,
        created_at=now,
        read_at=None,
    )
    notif_repo.save(n)

    resp = client.post(
        "/api/v1/notifications/ntf_mark_read_01/read",
        json={"userId": "USER-01"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["readAt"] is not None
    # Crucial CP6.2/6.3 rule: delivery status MUST remain SENT, not mutated to READ!
    assert data["deliveryStatus"] == "SENT"


def test_14_cannot_read_another_users_notification(client: TestClient):
    notif_repo = get_notification_repo()
    now = datetime.now(timezone.utc)
    n = Notification(
        notification_id="ntf_victim_01",
        alert_id="alt_01",
        user_id="USER-01",
        channel=NotificationChannel.IN_APP,
        title="Private Notice",
        body="Body",
        delivery_status=NotificationDeliveryStatus.SENT,
        created_at=now,
    )
    notif_repo.save(n)

    # USER-02 attempts to read USER-01's notification -> 403 NOTIFICATION_ACCESS_DENIED
    resp = client.post(
        "/api/v1/notifications/ntf_victim_01/read",
        json={"userId": "USER-02"},
    )
    assert resp.status_code == 403
    err = resp.json()
    assert err["detail"]["code"] == "NOTIFICATION_ACCESS_DENIED"


def test_15_mark_all_read(client: TestClient):
    notif_repo = get_notification_repo()
    now = datetime.now(timezone.utc)
    for i in range(3):
        notif_repo.save(
            Notification(
                notification_id=f"ntf_bulk_{i}",
                alert_id="alt_01",
                user_id="USER-01",
                channel=NotificationChannel.IN_APP,
                title=f"Notif {i}",
                body="Body",
                delivery_status=NotificationDeliveryStatus.SENT,
                created_at=now,
                read_at=None,
            )
        )

    resp = client.post("/api/v1/notifications/read-all", json={"userId": "USER-01"})
    assert resp.status_code == 200
    assert resp.json()["updatedCount"] == 3

    # Verify all now have readAt set
    unread = client.get("/api/v1/notifications?userId=USER-01&isRead=false").json()
    assert len(unread) == 0


def test_16_register_device(client: TestClient):
    resp = client.post(
        "/api/v1/devices",
        json={
            "userId": "USER-01",
            "token": "token_android_new_123",
            "platform": "ANDROID",
            "deviceName": "Operator Pixel 8",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["userId"] == "USER-01"
    assert data["fcmToken"] == "token_android_new_123"
    assert data["platform"] == "ANDROID"
    assert data["isEnabled"] is True


def test_17_idempotent_device_registration(client: TestClient):
    body = {
        "userId": "USER-01",
        "token": "token_refresh_same_user",
        "platform": "IOS",
        "deviceName": "iPhone 15",
    }
    r1 = client.post("/api/v1/devices", json=body)
    assert r1.status_code == 201
    dev_id1 = r1.json()["deviceId"]

    # Re-register with same token and same user -> idempotent update of same registration
    r2 = client.post("/api/v1/devices", json=body)
    assert r2.status_code == 201
    assert r2.json()["deviceId"] == dev_id1


def test_18_token_ownership_transfer(client: TestClient):
    # User A registers token
    r1 = client.post(
        "/api/v1/devices",
        json={
            "userId": "USER-ALPHA",
            "token": "token_shared_phone",
            "platform": "ANDROID",
        },
    )
    assert r1.status_code == 201
    dev_id = r1.json()["deviceId"]

    # User B registers same token -> ownership transfers to User B
    r2 = client.post(
        "/api/v1/devices",
        json={
            "userId": "USER-BETA",
            "token": "token_shared_phone",
            "platform": "ANDROID",
        },
    )
    assert r2.status_code == 201
    data2 = r2.json()
    assert data2["userId"] == "USER-BETA"
    assert data2["fcmToken"] == "token_shared_phone"


def test_19_delete_disable_device(client: TestClient):
    reg = client.post(
        "/api/v1/devices",
        json={
            "userId": "USER-01",
            "token": "token_to_disable",
            "platform": "WEB",
        },
    ).json()
    dev_id = reg["deviceId"]

    del_resp = client.delete(f"/api/v1/devices/{dev_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "disabled"
    assert del_resp.json()["deviceId"] == dev_id


def test_20_unknown_device_delete(client: TestClient):
    resp = client.delete("/api/v1/devices/non_existent_dev_reg_id")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "DEVICE_NOT_FOUND"


def test_21_alert_metadata_lookup(client: TestClient):
    alert_repo = get_alert_repo()
    now = datetime.now(timezone.utc)
    a = Alert(
        alert_id="alt_meta_test",
        farm_id="farm_meta_123",
        zone_id="zone_01",
        device_id="dev_01",
        event_type=AlertEventType.HIGH_TEMPERATURE,
        severity=AlertSeverity.HIGH,
        status=AlertStatus.OPEN,
        source=AlertSource.IOT_ENVIRONMENT,
        title="High Temp",
        message="Temp alert",
        created_at=now,
        updated_at=now,
        last_occurred_at=now,
    )
    alert_repo.save(a)

    resp = client.get("/api/v1/alerts/alt_meta_test/metadata")
    assert resp.status_code == 200
    data = resp.json()
    assert data["alertId"] == "alt_meta_test"
    assert data["farmId"] == "farm_meta_123"
    assert data["status"] == "OPEN"
    assert data["severity"] == "HIGH"
    assert data["eventType"] == "HIGH_TEMPERATURE"
    assert data["deviceId"] == "dev_01"


def test_22_unknown_alert_metadata_404(client: TestClient):
    resp = client.get("/api/v1/alerts/non_existent_alert_id/metadata")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "ALERT_NOT_FOUND"

