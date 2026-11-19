from datetime import datetime, timezone
from app.domain.enums import DevicePlatform, NotificationChannel, NotificationDeliveryStatus
from app.schemas.canonical import UserDevice, Notification
from app.services.notification_service import NotificationService


def test_user_device_token_uniqueness(notification_service: NotificationService):
    now = datetime(2026, 10, 27, 14, 0, 0, tzinfo=timezone.utc)

    dev1 = UserDevice(
        device_id="dev_001",
        user_id="user_alpha",
        fcm_token="shared_fcm_token_123",
        platform=DevicePlatform.ANDROID,
        is_enabled=True,
        created_at=now,
        updated_at=now,
    )
    notification_service.register_device(dev1)

    devices_alpha = notification_service.list_user_devices("user_alpha")
    assert len(devices_alpha) == 1
    assert devices_alpha[0].fcm_token == "shared_fcm_token_123"

    # User beta logs into the same phone -> same fcm_token
    dev2 = UserDevice(
        device_id="dev_002",
        user_id="user_beta",
        fcm_token="shared_fcm_token_123",
        platform=DevicePlatform.ANDROID,
        is_enabled=True,
        created_at=now,
        updated_at=now,
    )
    notification_service.register_device(dev2)

    # Token must now belong to user_beta; user_alpha's old registration was removed/replaced
    devices_alpha_after = notification_service.list_user_devices("user_alpha")
    assert len(devices_alpha_after) == 0

    devices_beta = notification_service.list_user_devices("user_beta")
    assert len(devices_beta) == 1
    assert devices_beta[0].device_id == "dev_002"
    assert devices_beta[0].fcm_token == "shared_fcm_token_123"


def test_read_state_operations(notification_service: NotificationService):
    now = datetime(2026, 10, 27, 14, 10, 0, tzinfo=timezone.utc)

    # Seed 3 notifications for user_gamma
    for i in range(3):
        n = Notification(
            notification_id=f"ntf_gamma_{i}",
            user_id="user_gamma",
            alert_id=f"alt_{i}",
            channel=NotificationChannel.IN_APP,
            title=f"Notification {i}",
            body=f"Body {i}",
            delivery_status=NotificationDeliveryStatus.SENT,
            created_at=now,
            read_at=None,
        )
        notification_service.notification_repo.save(n)

    # Check unread count
    unread_before = notification_service.list_notifications("user_gamma", is_read=False)
    assert len(unread_before) == 3

    read_before = notification_service.list_notifications("user_gamma", is_read=True)
    assert len(read_before) == 0

    # Mark single notification as read
    marked = notification_service.mark_notification_as_read(
        notification_id="ntf_gamma_0",
        user_id="user_gamma",
    )
    assert marked is not None
    assert marked.read_at is not None
    assert marked.is_read is True

    # Check counts
    unread_mid = notification_service.list_notifications("user_gamma", is_read=False)
    assert len(unread_mid) == 2
    read_mid = notification_service.list_notifications("user_gamma", is_read=True)
    assert len(read_mid) == 1

    # Mark all remaining as read
    marked_count = notification_service.mark_all_notifications_as_read("user_gamma")
    assert marked_count == 2

    unread_after = notification_service.list_notifications("user_gamma", is_read=False)
    assert len(unread_after) == 0

    read_after = notification_service.list_notifications("user_gamma", is_read=True)
    assert len(read_after) == 3
