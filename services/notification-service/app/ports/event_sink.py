"""Transport-neutral domain event sink port for Alert & Notification Service (CP6.3)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from app.schemas.canonical import Alert, Notification


class NotificationDomainEventSink(ABC):
    """Abstract sink for domain lifecycle events.

    Decouples domain logic from transports (WebSocket, RabbitMQ, etc.).
    """

    def on_alert_created(self, alert: Alert) -> None:
        """Called when a new alert is created and opened."""
        pass

    def on_alert_updated(self, alert: Alert) -> None:
        """Called when an alert is updated (deduplication, ack, resolution)."""
        pass

    def on_notification_created(self, notification: Notification) -> None:
        """Called when a new notification is generated."""
        pass

    def on_notification_updated(self, notification: Notification) -> None:
        """Called when a notification is updated (read, status change)."""
        pass


class CompositeNotificationDomainEventSink(NotificationDomainEventSink):
    """Multiplexes domain events to multiple sinks."""

    def __init__(self, sinks: Optional[List[NotificationDomainEventSink]] = None) -> None:
        self._sinks: List[NotificationDomainEventSink] = list(sinks or [])

    def add_sink(self, sink: NotificationDomainEventSink) -> None:
        self._sinks.append(sink)

    def on_alert_created(self, alert: Alert) -> None:
        for sink in self._sinks:
            sink.on_alert_created(alert)

    def on_alert_updated(self, alert: Alert) -> None:
        for sink in self._sinks:
            sink.on_alert_updated(alert)

    def on_notification_created(self, notification: Notification) -> None:
        for sink in self._sinks:
            sink.on_notification_created(notification)

    def on_notification_updated(self, notification: Notification) -> None:
        for sink in self._sinks:
            sink.on_notification_updated(notification)


__all__ = [
    "NotificationDomainEventSink",
    "CompositeNotificationDomainEventSink",
]
