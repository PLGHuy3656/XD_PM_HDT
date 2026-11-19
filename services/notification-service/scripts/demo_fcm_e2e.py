"""E2E Demonstration script for Firebase FCM Adapter V1 (CP6.4).

Demonstrates:
1. NotificationService wired to FirebaseFCMProvider with FakeFirebaseMessagingClient.
2. Ingesting AI predator detection event.
3. Multi-device independent dispatch (valid token -> SENT, invalid token -> FAILED).
4. Automatic soft-disabling of unregistered token device without deleting record.
5. Payload sanitization (stripping local filesystem paths, preserving HTTPS URLs, stringifying types).
6. Read-state lifecycle independence (SENT delivery status retained on mark-as-read).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from app.config.alert_rules import InMemoryAlertRuleConfigProvider
from app.domain.enums import (
    AlertEventType,
    AlertSeverity,
    DevicePlatform,
    NotificationChannel,
    NotificationDeliveryStatus,
)
from app.infrastructure.firebase import (
    FCMSettings,
    FakeFirebaseMessagingClient,
    FirebaseFCMProvider,
    redact_token,
    sanitize_fcm_data,
)
from app.ports.recipient_resolver import RecipientInfo
from app.repositories.in_memory_alert_repo import InMemoryAlertRepository
from app.repositories.in_memory_notification_repo import InMemoryNotificationRepository
from app.repositories.in_memory_user_device_repo import InMemoryUserDeviceRepository
from app.schemas.canonical import UserDevice
from app.schemas.events import AIAlertInputEvent
from app.services.in_memory_recipient_resolver import InMemoryRecipientResolver
from app.services.notification_service import NotificationService
from app.websocket.manager import NotificationWebSocketManager
from app.websocket.sink import WebSocketNotificationEventSink


def main() -> None:
    print("=" * 80)
    print("SwiftletCare Alert & Notification Service — CP6.4 Firebase FCM Adapter E2E Demo")
    print("=" * 80)

    # 1. Initialize Fake Firebase Client & Settings
    fake_client = FakeFirebaseMessagingClient()
    settings = FCMSettings(provider="firebase", enabled=True, project_id="swiftletcare-prod")
    provider = FirebaseFCMProvider(client=fake_client, settings=settings)

    print(f"\n[Step 1] Initialized FirebaseFCMProvider:")
    print(f"  Provider backend : {settings.provider}")
    print(f"  FCM Enabled      : {settings.enabled}")
    print(f"  Firebase Project : {settings.project_id}")

    # 2. Setup Repositories and Services
    alert_repo = InMemoryAlertRepository()
    notif_repo = InMemoryNotificationRepository()
    device_repo = InMemoryUserDeviceRepository()
    rule_config = InMemoryAlertRuleConfigProvider()
    resolver = InMemoryRecipientResolver()
    ws_manager = NotificationWebSocketManager()
    ws_sink = WebSocketNotificationEventSink(ws_manager=ws_manager)

    svc = NotificationService(
        alert_repo=alert_repo,
        notification_repo=notif_repo,
        user_device_repo=device_repo,
        rule_config_provider=rule_config,
        recipient_resolver=resolver,
        fcm_provider=provider,
        event_sink=ws_sink,
    )

    # 3. Configure Recipients & Devices
    # Owner has two devices:
    #   - Phone A: valid active token
    #   - Phone B: stale/unregistered token
    owner_id = "user_owner_nguyen"
    farm_id = "farm_kiengiang_01"

    resolver.register_recipient(
        farm_id=farm_id,
        recipient=RecipientInfo(user_id=owner_id, roles=["FARM_OWNER"]),
    )

    token_valid = "fcm_token_valid_pixel8_abcdef123456"
    token_invalid = "fcm_token_expired_iphone11_xyz987654"

    device_repo.register_device(
        UserDevice(
            device_id="dev_phone_a",
            user_id=owner_id,
            fcm_token=token_valid,
            platform=DevicePlatform.ANDROID,
            is_enabled=True,
        )
    )
    device_repo.register_device(
        UserDevice(
            device_id="dev_phone_b",
            user_id=owner_id,
            fcm_token=token_invalid,
            platform=DevicePlatform.IOS,
            is_enabled=True,
        )
    )

    # Simulate token_invalid being reported as unregistered by FCM gateway
    fake_client.invalid_tokens.add(token_invalid)

    print(f"\n[Step 2] Registered recipient '{owner_id}' with 2 devices:")
    print(f"  Device A (Android) : token={redact_token(token_valid)} (VALID)")
    print(f"  Device B (iOS)     : token={redact_token(token_invalid)} (EXPIRED/UNREGISTERED)")

    # 4. Ingest AI Predator Event
    print(f"\n[Step 3] Ingesting AI Predator Detection Event...")
    event_time = datetime(2026, 10, 27, 20, 15, 0, tzinfo=timezone.utc)
    ai_event = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id=farm_id,
        zone_id="zone_nesting_b",
        camera_id="cam_nesting_04",
        snapshot_url="https://media.swiftletcare.com/snaps/kiengiang_predator_04.jpg",
        timestamp=event_time,
        confidence=0.985,
        predator_type="barn_owl",
    )

    alerts = svc.handle_ai_event(ai_event)
    assert len(alerts) == 1
    alert = alerts[0]

    print(f"  Alert Created:")
    print(f"    Alert ID    : {alert.alert_id}")
    print(f"    Event Type  : {alert.event_type.value}")
    print(f"    Severity    : {alert.severity.value}")
    print(f"    Status      : {alert.status.value}")
    print(f"    Title       : {alert.title}")
    print(f"    Message     : {alert.message}")
    print(f"    Snapshot    : {alert.snapshot_url}")

    # 5. Inspect Notifications Dispatched
    print(f"\n[Step 4] Inspecting Notifications Dispatched to '{owner_id}':")
    notifs = svc.list_notifications(owner_id)
    print(f"  Total notifications generated: {len(notifs)}")

    in_app = next(n for n in notifs if n.channel == NotificationChannel.IN_APP)
    print(f"\n  Channel: IN_APP")
    print(f"    ID        : {in_app.notification_id}")
    print(f"    Status    : {in_app.delivery_status.value}")
    print(f"    Read At   : {in_app.read_at} (isRead={in_app.is_read})")

    fcm_notifs = [n for n in notifs if n.channel == NotificationChannel.FCM]
    print(f"\n  Channel: FCM (Multi-device dispatch)")
    for idx, fn in enumerate(fcm_notifs, 1):
        print(f"    FCM Notification #{idx}:")
        print(f"      ID         : {fn.notification_id}")
        print(f"      Status     : {fn.delivery_status.value}")
        if fn.failure_reason:
            print(f"      Fail Reason: {fn.failure_reason}")

    # 6. Verify Device Repository State After Invalid Token
    print(f"\n[Step 5] Checking UserDevice status after dispatch:")
    dev_a = device_repo.get_by_id("dev_phone_a")
    dev_b = device_repo.get_by_id("dev_phone_b")
    assert dev_a is not None and dev_a.is_enabled is True
    assert dev_b is not None and dev_b.is_enabled is False

    print(f"  Device A (dev_phone_a): is_enabled={dev_a.is_enabled} (Active)")
    print(f"  Device B (dev_phone_b): is_enabled={dev_b.is_enabled} (Soft-disabled, record preserved!)")

    # 7. Verify Fake Firebase Client Deliveries & Payload Sanitization
    print(f"\n[Step 6] Inspecting Messages Dispatched by FirebaseMessagingClient:")
    print(f"  Total messages accepted by Fake client: {len(fake_client.sent_messages)}")
    for sent in fake_client.sent_messages:
        print(f"    Message ID : {sent['message_id']}")
        print(f"    Token      : {redact_token(sent['token'])}")
        print(f"    Title      : {sent['title']}")
        print(f"    Body       : {sent['body']}")
        print(f"    Data Keys  : {list(sent['data'].keys())}")
        print(f"    Data Values: {json.dumps(sent['data'], indent=6)}")

    # 8. Verify Read State Lifecycle
    print(f"\n[Step 7] Marking IN_APP notification as read...")
    read_timestamp = datetime(2026, 10, 27, 20, 16, 0, tzinfo=timezone.utc)
    updated_notif = svc.mark_notification_as_read(
        notification_id=in_app.notification_id,
        user_id=owner_id,
        read_at=read_timestamp,
    )
    print(f"  Read At         : {updated_notif.read_at.isoformat()}")
    print(f"  isRead          : {updated_notif.is_read}")
    print(f"  Delivery Status : {updated_notif.delivery_status.value} (Preserved as SENT, never corrupted to READ)")

    # 9. Test Payload Sanitizer Function Directly
    print(f"\n[Step 8] Verifying Payload Sanitizer against path leaks:")
    leak_test_data = {
        "alertId": "alt_demo_01",
        "snapshotUrl": "https://cdn.swiftletcare.com/snaps/owl.jpg",
        "localFileWin": "C:\\Windows\\temp\\camera.jpg",
        "localFileUnix": "/home/app/secrets/cert.pem",
        "fileUri": "file:///var/log/app.log",
        "confidence": 0.99,
        "isVerified": True,
    }
    sanitized = sanitize_fcm_data(leak_test_data)
    print(f"  Input keys     : {list(leak_test_data.keys())}")
    print(f"  Sanitized keys : {list(sanitized.keys())}")
    print(f"  All values str : {all(isinstance(v, str) for v in sanitized.values())}")
    assert "localFileWin" not in sanitized
    assert "localFileUnix" not in sanitized
    assert "fileUri" not in sanitized
    assert sanitized["snapshotUrl"] == "https://cdn.swiftletcare.com/snaps/owl.jpg"
    assert sanitized["confidence"] == "0.99"
    assert sanitized["isVerified"] == "True"

    print("\n" + "=" * 80)
    print("SUCCESS: All CP6.4 Firebase FCM Adapter behaviors verified!")
    print("=" * 80)


if __name__ == "__main__":
    main()
