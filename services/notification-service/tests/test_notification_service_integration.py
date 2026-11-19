from datetime import datetime, timezone
import pytest
from app.domain.enums import (
    AlertEventType,
    AlertSeverity,
    AlertStatus,
    NotificationChannel,
    NotificationDeliveryStatus,
)
from app.schemas.events import (
    IoTPresenceAlertInputEvent,
    IoTCommandAlertInputEvent,
    IoTTelemetryAlertInputEvent,
)
from app.services.notification_service import NotificationService


def test_presence_full_e2e_cycle(notification_service: NotificationService):
    t0 = datetime(2026, 10, 27, 15, 0, 0, tzinfo=timezone.utc)

    # 1. Device reports OFFLINE
    off_event = IoTPresenceAlertInputEvent(
        device_id="SWC-NODE-001",
        farm_id="farm_001",
        zone_id="zone_01",
        status="OFFLINE",
        status_reason="Heartbeat missed 3x",
        timestamp=t0,
    )
    trigs, resolves = notification_service.handle_presence_event(off_event)
    assert len(trigs) == 1
    assert len(resolves) == 0

    alert = trigs[0]
    assert alert.status == AlertStatus.OPEN
    assert alert.severity == AlertSeverity.CRITICAL
    assert alert.event_type == AlertEventType.DEVICE_OFFLINE

    # Verify notifications were dispatched to recipient
    notifs = notification_service.list_notifications("user_owner_01")
    assert len(notifs) >= 2  # 1 IN_APP + 1 FCM
    offline_notifs = [n for n in notifs if n.alert_id == alert.alert_id]
    assert len(offline_notifs) == 2

    # 2. Device reports ONLINE -> auto-resolve
    t1 = datetime(2026, 10, 27, 15, 5, 0, tzinfo=timezone.utc)
    on_event = IoTPresenceAlertInputEvent(
        device_id="SWC-NODE-001",
        farm_id="farm_001",
        zone_id="zone_01",
        status="ONLINE",
        timestamp=t1,
    )
    trigs2, resolves2 = notification_service.handle_presence_event(on_event)
    assert len(trigs2) == 0
    assert len(resolves2) == 1

    resolved_alert = resolves2[0]
    assert resolved_alert.alert_id == alert.alert_id
    assert resolved_alert.status == AlertStatus.RESOLVED
    assert resolved_alert.resolved_by == "SYSTEM"
    assert "reconnected" in (resolved_alert.resolution_note or "").lower()


def test_command_failure_e2e_cycle(notification_service: NotificationService):
    t0 = datetime(2026, 10, 27, 15, 10, 0, tzinfo=timezone.utc)

    # SUCCESS command should NOT trigger alert
    ok_cmd = IoTCommandAlertInputEvent(
        command_id="cmd_001",
        device_id="SWC-NODE-001",
        farm_id="farm_001",
        command_type="SET_RELAY",
        status="SUCCESS",
        timestamp=t0,
    )
    alerts_ok = notification_service.handle_command_event(ok_cmd)
    assert len(alerts_ok) == 0

    # TIMEOUT command triggers HIGH alert
    fail_cmd = IoTCommandAlertInputEvent(
        command_id="cmd_002",
        device_id="SWC-NODE-001",
        farm_id="farm_001",
        zone_id="zone_01",
        command_type="SET_RELAY",
        status="TIMEOUT",
        failure_reason="No ACK received within 5000ms",
        timestamp=t0,
    )
    alerts_fail = notification_service.handle_command_event(fail_cmd)
    assert len(alerts_fail) == 1
    alert = alerts_fail[0]
    assert alert.status == AlertStatus.OPEN
    assert alert.severity == AlertSeverity.HIGH
    assert alert.event_type == AlertEventType.COMMAND_FAILED

    # Human operator acknowledges alert
    ack = notification_service.acknowledge_alert(
        alert_id=alert.alert_id,
        acknowledged_by="user_owner_01",
    )
    assert ack.status == AlertStatus.ACKNOWLEDGED
    assert ack.acknowledged_by == "user_owner_01"

    # Human operator resolves alert
    resolved = notification_service.resolve_alert(
        alert_id=alert.alert_id,
        resolved_by="user_owner_01",
        resolution_note="Manually verified relay state, cleared warning",
    )
    assert resolved.status == AlertStatus.RESOLVED
    assert resolved.resolved_by == "user_owner_01"


def test_alert_query_filtering_and_pagination(notification_service: NotificationService):
    now = datetime(2026, 10, 27, 15, 20, 0, tzinfo=timezone.utc)

    # Ingest several telemetry alerts across two zones
    for i, zone in enumerate(["zone_01", "zone_02", "zone_01"]):
        event = IoTTelemetryAlertInputEvent(
            device_id=f"SWC-NODE-{i:03d}",
            farm_id="farm_001",
            zone_id=zone,
            timestamp=now,
            temperature=33.0,
            humidity=80.0,
        )
        notification_service.handle_telemetry_event(event)

    # Filter by farm_id
    farm_alerts = notification_service.list_alerts(farm_id="farm_001")
    assert len(farm_alerts) >= 3

    # Filter by zone_id
    z2_alerts = notification_service.list_alerts(farm_id="farm_001", zone_id="zone_02")
    assert len(z2_alerts) == 1
    assert z2_alerts[0].zone_id == "zone_02"

    # Filter by status
    open_alerts = notification_service.list_alerts(farm_id="farm_001", status=AlertStatus.OPEN)
    assert len(open_alerts) >= 3

    # Limit and offset pagination
    page1 = notification_service.list_alerts(limit=2, offset=0)
    assert len(page1) == 2
    page2 = notification_service.list_alerts(limit=2, offset=2)
    assert len(page2) >= 1
    assert page1[0].alert_id != page2[0].alert_id
