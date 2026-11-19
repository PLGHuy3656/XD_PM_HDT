"""Comprehensive CP6.4 test suite for Firebase FCM Adapter V1 (Tests 1-42)."""
from __future__ import annotations

import os
from datetime import datetime, timezone
import pytest

from app.config.alert_rules import InMemoryAlertRuleConfigProvider
from app.domain.enums import (
    AlertEventType,
    AlertSeverity,
    AlertSource,
    AlertStatus,
    DevicePlatform,
    NotificationChannel,
    NotificationDeliveryStatus,
)
from app.infrastructure.firebase import (
    DisabledFCMProvider,
    FakeFirebaseMessagingClient,
    FCMErrorCategory,
    FCMProviderType,
    FCMSettings,
    FirebaseFCMProvider,
    create_fcm_provider,
    normalize_firebase_exception,
    redact_token,
    sanitize_fcm_data,
)
from app.ports.recipient_resolver import RecipientInfo
from app.repositories.in_memory_alert_repo import InMemoryAlertRepository
from app.repositories.in_memory_notification_repo import InMemoryNotificationRepository
from app.repositories.in_memory_user_device_repo import InMemoryUserDeviceRepository
from app.schemas.canonical import Alert, Notification, UserDevice
from app.schemas.events import (
    AIAlertInputEvent,
    IoTCommandAlertInputEvent,
    IoTPresenceAlertInputEvent,
    IoTTelemetryAlertInputEvent,
)
from app.services.in_memory_recipient_resolver import InMemoryRecipientResolver
from app.services.mock_fcm_provider import MockFCMProvider
from app.services.notification_service import NotificationService
from app.websocket.manager import NotificationWebSocketManager
from app.websocket.sink import WebSocketNotificationEventSink


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def fake_fcm_client() -> FakeFirebaseMessagingClient:
    return FakeFirebaseMessagingClient()


@pytest.fixture
def firebase_provider(fake_fcm_client: FakeFirebaseMessagingClient) -> FirebaseFCMProvider:
    settings = FCMSettings(provider="firebase", enabled=True, project_id="swiftletcare-test")
    return FirebaseFCMProvider(client=fake_fcm_client, settings=settings)


@pytest.fixture
def test_env(fake_fcm_client: FakeFirebaseMessagingClient, firebase_provider: FirebaseFCMProvider):
    alert_repo = InMemoryAlertRepository()
    notif_repo = InMemoryNotificationRepository()
    device_repo = InMemoryUserDeviceRepository()
    rule_config = InMemoryAlertRuleConfigProvider()
    resolver = InMemoryRecipientResolver()
    ws_manager = NotificationWebSocketManager()
    ws_sink = WebSocketNotificationEventSink(ws_manager=ws_manager)

    # Register default owner recipient
    resolver.register_recipient(
        farm_id="farm_001",
        recipient=RecipientInfo(
            user_id="user_owner_01",
            roles=["FARM_OWNER"],
        ),
    )

    # Register default device
    device_repo.register_device(
        UserDevice(
            device_id="dev_reg_01",
            user_id="user_owner_01",
            fcm_token="token_device_alpha_1234",
            platform=DevicePlatform.ANDROID,
            is_enabled=True,
        )
    )

    svc = NotificationService(
        alert_repo=alert_repo,
        notification_repo=notif_repo,
        user_device_repo=device_repo,
        rule_config_provider=rule_config,
        recipient_resolver=resolver,
        fcm_provider=firebase_provider,
        event_sink=ws_sink,
    )

    return {
        "service": svc,
        "client": fake_fcm_client,
        "provider": firebase_provider,
        "alert_repo": alert_repo,
        "notif_repo": notif_repo,
        "device_repo": device_repo,
        "resolver": resolver,
        "ws_manager": ws_manager,
    }


# =============================================================================
# GROUP 1: Provider Unit Tests (Tests 1-12)
# =============================================================================

def test_01_successful_send_preserves_message_id(firebase_provider: FirebaseFCMProvider, fake_fcm_client: FakeFirebaseMessagingClient):
    resp = firebase_provider.send_single(
        token="valid_token_123",
        title="Alert Title",
        body="Alert Body",
        data={"farmId": "farm_001"},
    )
    assert resp.success is True
    assert resp.message_id is not None
    assert resp.message_id.startswith("projects/swiftletcare-test/messages/")
    assert resp.error is None
    assert resp.invalid_tokens == []
    assert len(fake_fcm_client.sent_messages) == 1


def test_02_successful_send_marks_delivery_status_sent_never_delivered(test_env):
    svc: NotificationService = test_env["service"]
    now = datetime(2026, 10, 27, 14, 0, 0, tzinfo=timezone.utc)

    event = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_01",
        timestamp=now,
        confidence=0.97,
        predator_type="owl",
    )
    svc.handle_ai_event(event)

    notifs = svc.list_notifications("user_owner_01")
    fcm_notifs = [n for n in notifs if n.channel == NotificationChannel.FCM]
    assert len(fcm_notifs) == 1
    # Firebase send success means SENT; never automatically DELIVERED
    assert fcm_notifs[0].delivery_status == NotificationDeliveryStatus.SENT
    assert fcm_notifs[0].delivery_status != NotificationDeliveryStatus.DELIVERED


def test_03_invalid_token_sets_invalid_tokens_list(firebase_provider: FirebaseFCMProvider, fake_fcm_client: FakeFirebaseMessagingClient):
    bad_token = "expired_token_xyz"
    fake_fcm_client.invalid_tokens.add(bad_token)

    resp = firebase_provider.send_single(
        token=bad_token,
        title="Title",
        body="Body",
        data={"k": "v"},
    )
    assert resp.success is False
    assert resp.message_id is None
    assert bad_token in resp.invalid_tokens
    assert resp.error is not None
    assert "Invalid or unregistered FCM token" in resp.error


def test_04_invalid_token_marks_notification_as_failed(test_env):
    svc: NotificationService = test_env["service"]
    client: FakeFirebaseMessagingClient = test_env["client"]
    client.invalid_tokens.add("token_device_alpha_1234")

    now = datetime(2026, 10, 27, 14, 5, 0, tzinfo=timezone.utc)
    event = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_01",
        timestamp=now,
        confidence=0.92,
        predator_type="snake",
    )
    svc.handle_ai_event(event)

    notifs = svc.list_notifications("user_owner_01")
    fcm_notifs = [n for n in notifs if n.channel == NotificationChannel.FCM]
    assert len(fcm_notifs) == 1
    assert fcm_notifs[0].delivery_status == NotificationDeliveryStatus.FAILED
    assert "Invalid or unregistered" in (fcm_notifs[0].failure_reason or "")


def test_05_invalid_token_disables_user_device(test_env):
    svc: NotificationService = test_env["service"]
    client: FakeFirebaseMessagingClient = test_env["client"]
    device_repo: InMemoryUserDeviceRepository = test_env["device_repo"]

    client.invalid_tokens.add("token_device_alpha_1234")

    now = datetime(2026, 10, 27, 14, 10, 0, tzinfo=timezone.utc)
    event = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_01",
        timestamp=now,
        confidence=0.94,
        predator_type="rat",
    )
    svc.handle_ai_event(event)

    # Check device is disabled
    dev = device_repo.get_by_id("dev_reg_01")
    assert dev is not None
    assert dev.is_enabled is False


def test_06_soft_disabled_device_remains_stored_in_repository(test_env):
    device_repo: InMemoryUserDeviceRepository = test_env["device_repo"]
    device_repo.disable_by_token("token_device_alpha_1234")

    # The record is NOT deleted; remains queryable with is_enabled=False
    dev = device_repo.get_by_id("dev_reg_01")
    assert dev is not None
    assert dev.is_enabled is False
    all_devs = device_repo.list_by_user("user_owner_01", is_enabled_only=False)
    assert len(all_devs) == 1
    enabled_devs = device_repo.list_by_user("user_owner_01", is_enabled_only=True)
    assert len(enabled_devs) == 0


def test_07_unauthenticated_error_normalization():
    class UnauthenticatedError(Exception):
        pass

    exc = UnauthenticatedError("The request was not authenticated (credentials expired)")
    norm = normalize_firebase_exception(exc)
    assert norm.category == FCMErrorCategory.AUTHENTICATION_ERROR
    assert norm.is_retryable is False
    assert norm.is_invalid_token is False


def test_08_quota_exceeded_error_normalization():
    class QuotaExceededError(Exception):
        pass

    exc = QuotaExceededError("Resource exhausted: rate limit reached")
    norm = normalize_firebase_exception(exc)
    assert norm.category == FCMErrorCategory.QUOTA_EXCEEDED
    assert norm.is_retryable is False


def test_09_unavailable_error_normalization():
    class UnavailableError(Exception):
        pass

    exc = UnavailableError("Service unavailable, backend timeout")
    norm = normalize_firebase_exception(exc)
    assert norm.category == FCMErrorCategory.UNAVAILABLE
    assert norm.is_retryable is True


def test_10_internal_error_normalization():
    class InternalError(Exception):
        pass

    exc = InternalError("FCM backend encountered an internal error")
    norm = normalize_firebase_exception(exc)
    assert norm.category == FCMErrorCategory.INTERNAL_ERROR
    assert norm.is_retryable is True


def test_11_unknown_exception_normalization():
    exc = RuntimeError("unexpected transport socket failure")
    norm = normalize_firebase_exception(exc)
    assert norm.category == FCMErrorCategory.UNKNOWN
    assert norm.is_retryable is False


def test_12_no_exception_leaks_to_domain_caller(firebase_provider: FirebaseFCMProvider, fake_fcm_client: FakeFirebaseMessagingClient):
    fake_fcm_client.simulate_exception = RuntimeError("Fatal hardware crash")

    # Provider must catch and normalize without re-raising
    resp = firebase_provider.send_single(
        token="some_token",
        title="Alert",
        body="Body",
        data={},
    )
    assert resp.success is False
    assert resp.message_id is None
    assert "Fatal hardware crash" in (resp.error or "")


# =============================================================================
# GROUP 2: Multi-Device Tests (Tests 13-16)
# =============================================================================

def test_13_multiple_enabled_devices_produce_multiple_fcm_notifications(test_env):
    svc: NotificationService = test_env["service"]
    device_repo: InMemoryUserDeviceRepository = test_env["device_repo"]
    client: FakeFirebaseMessagingClient = test_env["client"]

    # Register second device for owner
    device_repo.register_device(
        UserDevice(
            device_id="dev_reg_02",
            user_id="user_owner_01",
            fcm_token="token_device_beta_5678",
            platform=DevicePlatform.IOS,
            is_enabled=True,
        )
    )

    now = datetime(2026, 10, 27, 14, 15, 0, tzinfo=timezone.utc)
    event = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_01",
        timestamp=now,
        confidence=0.99,
        predator_type="snake",
    )
    svc.handle_ai_event(event)

    notifs = svc.list_notifications("user_owner_01")
    fcm_notifs = [n for n in notifs if n.channel == NotificationChannel.FCM]
    assert len(fcm_notifs) == 2
    assert all(n.delivery_status == NotificationDeliveryStatus.SENT for n in fcm_notifs)
    assert len(client.sent_messages) == 2


def test_14_independent_device_delivery_status(test_env):
    svc: NotificationService = test_env["service"]
    device_repo: InMemoryUserDeviceRepository = test_env["device_repo"]
    client: FakeFirebaseMessagingClient = test_env["client"]

    # Register second device and make it fail
    token2 = "token_device_beta_5678"
    device_repo.register_device(
        UserDevice(
            device_id="dev_reg_02",
            user_id="user_owner_01",
            fcm_token=token2,
            platform=DevicePlatform.IOS,
            is_enabled=True,
        )
    )
    client.fail_tokens.add(token2)

    now = datetime(2026, 10, 27, 14, 20, 0, tzinfo=timezone.utc)
    event = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_01",
        timestamp=now,
        confidence=0.96,
        predator_type="rat",
    )
    svc.handle_ai_event(event)

    notifs = svc.list_notifications("user_owner_01")
    fcm_notifs = [n for n in notifs if n.channel == NotificationChannel.FCM]
    assert len(fcm_notifs) == 2

    # Exactly one succeeded and one failed
    statuses = {n.delivery_status for n in fcm_notifs}
    assert NotificationDeliveryStatus.SENT in statuses
    assert NotificationDeliveryStatus.FAILED in statuses


def test_15_invalid_token_on_device2_only_disables_device2(test_env):
    svc: NotificationService = test_env["service"]
    device_repo: InMemoryUserDeviceRepository = test_env["device_repo"]
    client: FakeFirebaseMessagingClient = test_env["client"]

    token2 = "token_bad_device_02"
    device_repo.register_device(
        UserDevice(
            device_id="dev_reg_02",
            user_id="user_owner_01",
            fcm_token=token2,
            platform=DevicePlatform.IOS,
            is_enabled=True,
        )
    )
    client.invalid_tokens.add(token2)

    now = datetime(2026, 10, 27, 14, 25, 0, tzinfo=timezone.utc)
    event = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_01",
        timestamp=now,
        confidence=0.90,
        predator_type="owl",
    )
    svc.handle_ai_event(event)

    d1 = device_repo.get_by_id("dev_reg_01")
    d2 = device_repo.get_by_id("dev_reg_02")
    assert d1 is not None and d1.is_enabled is True
    assert d2 is not None and d2.is_enabled is False


def test_16_failed_device_does_not_prevent_in_app_notification(test_env):
    svc: NotificationService = test_env["service"]
    client: FakeFirebaseMessagingClient = test_env["client"]
    client.simulate_exception = RuntimeError("Complete FCM outage")

    now = datetime(2026, 10, 27, 14, 30, 0, tzinfo=timezone.utc)
    event = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_01",
        timestamp=now,
        confidence=0.91,
        predator_type="snake",
    )
    svc.handle_ai_event(event)

    notifs = svc.list_notifications("user_owner_01")
    in_app_notifs = [n for n in notifs if n.channel == NotificationChannel.IN_APP]
    assert len(in_app_notifs) == 1
    assert in_app_notifs[0].delivery_status == NotificationDeliveryStatus.SENT


# =============================================================================
# GROUP 3: Payload Structure & Sanitization Tests (Tests 17-25)
# =============================================================================

def test_17_all_payload_data_values_are_strings():
    raw_data = {
        "alertId": "alt_123",
        "count": 42,
        "ratio": 0.95,
        "isFlagged": True,
        "nullVal": None,
    }
    sanitized = sanitize_fcm_data(raw_data)
    assert "nullVal" not in sanitized
    for k, v in sanitized.items():
        assert isinstance(v, str), f"Key '{k}' has non-string value: {type(v)}"


def test_18_notification_title_and_body_match_alert(test_env):
    svc: NotificationService = test_env["service"]
    client: FakeFirebaseMessagingClient = test_env["client"]

    now = datetime(2026, 10, 27, 14, 35, 0, tzinfo=timezone.utc)
    event = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_01",
        timestamp=now,
        confidence=0.93,
        predator_type="rat",
    )
    alerts = svc.handle_ai_event(event)
    alert = alerts[0]

    assert len(client.sent_messages) == 1
    msg = client.sent_messages[0]
    assert msg["title"] == alert.title
    assert msg["body"] == alert.message


def test_19_required_payload_data_fields(test_env):
    svc: NotificationService = test_env["service"]
    client: FakeFirebaseMessagingClient = test_env["client"]

    now = datetime(2026, 10, 27, 14, 40, 0, tzinfo=timezone.utc)
    event = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_01",
        timestamp=now,
        confidence=0.88,
        predator_type="owl",
    )
    svc.handle_ai_event(event)

    msg = client.sent_messages[0]
    data = msg["data"]
    assert "alertId" in data
    assert "farmId" in data
    assert "eventType" in data
    assert "severity" in data
    assert data["farmId"] == "farm_001"
    assert data["eventType"] == "PREDATOR_DETECTED"
    assert data["severity"] == "CRITICAL"


def test_20_optional_payload_data_fields(test_env):
    svc: NotificationService = test_env["service"]
    client: FakeFirebaseMessagingClient = test_env["client"]

    now = datetime(2026, 10, 27, 14, 45, 0, tzinfo=timezone.utc)
    event = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_01",
        snapshot_url="https://storage.swiftletcare.com/snaps/owl_01.jpg",
        timestamp=now,
        confidence=0.95,
        predator_type="owl",
    )
    svc.handle_ai_event(event)

    data = client.sent_messages[0]["data"]
    assert data["zoneId"] == "zone_01"
    assert data["cameraId"] == "cam_01"
    assert data["snapshotUrl"] == "https://storage.swiftletcare.com/snaps/owl_01.jpg"


def test_21_local_filesystem_paths_stripped():
    raw_data = {
        "winPathC": "C:\\Users\\admin\\secret.jpg",
        "winPathD": "d:\\Development\\Projects\\data.json",
        "winPathE": "E:\\app\\logs\\trace.log",
        "linuxHome": "/home/ubuntu/app/photo.png",
        "linuxVar": "/var/log/syslog",
        "fileUri": "file:///path/to/snapshot.jpg",
        "validUrl": "https://cdn.swiftletcare.com/images/snap.jpg",
        "normalKey": "normalValue",
    }
    sanitized = sanitize_fcm_data(raw_data)
    assert "winPathC" not in sanitized
    assert "winPathD" not in sanitized
    assert "winPathE" not in sanitized
    assert "linuxHome" not in sanitized
    assert "linuxVar" not in sanitized
    assert "fileUri" not in sanitized
    assert sanitized["validUrl"] == "https://cdn.swiftletcare.com/images/snap.jpg"
    assert sanitized["normalKey"] == "normalValue"


def test_22_http_and_https_urls_preserved():
    data = {
        "httpUrl": "http://insecure.example.com/stream.m3u8",
        "httpsUrl": "https://secure.example.com/alerts/123.jpg",
    }
    sanitized = sanitize_fcm_data(data)
    assert sanitized["httpUrl"] == "http://insecure.example.com/stream.m3u8"
    assert sanitized["httpsUrl"] == "https://secure.example.com/alerts/123.jpg"


def test_23_no_raw_tokens_or_secrets_in_payload_data(test_env):
    svc: NotificationService = test_env["service"]
    client: FakeFirebaseMessagingClient = test_env["client"]

    now = datetime(2026, 10, 27, 14, 50, 0, tzinfo=timezone.utc)
    event = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_01",
        timestamp=now,
        confidence=0.92,
        predator_type="rat",
    )
    svc.handle_ai_event(event)

    data = client.sent_messages[0]["data"]
    # Ensure no token or credential keys leaked into message data
    for k, v in data.items():
        assert "token" not in k.lower()
        assert "secret" not in k.lower()
        assert "credential" not in k.lower()
        assert "private_key" not in v.lower()


def test_24_redacted_token_helper():
    assert redact_token(None) == "[EMPTY_TOKEN]"
    assert redact_token("") == "[EMPTY_TOKEN]"
    assert redact_token("12345") == "***"
    assert redact_token("12345678") == "***"
    assert redact_token("abcd1234wxyz") == "abcd...wxyz"
    assert redact_token("fcm_token_abcdefghij1234567890") == "fcm_...7890"


def test_25_primitive_types_cast_to_string_safely():
    data = {
        "int_field": 100,
        "float_field": 32.5,
        "bool_true": True,
        "bool_false": False,
    }
    sanitized = sanitize_fcm_data(data)
    assert sanitized == {
        "int_field": "100",
        "float_field": "32.5",
        "bool_true": "True",
        "bool_false": "False",
    }


# =============================================================================
# GROUP 4: Configuration & Factory Tests (Tests 26-32)
# =============================================================================

def test_26_factory_creates_mock_provider():
    settings = FCMSettings(provider="mock")
    provider = create_fcm_provider(settings=settings)
    assert isinstance(provider, MockFCMProvider)


def test_27_factory_creates_disabled_provider():
    settings = FCMSettings(provider="disabled")
    provider = create_fcm_provider(settings=settings)
    assert isinstance(provider, DisabledFCMProvider)


def test_28_factory_disabled_when_enabled_is_false():
    settings = FCMSettings(provider="mock", enabled=False)
    provider = create_fcm_provider(settings=settings)
    assert isinstance(provider, DisabledFCMProvider)


def test_29_factory_creates_firebase_provider_with_injected_client(fake_fcm_client: FakeFirebaseMessagingClient):
    settings = FCMSettings(provider="firebase", project_id="swiftletcare-test")
    provider = create_fcm_provider(settings=settings, client=fake_fcm_client)
    assert isinstance(provider, FirebaseFCMProvider)
    assert provider.client is fake_fcm_client


def test_30_disabled_provider_suppresses_send_without_raising():
    provider = DisabledFCMProvider()
    resp = provider.send_single("some_token", "Title", "Body", {})
    assert resp.success is False
    assert resp.error == "FCM push notification delivery is disabled"
    assert resp.invalid_tokens == []

    m_resp = provider.send_multicast(["t1", "t2"], "Title", "Body", {})
    assert m_resp.success is False
    assert m_resp.error == "FCM push notification delivery is disabled"


def test_31_real_client_validation_fails_without_credentials(monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv("FIREBASE_CREDENTIALS_PATH", raising=False)

    settings = FCMSettings(provider="firebase", credentials_path="nonexistent_service_account.json")
    with pytest.raises(ValueError, match="Firebase credentials file not found"):
        settings.validate_for_runtime()

    settings_no_cred = FCMSettings(provider="firebase", credentials_path=None)
    with pytest.raises(ValueError, match="requires 'FIREBASE_CREDENTIALS_PATH'"):
        settings_no_cred.validate_for_runtime()


def test_32_settings_from_env_parsing(monkeypatch):
    monkeypatch.setenv("FCM_PROVIDER", "firebase")
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "sc-prod-001")
    monkeypatch.setenv("FIREBASE_CREDENTIALS_PATH", "/etc/secrets/sa.json")

    settings = FCMSettings.from_env()
    assert settings.provider == "firebase"
    assert settings.enabled is True
    assert settings.project_id == "sc-prod-001"
    assert settings.credentials_path == "/etc/secrets/sa.json"

    monkeypatch.setenv("FCM_ENABLED", "false")
    monkeypatch.setenv("FCM_PROVIDER", "")
    settings_disabled = FCMSettings.from_env()
    assert settings_disabled.provider == "disabled"
    assert settings_disabled.enabled is False


# =============================================================================
# GROUP 5: Existing Semantics Regression & Integration (Tests 33-42)
# =============================================================================

def test_33_in_app_notification_created_unconditionally(test_env):
    svc: NotificationService = test_env["service"]
    device_repo: InMemoryUserDeviceRepository = test_env["device_repo"]
    client: FakeFirebaseMessagingClient = test_env["client"]

    # Delete all devices for user
    for dev in device_repo.list_by_user("user_owner_01", is_enabled_only=False):
        device_repo.disable_by_token(dev.fcm_token)

    now = datetime(2026, 10, 27, 15, 0, 0, tzinfo=timezone.utc)
    event = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_01",
        timestamp=now,
        confidence=0.91,
        predator_type="snake",
    )
    svc.handle_ai_event(event)

    # In-app notification must still be generated
    notifs = svc.list_notifications("user_owner_01")
    in_app = [n for n in notifs if n.channel == NotificationChannel.IN_APP]
    assert len(in_app) == 1
    assert in_app[0].delivery_status == NotificationDeliveryStatus.SENT
    assert len(client.sent_messages) == 0


def test_34_read_at_independent_of_delivery_status(test_env):
    svc: NotificationService = test_env["service"]
    now = datetime(2026, 10, 27, 15, 5, 0, tzinfo=timezone.utc)

    event = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_01",
        timestamp=now,
        confidence=0.95,
        predator_type="rat",
    )
    svc.handle_ai_event(event)

    notifs = svc.list_notifications("user_owner_01")
    in_app = next(n for n in notifs if n.channel == NotificationChannel.IN_APP)
    assert in_app.delivery_status == NotificationDeliveryStatus.SENT
    assert in_app.read_at is None
    assert in_app.is_read is False

    read_now = datetime(2026, 10, 27, 15, 6, 0, tzinfo=timezone.utc)
    updated = svc.mark_notification_as_read(
        notification_id=in_app.notification_id,
        user_id="user_owner_01",
        read_at=read_now,
    )
    assert updated.read_at == read_now
    assert updated.is_read is True
    # Delivery status must remain SENT, never mutated to READ
    assert updated.delivery_status == NotificationDeliveryStatus.SENT


def test_35_deduplication_suppresses_duplicate_alerts_and_fcm(test_env):
    svc: NotificationService = test_env["service"]
    client: FakeFirebaseMessagingClient = test_env["client"]

    t1 = datetime(2026, 10, 27, 15, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 10, 27, 15, 12, 0, tzinfo=timezone.utc)  # Within 10-minute cooldown

    e1 = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_01",
        timestamp=t1,
        confidence=0.94,
        predator_type="snake",
    )
    e2 = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_01",
        timestamp=t2,
        confidence=0.96,
        predator_type="snake",
    )

    alerts1 = svc.handle_ai_event(e1)
    alerts2 = svc.handle_ai_event(e2)

    assert len(alerts1) == 1
    assert len(alerts2) == 1
    assert alerts1[0].alert_id == alerts2[0].alert_id

    # Client must receive only 1 push message
    assert len(client.sent_messages) == 1


def test_36_resolved_alert_recurrence_creates_new_alert_and_dispatches_fcm(test_env):
    svc: NotificationService = test_env["service"]
    client: FakeFirebaseMessagingClient = test_env["client"]

    t1 = datetime(2026, 10, 27, 15, 20, 0, tzinfo=timezone.utc)
    e1 = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_01",
        timestamp=t1,
        confidence=0.94,
        predator_type="snake",
    )
    alerts1 = svc.handle_ai_event(e1)
    a1 = alerts1[0]

    # Resolve first alert
    svc.resolve_alert(a1.alert_id, resolved_by="user_owner_01", resolution_note="Cleared snake")

    # Second event occurs after resolution
    t2 = datetime(2026, 10, 27, 15, 25, 0, tzinfo=timezone.utc)
    e2 = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_01",
        timestamp=t2,
        confidence=0.96,
        predator_type="snake",
    )
    alerts2 = svc.handle_ai_event(e2)
    a2 = alerts2[0]

    assert a1.alert_id != a2.alert_id
    assert a2.status == AlertStatus.OPEN
    # FCM dispatched twice
    assert len(client.sent_messages) == 2


def test_37_hysteresis_auto_recovery(test_env):
    svc: NotificationService = test_env["service"]

    # 1. High temp breach -> Alert OPEN
    t1 = datetime(2026, 10, 27, 15, 30, 0, tzinfo=timezone.utc)
    te1 = IoTTelemetryAlertInputEvent(
        farm_id="farm_001",
        zone_id="zone_01",
        device_id="sensor_temp_01",
        timestamp=t1,
        temperature=36.0,  # > 31.0 threshold
        humidity=80.0,
    )
    triggered, resolved = svc.handle_telemetry_event(te1)
    assert len(triggered) == 1
    assert len(resolved) == 0
    alert = triggered[0]
    assert alert.status == AlertStatus.OPEN

    # 2. Temperature normalizes below hysteresis (<= 30.5) -> Alert Auto-RESOLVED
    t2 = datetime(2026, 10, 27, 15, 32, 0, tzinfo=timezone.utc)
    te2 = IoTTelemetryAlertInputEvent(
        farm_id="farm_001",
        zone_id="zone_01",
        device_id="sensor_temp_01",
        timestamp=t2,
        temperature=29.0,  # <= 30.5 recovery threshold
        humidity=80.0,
    )
    triggered2, resolved2 = svc.handle_telemetry_event(te2)
    assert len(triggered2) == 0
    assert len(resolved2) == 1
    assert resolved2[0].alert_id == alert.alert_id
    assert resolved2[0].status == AlertStatus.RESOLVED


def test_38_device_offline_online_lifecycle(test_env):
    svc: NotificationService = test_env["service"]

    # 1. OFFLINE -> Triggers DEVICE_OFFLINE Alert
    t1 = datetime(2026, 10, 27, 15, 35, 0, tzinfo=timezone.utc)
    pe1 = IoTPresenceAlertInputEvent(
        farm_id="farm_001",
        device_id="iot_gateway_01",
        status="OFFLINE",
        timestamp=t1,
        status_reason="Heartbeat timeout",
    )
    trig1, res1 = svc.handle_presence_event(pe1)
    assert len(trig1) == 1
    assert len(res1) == 0
    assert trig1[0].event_type == AlertEventType.DEVICE_OFFLINE

    # 2. ONLINE -> Auto-resolves DEVICE_OFFLINE Alert
    t2 = datetime(2026, 10, 27, 15, 37, 0, tzinfo=timezone.utc)
    pe2 = IoTPresenceAlertInputEvent(
        farm_id="farm_001",
        device_id="iot_gateway_01",
        status="ONLINE",
        timestamp=t2,
    )
    trig2, res2 = svc.handle_presence_event(pe2)
    assert len(trig2) == 0
    assert len(res2) == 1
    assert res2[0].status == AlertStatus.RESOLVED


def test_39_command_failed_requires_human_resolution(test_env):
    svc: NotificationService = test_env["service"]

    t1 = datetime(2026, 10, 27, 15, 40, 0, tzinfo=timezone.utc)
    ce = IoTCommandAlertInputEvent(
        command_id="cmd_pump_fail_01",
        farm_id="farm_001",
        zone_id="zone_01",
        device_id="actuator_pump_01",
        command_type="START_PUMP",
        status="FAILED",
        failure_reason="Motor stalled",
        timestamp=t1,
    )
    alerts = svc.handle_command_event(ce)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.event_type == AlertEventType.COMMAND_FAILED
    assert alert.status == AlertStatus.OPEN

    # Telemetry cannot auto-resolve command errors
    te = IoTTelemetryAlertInputEvent(
        farm_id="farm_001",
        zone_id="zone_01",
        device_id="actuator_pump_01",
        timestamp=datetime(2026, 10, 27, 15, 42, 0, tzinfo=timezone.utc),
        temperature=28.0,
        humidity=75.0,
    )
    _, res = svc.handle_telemetry_event(te)
    assert len(res) == 0

    # Must be resolved by operator
    resolved = svc.resolve_alert(alert.alert_id, resolved_by="user_operator", resolution_note="Pump unstuck")
    assert resolved.status == AlertStatus.RESOLVED


def test_40_predator_critical_requires_human_resolution(test_env):
    svc: NotificationService = test_env["service"]

    now = datetime(2026, 10, 27, 15, 45, 0, tzinfo=timezone.utc)
    event = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_01",
        timestamp=now,
        confidence=0.98,
        predator_type="snake",
    )
    alerts = svc.handle_ai_event(event)
    alert = alerts[0]
    assert alert.status == AlertStatus.OPEN

    resolved = svc.resolve_alert(alert.alert_id, resolved_by="user_owner_01", resolution_note="Trap placed")
    assert resolved.status == AlertStatus.RESOLVED


def test_41_realtime_websocket_event_published_alongside_fcm(test_env):
    svc: NotificationService = test_env["service"]
    ws_manager: NotificationWebSocketManager = test_env["ws_manager"]
    client: FakeFirebaseMessagingClient = test_env["client"]

    published_events = []
    def mock_send_user(user_id, env):
        published_events.append((user_id, env))
    ws_manager.send_to_user_from_sync = mock_send_user

    now = datetime(2026, 10, 27, 15, 50, 0, tzinfo=timezone.utc)
    event = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_01",
        timestamp=now,
        confidence=0.97,
        predator_type="owl",
    )
    svc.handle_ai_event(event)

    # Verify both FCM client and WS dispatch were triggered
    assert len(client.sent_messages) == 1
    assert len(published_events) >= 1
    users = [u for u, e in published_events]
    assert "user_owner_01" in users


def test_42_end_to_end_event_ingestion_with_firebase_provider(test_env):
    svc: NotificationService = test_env["service"]
    client: FakeFirebaseMessagingClient = test_env["client"]
    alert_repo: InMemoryAlertRepository = test_env["alert_repo"]
    notif_repo: InMemoryNotificationRepository = test_env["notif_repo"]

    now = datetime(2026, 10, 27, 15, 55, 0, tzinfo=timezone.utc)
    event = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_nesting_a",
        camera_id="cam_nesting_01",
        snapshot_url="https://media.swiftletcare.com/snaps/owl_alert.jpg",
        timestamp=now,
        confidence=0.99,
        predator_type="owl",
    )

    alerts = svc.handle_ai_event(event)
    assert len(alerts) == 1
    alert = alerts[0]

    # Verify Alert in repository
    saved_alert = alert_repo.get_by_id(alert.alert_id)
    assert saved_alert is not None
    assert saved_alert.severity == AlertSeverity.CRITICAL

    # Verify IN_APP and FCM notifications in repository
    user_notifs = notif_repo.list_by_user("user_owner_01")
    assert len(user_notifs) == 2

    in_app = next(n for n in user_notifs if n.channel == NotificationChannel.IN_APP)
    assert in_app.delivery_status == NotificationDeliveryStatus.SENT

    fcm = next(n for n in user_notifs if n.channel == NotificationChannel.FCM)
    assert fcm.delivery_status == NotificationDeliveryStatus.SENT

    # Verify Firebase client dispatch
    assert len(client.sent_messages) == 1
    sent_msg = client.sent_messages[0]
    assert sent_msg["token"] == "token_device_alpha_1234"
    assert sent_msg["data"]["snapshotUrl"] == "https://media.swiftletcare.com/snaps/owl_alert.jpg"
