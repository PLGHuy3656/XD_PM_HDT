"""Domain Event Publisher Abstraction & Implementations for IoT Service (CP7.2).

Publishes CanonicalDomainEvent objects to swiftlet.domain.events topic exchange.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
import logging
from typing import Any

from app.domain_events.canonical import CanonicalDomainEvent

logger = logging.getLogger("iot_service.domain_events")


class DomainEventPublisher(ABC):
    """Abstract port for publishing IoT domain events."""

    @abstractmethod
    def publish(self, event: CanonicalDomainEvent) -> bool:
        """Publishes a canonical domain event. Returns True on success, False on failure."""
        raise NotImplementedError


class NoOpDomainEventPublisher(DomainEventPublisher):
    """Publisher used when RabbitMQ is disabled (RABBITMQ_ENABLED=false)."""

    def publish(self, event: CanonicalDomainEvent) -> bool:
        logger.debug(
            "[DOMAIN EVENT NOOP] Event '%s' of type '%s' suppressed (RabbitMQ disabled)",
            event.eventId,
            event.eventType,
        )
        return True


class InMemoryDomainEventPublisher(DomainEventPublisher):
    """Publisher used in testing to inspect and verify emitted events."""

    def __init__(self):
        self.published_events: list[CanonicalDomainEvent] = []

    def publish(self, event: CanonicalDomainEvent) -> bool:
        self.published_events.append(event)
        logger.info(
            "[DOMAIN EVENT IN-MEMORY] Emitted '%s' (%s)",
            event.eventType,
            event.eventId,
        )
        return True

    def clear(self) -> None:
        self.published_events.clear()

    @property
    def event_types(self) -> list[str]:
        return [e.eventType for e in self.published_events]


class RabbitMQEventPublisher(DomainEventPublisher):
    """Publisher publishing to RabbitMQ swiftlet.domain.events exchange.

    Falls back safely if RabbitMQ is not installed or unreachable.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5672,
        user: str = "swiftlet",
        password: str = "swiftlet123",
        exchange: str = "swiftlet.domain.events",
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.exchange = exchange
        self._connection = None
        self._channel = None

    def publish(self, event: CanonicalDomainEvent) -> bool:
        try:
            import pika

            credentials = pika.PlainCredentials(self.user, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=credentials,
                connection_attempts=1,
                retry_delay=1,
                socket_timeout=3,
            )

            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            channel.confirm_delivery()

            body = json.dumps(event.model_dump())
            routing_key = event.eventType

            channel.basic_publish(
                exchange=self.exchange,
                routing_key=routing_key,
                body=body.encode("utf-8"),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,  # Persistent
                ),
            )
            connection.close()
            logger.info(
                "[DOMAIN EVENT PUBLISHED] Routing key '%s' eventId '%s'",
                routing_key,
                event.eventId,
            )
            return True
        except Exception as exc:
            logger.warning(
                "[DOMAIN EVENT PUBLISH ERROR] Failed to publish event '%s' (%s): %s",
                event.eventType,
                event.eventId,
                exc,
            )
            return False


def get_default_publisher() -> DomainEventPublisher:
    """Factory selecting publisher based on configuration."""
    import os

    rabbitmq_enabled = os.getenv("RABBITMQ_ENABLED", "false").lower() == "true"
    if rabbitmq_enabled:
        return RabbitMQEventPublisher(
            host=os.getenv("RABBITMQ_HOST", "127.0.0.1"),
            port=int(os.getenv("RABBITMQ_PORT", "5672")),
            user=os.getenv("RABBITMQ_USER", "swiftlet"),
            password=os.getenv("RABBITMQ_PASSWORD", "swiftlet123"),
            exchange=os.getenv("RABBITMQ_EXCHANGE", "swiftlet.domain.events"),
        )
    return NoOpDomainEventPublisher()


default_domain_event_publisher: DomainEventPublisher = get_default_publisher()
