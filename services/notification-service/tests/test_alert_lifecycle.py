from datetime import datetime, timezone
import pytest
from app.domain.enums import AlertStatus, AlertSeverity, AlertSource, AlertEventType
from app.repositories.in_memory_alert_repo import InMemoryAlertRepository
from app.services.alert_lifecycle_service import AlertLifecycleService


def test_valid_alert_lifecycle_transitions(lifecycle_service: AlertLifecycleService):
    now = datetime(2026, 10, 27, 8, 0, 0, tzinfo=timezone.utc)
    alert, is_new = lifecycle_service.process_incoming_alert(
        farm_id="farm_001",
        zone_id="zone_01",
        device_id="SWC-NODE-001",
        camera_id=None,
        event_type=AlertEventType.HIGH_TEMPERATURE,
        severity=AlertSeverity.HIGH,
        source=AlertSource.IOT_ENVIRONMENT,
        title="High Temperature",
        message="Temp is 32C",
        occurred_at=now,
    )
    assert is_new is True
    assert alert.status == AlertStatus.OPEN

    # 1. OPEN -> ACKNOWLEDGED
    ack_alert = lifecycle_service.acknowledge(
        alert_id=alert.alert_id,
        acknowledged_by="user_operator_01",
    )
    assert ack_alert.status == AlertStatus.ACKNOWLEDGED
    assert ack_alert.acknowledged_by == "user_operator_01"
    assert ack_alert.acknowledged_at is not None

    # 2. ACKNOWLEDGED -> RESOLVED
    res_alert = lifecycle_service.resolve(
        alert_id=alert.alert_id,
        resolved_by="user_operator_01",
        resolution_note="Fan speed adjusted, temperature normalized",
    )
    assert res_alert.status == AlertStatus.RESOLVED
    assert res_alert.resolved_by == "user_operator_01"
    assert res_alert.resolution_note == "Fan speed adjusted, temperature normalized"
    assert res_alert.resolved_at is not None


def test_direct_open_to_resolved_transition(lifecycle_service: AlertLifecycleService):
    alert, _ = lifecycle_service.process_incoming_alert(
        farm_id="farm_001",
        zone_id="zone_01",
        device_id="SWC-NODE-001",
        camera_id=None,
        event_type=AlertEventType.AUDIO_FAULT,
        severity=AlertSeverity.HIGH,
        source=AlertSource.IOT_DEVICE,
        title="Audio Fault",
        message="Microphone failure",
    )
    assert alert.status == AlertStatus.OPEN

    # Directly resolve from OPEN
    res = lifecycle_service.resolve(
        alert_id=alert.alert_id,
        resolved_by="technician_01",
        resolution_note="Microphone replaced",
    )
    assert res.status == AlertStatus.RESOLVED


def test_invalid_lifecycle_transitions(lifecycle_service: AlertLifecycleService):
    alert, _ = lifecycle_service.process_incoming_alert(
        farm_id="farm_001",
        zone_id="zone_01",
        device_id="SWC-NODE-001",
        camera_id=None,
        event_type=AlertEventType.HIGH_TEMPERATURE,
        severity=AlertSeverity.HIGH,
        source=AlertSource.IOT_ENVIRONMENT,
        title="High Temp",
        message="Temp high",
    )

    # 1. Acknowledge once
    lifecycle_service.acknowledge(alert.alert_id, "user_01")

    # Acknowledge again while already ACKNOWLEDGED -> ValueError
    with pytest.raises(ValueError, match="already ACKNOWLEDGED"):
        lifecycle_service.acknowledge(alert.alert_id, "user_02")

    # Resolve alert
    lifecycle_service.resolve(alert.alert_id, "user_01", "Fixed")

    # 2. Try to acknowledge a RESOLVED alert -> ValueError
    with pytest.raises(ValueError, match="already RESOLVED"):
        lifecycle_service.acknowledge(alert.alert_id, "user_01")

    # 3. Try to resolve an already RESOLVED alert -> ValueError
    with pytest.raises(ValueError, match="already RESOLVED"):
        lifecycle_service.resolve(alert.alert_id, "user_01", "Fixed again")


def test_alert_deduplication_and_reopen_after_resolution(lifecycle_service: AlertLifecycleService):
    # Event 1: New Alert
    t1 = datetime(2026, 10, 27, 9, 0, 0, tzinfo=timezone.utc)
    a1, is_new1 = lifecycle_service.process_incoming_alert(
        farm_id="farm_001",
        zone_id="zone_01",
        device_id="SWC-NODE-001",
        camera_id=None,
        event_type=AlertEventType.HIGH_TEMPERATURE,
        severity=AlertSeverity.HIGH,
        source=AlertSource.IOT_ENVIRONMENT,
        title="High Temp",
        message="Temp 31.5C",
        occurred_at=t1,
    )
    assert is_new1 is True
    assert a1.occurrence_count == 1
    assert a1.created_at == t1

    # Event 2: Same dedup key while OPEN -> deduplicates into a1
    t2 = datetime(2026, 10, 27, 9, 5, 0, tzinfo=timezone.utc)
    a2, is_new2 = lifecycle_service.process_incoming_alert(
        farm_id="farm_001",
        zone_id="zone_01",
        device_id="SWC-NODE-001",
        camera_id=None,
        event_type=AlertEventType.HIGH_TEMPERATURE,
        severity=AlertSeverity.HIGH,
        source=AlertSource.IOT_ENVIRONMENT,
        title="High Temp",
        message="Temp 32.0C",
        occurred_at=t2,
    )
    assert is_new2 is False
    assert a2.alert_id == a1.alert_id
    assert a2.occurrence_count == 2
    assert a2.last_occurred_at == t2
    assert a2.status == AlertStatus.OPEN

    # Acknowledge the alert
    lifecycle_service.acknowledge(a1.alert_id, "operator_01")

    # Event 3: Same dedup key while ACKNOWLEDGED -> deduplicates into a1
    t3 = datetime(2026, 10, 27, 9, 10, 0, tzinfo=timezone.utc)
    a3, is_new3 = lifecycle_service.process_incoming_alert(
        farm_id="farm_001",
        zone_id="zone_01",
        device_id="SWC-NODE-001",
        camera_id=None,
        event_type=AlertEventType.HIGH_TEMPERATURE,
        severity=AlertSeverity.HIGH,
        source=AlertSource.IOT_ENVIRONMENT,
        title="High Temp",
        message="Temp 32.2C",
        occurred_at=t3,
    )
    assert is_new3 is False
    assert a3.alert_id == a1.alert_id
    assert a3.occurrence_count == 3
    assert a3.status == AlertStatus.ACKNOWLEDGED

    # Resolve the alert
    lifecycle_service.resolve(a1.alert_id, "operator_01", "Cooling restored")

    # Event 4: Same dedup key after RESOLVED -> creates a brand NEW alert!
    t4 = datetime(2026, 10, 27, 10, 0, 0, tzinfo=timezone.utc)
    a4, is_new4 = lifecycle_service.process_incoming_alert(
        farm_id="farm_001",
        zone_id="zone_01",
        device_id="SWC-NODE-001",
        camera_id=None,
        event_type=AlertEventType.HIGH_TEMPERATURE,
        severity=AlertSeverity.HIGH,
        source=AlertSource.IOT_ENVIRONMENT,
        title="High Temp",
        message="Temp 31.8C again",
        occurred_at=t4,
    )
    assert is_new4 is True
    assert a4.alert_id != a1.alert_id
    assert a4.occurrence_count == 1
    assert a4.status == AlertStatus.OPEN
