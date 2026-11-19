from datetime import datetime, timezone
from app.domain.enums import (
    AlertEventType,
    NotificationChannel,
    NotificationDeliveryStatus,
    DevicePlatform,
)
from app.schemas.canonical import UserDevice
from app.schemas.events import AIAlertInputEvent, IoTTelemetryAlertInputEvent
from app.services.notification_service import NotificationService
from app.services.mock_fcm_provider import MockFCMProvider


def test_notification_dispatch_on_new_alert(
    notification_service: NotificationService,
    fcm_provider: MockFCMProvider,
):
    now = datetime(2026, 10, 27, 13, 0, 0, tzinfo=timezone.utc)
    event = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_01",
        timestamp=now,
        confidence=0.95,
        predator_type="snake",
    )

    alerts = notification_service.handle_ai_event(event)
    assert len(alerts) == 1
    alert = alerts[0]

    # Check recipient user_owner_01 received both IN_APP and FCM notifications
    notifs = notification_service.list_notifications("user_owner_01")
    assert len(notifs) == 2

    in_app_notifs = [n for n in notifs if n.channel == NotificationChannel.IN_APP]
    fcm_notifs = [n for n in notifs if n.channel == NotificationChannel.FCM]

    assert len(in_app_notifs) == 1
    assert in_app_notifs[0].delivery_status == NotificationDeliveryStatus.SENT
    assert in_app_notifs[0].alert_id == alert.alert_id

    assert len(fcm_notifs) == 1
    # Successful FCM send is SENT (never DELIVERED automatically)
    assert fcm_notifs[0].delivery_status == NotificationDeliveryStatus.SENT
    assert fcm_notifs[0].alert_id == alert.alert_id

    # Verify FCM provider dispatched the message
    assert len(fcm_provider.sent_messages) == 1
    assert fcm_provider.sent_messages[0]["token"] == "token_owner_android_01"


def test_fcm_dispatch_failure_handling(
    notification_service: NotificationService,
    fcm_provider: MockFCMProvider,
):
    fcm_provider.fail_all = True

    now = datetime(2026, 10, 27, 13, 10, 0, tzinfo=timezone.utc)
    event = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_01",
        timestamp=now,
        confidence=0.91,
        predator_type="rat",
    )

    notification_service.handle_ai_event(event)

    notifs = notification_service.list_notifications("user_owner_01")
    fcm_notifs = [n for n in notifs if n.channel == NotificationChannel.FCM]
    assert len(fcm_notifs) == 1
    assert fcm_notifs[0].delivery_status == NotificationDeliveryStatus.FAILED
    assert "FCM dispatch simulated failure" in (fcm_notifs[0].failure_reason or "")


def test_invalid_fcm_token_disables_user_device(
    notification_service: NotificationService,
    fcm_provider: MockFCMProvider,
):
    # Register bad token device
    notification_service.register_device(
        UserDevice(
            device_id="dev_expired_phone",
            user_id="user_owner_01",
            fcm_token="invalid_token_999",
            platform=DevicePlatform.IOS,
            is_enabled=True,
        )
    )
    fcm_provider.invalid_tokens.add("invalid_token_999")

    now = datetime(2026, 10, 27, 13, 20, 0, tzinfo=timezone.utc)
    event = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_01",
        timestamp=now,
        confidence=0.98,
        predator_type="cat",
    )
    notification_service.handle_ai_event(event)

    # Device with invalid_token_999 should now be disabled
    bad_dev = notification_service.user_device_repo.get_by_id("dev_expired_phone")
    assert bad_dev is not None
    assert bad_dev.is_enabled is False


def test_notification_suppressed_on_deduplicated_events(
    notification_service: NotificationService,
    fcm_provider: MockFCMProvider,
):
    now = datetime(2026, 10, 27, 13, 30, 0, tzinfo=timezone.utc)
    event1 = IoTTelemetryAlertInputEvent(
        device_id="SWC-NODE-001",
        farm_id="farm_001",
        zone_id="zone_01",
        timestamp=now,
        temperature=32.0,
        humidity=75.0,
    )

    notification_service.handle_telemetry_event(event1)

    initial_notifs = notification_service.list_notifications("user_owner_01")
    assert len(initial_notifs) == 2  # 1 IN_APP + 1 FCM

    # Second event with same high temperature -> deduplicated into existing alert
    event2 = IoTTelemetryAlertInputEvent(
        device_id="SWC-NODE-001",
        farm_id="farm_001",
        zone_id="zone_01",
        timestamp=now,
        temperature=32.5,
        humidity=75.0,
    )
    notification_service.handle_telemetry_event(event2)

    # Notifications count must NOT increase
    current_notifs = notification_service.list_notifications("user_owner_01")
    assert len(current_notifs) == 2
    assert len(fcm_provider.sent_messages) == 1
