"""RabbitMQ domain event publisher adapter for AI Service."""
from __future__ import annotations

import json
import logging
from typing import Optional

import aio_pika

from app.domain_events.constants import CANONICAL_EXCHANGE
from app.domain_events.envelope import DomainEvent
from app.infrastructure.rabbitmq.connection import RabbitMQConnectionManager
from app.ports.domain_event_publisher import DomainEventPublisher

logger = logging.getLogger("ai_service.infrastructure.rabbitmq.publisher")


class RabbitMQEventPublisher(DomainEventPublisher):
    """Infrastructure adapter that publishes DomainEvents to RabbitMQ topic exchange.

    Reliability Characteristics:
    - Durable topology: Declares durable topic exchange ('swiftlet.domain.events').
    - Persistent delivery: DeliveryMode.PERSISTENT marks messages to be written to disk by broker.
    - Publisher confirms: Awaits broker ACK confirming message receipt before returning.
    - No transactional outbox: Without a transactional outbox or persistent queue buffer,
      events emitted during broker outage are logged as failed and dropped. Delivery is
      at-most-once across outage windows, and there is NO exactly-once guarantee.
    - Fault isolation: Broker failures increment failure counters and log diagnostics
      without crashing the video processing pipeline.
    """

    def __init__(
        self,
        connection_manager: Optional[RabbitMQConnectionManager] = None,
        host: str = "127.0.0.1",
        port: int = 5672,
        user: str = "swiftlet",
        password: str = "swiftlet123",
        vhost: str = "/",
        exchange_name: str = CANONICAL_EXCHANGE,
    ) -> None:
        self.connection_manager = connection_manager or RabbitMQConnectionManager(
            host=host,
            port=port,
            user=user,
            password=password,
            vhost=vhost,
            exchange_name=exchange_name,
        )
        self.published_count: int = 0
        self.failed_count: int = 0
        self.last_error: Optional[str] = None

    async def connect(self) -> None:
        """Connects to RabbitMQ."""
        await self.connection_manager.connect()

    async def close(self) -> None:
        """Closes RabbitMQ connection."""
        await self.connection_manager.close()

    @property
    def is_connected(self) -> bool:
        return self.connection_manager.is_connected

    async def publish(self, event: DomainEvent) -> None:
        """Publishes a DomainEvent to the canonical topic exchange with publisher confirm."""
        routing_key = event.event_type
        payload_dict = event.to_dict()
        body_bytes = json.dumps(payload_dict).encode("utf-8")

        message = aio_pika.Message(
            body=body_bytes,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            message_id=event.event_id,
            type=event.event_type,
            correlation_id=event.correlation_id,
        )

        try:
            exchange = await self.connection_manager.get_exchange()
            await exchange.publish(message, routing_key=routing_key)
            self.published_count += 1
            self.last_error = None
            logger.info(
                "[AI RABBITMQ PUBLISHED] eventId='%s' eventType='%s' routingKey='%s'",
                event.event_id,
                event.event_type,
                routing_key,
            )
        except Exception as exc:
            self.failed_count += 1
            self.last_error = str(exc)
            logger.error(
                "[AI RABBITMQ PUBLISH FAILED] eventId='%s' eventType='%s' error: %s",
                event.event_id,
                event.event_type,
                exc,
                exc_info=True,
            )


__all__ = ["RabbitMQEventPublisher"]
