from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from app.domain.enums import (
    AlertStatus,
    AlertSeverity,
    AlertSource,
    AlertEventType,
    NotificationChannel,
    NotificationDeliveryStatus,
    DevicePlatform,
)
from app.schemas.canonical import Alert, Notification, UserDevice


def test_alert_canonical_model_serialization():
    now = datetime(2026, 10, 27, 10, 30, 0, tzinfo=timezone.utc)
    alert = Alert(
        alert_id="alt_test_001",
        farm_id="farm_001",
        zone_id="zone_A",
        device_id="SWC-NODE-001",
        camera_id=None,
        event_type=AlertEventType.HIGH_TEMPERATURE,
        severity=AlertSeverity.HIGH,
        status=AlertStatus.OPEN,
        source=AlertSource.IOT_ENVIRONMENT,
        title="High Temperature",
        message="Temperature reached 32C",
        snapshot_url=None,
        telemetry_snapshot={"temperature": 32.0, "humidity": 75.0},
        created_at=now,
        last_occurred_at=now,
        updated_at=now,
        occurrence_count=1,
    )

    data = alert.model_dump(by_alias=True)
    assert data["alertId"] == "alt_test_001"
    assert data["farmId"] == "farm_001"
    assert data["zoneId"] == "zone_A"
    assert data["deviceId"] == "SWC-NODE-001"
    assert data["eventType"] == "HIGH_TEMPERATURE"
    assert data["severity"] == "HIGH"
    assert data["status"] == "OPEN"
    assert data["source"] == "IOT_ENVIRONMENT"
    assert data["occurrenceCount"] == 1
    assert data["createdAt"] == "2026-10-27T10:30:00Z"

    # Roundtrip from json
    json_str = alert.model_dump_json(by_alias=True)
    reloaded = Alert.model_validate_json(json_str)
    assert reloaded.alert_id == alert.alert_id
    assert reloaded.telemetry_snapshot == {"temperature": 32.0, "humidity": 75.0}


def test_alert_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        Alert(
            alert_id="alt_test_001",
            farm_id="farm_001",
            event_type=AlertEventType.PREDATOR_DETECTED,
            severity=AlertSeverity.CRITICAL,
            source=AlertSource.AI,
            title="Predator",
            message="Owl detected",
            unauthorized_field="malicious_payload",  # extra field
        )


def test_notification_canonical_model_read_state():
    now = datetime(2026, 10, 27, 11, 0, 0, tzinfo=timezone.utc)
    notif = Notification(
        notification_id="ntf_001",
        user_id="usr_001",
        alert_id="alt_001",
        channel=NotificationChannel.IN_APP,
        title="High Temp",
        body="Warning temp high",
        delivery_status=NotificationDeliveryStatus.SENT,
        created_at=now,
        read_at=None,
    )

    # is_read is derived from read_at
    assert notif.is_read is False
    assert notif.read_at is None

    # Mark as read
    read_time = datetime(2026, 10, 27, 11, 5, 0, tzinfo=timezone.utc)
    notif.read_at = read_time
    assert notif.is_read is True

    dumped = notif.model_dump(by_alias=True)
    assert dumped["readAt"] == "2026-10-27T11:05:00Z"
    assert dumped["deliveryStatus"] == "SENT"


def test_notification_delivery_status_does_not_contain_read():
    statuses = [s.value for s in NotificationDeliveryStatus]
    assert "READ" not in statuses
    assert set(statuses) == {"PENDING", "SENT", "DELIVERED", "FAILED", "SUPPRESSED"}


def test_user_device_model():
    now = datetime(2026, 10, 27, 12, 0, 0, tzinfo=timezone.utc)
    device = UserDevice(
        device_id="ud_001",
        user_id="usr_001",
        fcm_token="token_xyz_123",
        platform=DevicePlatform.ANDROID,
        is_enabled=True,
        created_at=now,
        updated_at=now,
    )
    dumped = device.model_dump(by_alias=True)
    assert dumped["deviceId"] == "ud_001"
    assert dumped["userId"] == "usr_001"
    assert dumped["fcmToken"] == "token_xyz_123"
    assert dumped["platform"] == "ANDROID"
    assert dumped["isEnabled"] is True
