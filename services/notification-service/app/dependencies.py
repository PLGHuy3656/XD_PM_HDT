"""Dependency injection container and state management for FastAPI (CP6.3)."""
from __future__ import annotations

import threading
from typing import Optional

from app.config.alert_rules import AlertRuleConfig, AlertRuleConfigProvider, InMemoryAlertRuleConfigProvider
from app.infrastructure.firebase.client import FirebaseMessagingClient
from app.infrastructure.firebase.config import FCMSettings
from app.infrastructure.firebase.factory import create_fcm_provider
from app.ports.alert_repository import AlertRepository
from app.ports.fcm_provider import FCMProvider
from app.ports.notification_repository import NotificationRepository
from app.ports.recipient_resolver import RecipientInfo, RecipientResolver
from app.ports.user_device_repository import UserDeviceRepository
from app.repositories.in_memory_alert_repo import InMemoryAlertRepository
from app.repositories.in_memory_notification_repo import InMemoryNotificationRepository
from app.repositories.in_memory_user_device_repo import InMemoryUserDeviceRepository
from app.repositories.postgres_alert_repo import PostgreSQLAlertRepository
from app.repositories.postgres_notification_repo import PostgreSQLNotificationRepository
from app.repositories.postgres_user_device_repo import PostgreSQLUserDeviceRepository
from app.services.in_memory_recipient_resolver import InMemoryRecipientResolver
from app.services.mock_fcm_provider import MockFCMProvider
from app.services.notification_service import NotificationService
from app.websocket.manager import NotificationWebSocketManager
from app.websocket.sink import WebSocketNotificationEventSink

_lock = threading.RLock()

_alert_repo: Optional[AlertRepository] = None
_notification_repo: Optional[NotificationRepository] = None
_user_device_repo: Optional[UserDeviceRepository] = None
_rule_config_provider: Optional[AlertRuleConfigProvider] = None
_recipient_resolver: Optional[RecipientResolver] = None
_fcm_provider: Optional[FCMProvider] = None
_ws_manager: Optional[NotificationWebSocketManager] = None
_ws_sink: Optional[WebSocketNotificationEventSink] = None
_notification_service: Optional[NotificationService] = None


def init_app_state(
    alert_repo: Optional[AlertRepository] = None,
    notification_repo: Optional[NotificationRepository] = None,
    user_device_repo: Optional[UserDeviceRepository] = None,
    rule_config_provider: Optional[AlertRuleConfigProvider] = None,
    recipient_resolver: Optional[RecipientResolver] = None,
    fcm_provider: Optional[FCMProvider] = None,
    fcm_settings: Optional[FCMSettings] = None,
    fcm_client: Optional[FirebaseMessagingClient] = None,
    ws_manager: Optional[NotificationWebSocketManager] = None,
) -> NotificationService:
    """Initialize or inject application state and dependencies."""
    global _alert_repo, _notification_repo, _user_device_repo
    global _rule_config_provider, _recipient_resolver, _fcm_provider
    global _ws_manager, _ws_sink, _notification_service

    with _lock:
        _alert_repo = alert_repo or PostgreSQLAlertRepository()
        _notification_repo = notification_repo or PostgreSQLNotificationRepository()
        _user_device_repo = user_device_repo or PostgreSQLUserDeviceRepository()
        _rule_config_provider = rule_config_provider or InMemoryAlertRuleConfigProvider()
        _recipient_resolver = recipient_resolver or InMemoryRecipientResolver()
        if fcm_provider is not None:
            _fcm_provider = fcm_provider
        else:
            _fcm_provider = create_fcm_provider(settings=fcm_settings, client=fcm_client)
        _ws_manager = ws_manager or NotificationWebSocketManager()

        _ws_sink = WebSocketNotificationEventSink(ws_manager=_ws_manager)

        _notification_service = NotificationService(
            alert_repo=_alert_repo,
            notification_repo=_notification_repo,
            user_device_repo=_user_device_repo,
            rule_config_provider=_rule_config_provider,
            recipient_resolver=_recipient_resolver,
            fcm_provider=_fcm_provider,
            event_sink=_ws_sink,
        )

        return _notification_service


def reset_app_state() -> None:
    """Reset all in-memory state (used in test fixtures)."""
    init_app_state()


def get_notification_service() -> NotificationService:
    global _notification_service
    if _notification_service is None:
        init_app_state()
    assert _notification_service is not None
    return _notification_service


def get_alert_repo() -> AlertRepository:
    global _alert_repo
    if _alert_repo is None:
        init_app_state()
    assert _alert_repo is not None
    return _alert_repo


def get_notification_repo() -> NotificationRepository:
    global _notification_repo
    if _notification_repo is None:
        init_app_state()
    assert _notification_repo is not None
    return _notification_repo


def get_user_device_repo() -> UserDeviceRepository:
    global _user_device_repo
    if _user_device_repo is None:
        init_app_state()
    assert _user_device_repo is not None
    return _user_device_repo


def get_rule_config_provider() -> AlertRuleConfigProvider:
    global _rule_config_provider
    if _rule_config_provider is None:
        init_app_state()
    assert _rule_config_provider is not None
    return _rule_config_provider


def get_recipient_resolver() -> RecipientResolver:
    global _recipient_resolver
    if _recipient_resolver is None:
        init_app_state()
    assert _recipient_resolver is not None
    return _recipient_resolver


def get_fcm_provider() -> FCMProvider:
    global _fcm_provider
    if _fcm_provider is None:
        init_app_state()
    assert _fcm_provider is not None
    return _fcm_provider


def get_ws_manager() -> NotificationWebSocketManager:
    global _ws_manager
    if _ws_manager is None:
        init_app_state()
    assert _ws_manager is not None
    return _ws_manager


__all__ = [
    "init_app_state",
    "reset_app_state",
    "get_notification_service",
    "get_alert_repo",
    "get_notification_repo",
    "get_user_device_repo",
    "get_rule_config_provider",
    "get_recipient_resolver",
    "get_fcm_provider",
    "get_ws_manager",
]
