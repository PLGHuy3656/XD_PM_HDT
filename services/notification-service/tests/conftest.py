import pytest
from fastapi.testclient import TestClient

from app.config.alert_rules import AlertRuleConfig, InMemoryAlertRuleConfigProvider
from app.database import get_connection
from app.dependencies import (
    get_notification_service,
    get_recipient_resolver,
    get_rule_config_provider,
    get_user_device_repo,
    get_ws_manager,
    reset_app_state,
)
from app.domain.enums import DevicePlatform
from app.main import app
from app.ports.recipient_resolver import RecipientInfo
from app.repositories.in_memory_alert_repo import InMemoryAlertRepository
from app.repositories.in_memory_notification_repo import InMemoryNotificationRepository
from app.repositories.in_memory_user_device_repo import InMemoryUserDeviceRepository
from app.schemas.canonical import UserDevice
from app.services.alert_lifecycle_service import AlertLifecycleService
from app.services.alert_rule_engine import AlertRuleEngine
from app.services.in_memory_recipient_resolver import InMemoryRecipientResolver
from app.services.mock_fcm_provider import MockFCMProvider
from app.services.notification_service import NotificationService
from app.websocket.manager import NotificationWebSocketManager


@pytest.fixture(autouse=True)
def _clean_notification_db():
    """Ensure clean PostgreSQL notification_db tables before and after each test."""
    try:
        with get_connection(autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE notifications, alerts, user_devices RESTART IDENTITY CASCADE")
    except Exception:
        pass
    yield
    try:
        with get_connection(autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE notifications, alerts, user_devices RESTART IDENTITY CASCADE")
    except Exception:
        pass


@pytest.fixture
def alert_repo() -> InMemoryAlertRepository:
    return InMemoryAlertRepository()


@pytest.fixture
def notification_repo() -> InMemoryNotificationRepository:
    return InMemoryNotificationRepository()


@pytest.fixture
def user_device_repo() -> InMemoryUserDeviceRepository:
    return InMemoryUserDeviceRepository()


@pytest.fixture
def rule_config_provider() -> InMemoryAlertRuleConfigProvider:
    provider = InMemoryAlertRuleConfigProvider()
    provider.set_rules_for_farm(
        "farm_001",
        AlertRuleConfig(
            farm_id="farm_001",
            high_temp_celsius=31.0,
            high_temp_recovery_celsius=30.5,
            low_temp_celsius=27.0,
            low_temp_recovery_celsius=27.5,
            high_humidity_pct=85.0,
            high_humidity_recovery_pct=82.0,
            low_humidity_pct=70.0,
            low_humidity_recovery_pct=73.0,
        ),
    )
    return provider


@pytest.fixture
def recipient_resolver() -> InMemoryRecipientResolver:
    resolver = InMemoryRecipientResolver()
    resolver.register_recipient(
        "farm_001",
        RecipientInfo(
            user_id="user_owner_01",
            email="owner@farm001.com",
            roles=["FARM_OWNER"],
        ),
    )
    return resolver


@pytest.fixture
def fcm_provider() -> MockFCMProvider:
    return MockFCMProvider()


@pytest.fixture
def lifecycle_service(alert_repo: InMemoryAlertRepository) -> AlertLifecycleService:
    return AlertLifecycleService(alert_repo=alert_repo)


@pytest.fixture
def rule_engine(rule_config_provider: InMemoryAlertRuleConfigProvider) -> AlertRuleEngine:
    return AlertRuleEngine(config_provider=rule_config_provider)


@pytest.fixture
def notification_service(
    alert_repo: InMemoryAlertRepository,
    notification_repo: InMemoryNotificationRepository,
    user_device_repo: InMemoryUserDeviceRepository,
    rule_config_provider: InMemoryAlertRuleConfigProvider,
    recipient_resolver: InMemoryRecipientResolver,
    fcm_provider: MockFCMProvider,
) -> NotificationService:
    user_device_repo.register_device(
        UserDevice(
            device_id="dev_phone_01",
            user_id="user_owner_01",
            fcm_token="token_owner_android_01",
            platform=DevicePlatform.ANDROID,
            is_enabled=True,
        )
    )

    return NotificationService(
        alert_repo=alert_repo,
        notification_repo=notification_repo,
        user_device_repo=user_device_repo,
        rule_config_provider=rule_config_provider,
        recipient_resolver=recipient_resolver,
        fcm_provider=fcm_provider,
    )


@pytest.fixture
def client():
    """TestClient fixture with isolated app state for REST and WebSocket tests."""
    reset_app_state()
    rule_provider = get_rule_config_provider()
    rule_provider.set_rules_for_farm(
        "farm_001",
        AlertRuleConfig(
            farm_id="farm_001",
            high_temp_celsius=31.0,
            high_temp_recovery_celsius=30.5,
            low_temp_celsius=27.0,
            low_temp_recovery_celsius=27.5,
            high_humidity_pct=85.0,
            high_humidity_recovery_pct=82.0,
            low_humidity_pct=70.0,
            low_humidity_recovery_pct=73.0,
        ),
    )
    resolver = get_recipient_resolver()
    resolver.register_recipient(
        "farm_001",
        RecipientInfo(user_id="USER-01", email="user01@farm.com", roles=["OPERATOR"]),
    )
    dev_repo = get_user_device_repo()
    dev_repo.register_device(
        UserDevice(
            device_id="dev_phone_user01",
            user_id="USER-01",
            fcm_token="token_user01_fcm",
            platform=DevicePlatform.ANDROID,
            is_enabled=True,
        )
    )

    with TestClient(app) as tc:
        yield tc
