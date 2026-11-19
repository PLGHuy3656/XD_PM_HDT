"""WebSocket implementation of NotificationDomainEventSink (CP6.3)."""
from __future__ import annotations

from typing import Any, Dict

from app.ports.event_sink import NotificationDomainEventSink
from app.schemas.canonical import Alert, Notification
from app.websocket.manager import (
    NotificationWebSocketManager,
    build_ws_envelope,
)


class WebSocketNotificationEventSink(NotificationDomainEventSink):
    """Bridges domain lifecycle events to WebSocket clients via NotificationWebSocketManager."""

    def __init__(self, ws_manager: NotificationWebSocketManager) -> None:
        self.ws_manager = ws_manager

    def on_alert_created(self, alert: Alert) -> None:
        envelope = build_ws_envelope(
            "alert.created",
            alert.model_dump(by_alias=True),
        )
        self.ws_manager.broadcast_from_sync(envelope)

    def on_alert_updated(self, alert: Alert) -> None:
        envelope = build_ws_envelope(
            "alert.updated",
            alert.model_dump(by_alias=True),
        )
        self.ws_manager.broadcast_from_sync(envelope)

    def on_notification_created(self, notification: Notification) -> None:
        envelope = build_ws_envelope(
            "notification.created",
            notification.model_dump(by_alias=True),
        )
        # Scoped strictly to the specific recipient user!
        self.ws_manager.send_to_user_from_sync(notification.user_id, envelope)

    def on_notification_updated(self, notification: Notification) -> None:
        envelope = build_ws_envelope(
            "notification.updated",
            notification.model_dump(by_alias=True),
        )
        # Scoped strictly to the specific recipient user!
        self.ws_manager.send_to_user_from_sync(notification.user_id, envelope)


__all__ = ["WebSocketNotificationEventSink"]
