"""Declarative topology definitions for SwiftletCare RabbitMQ infrastructure (CP7.1)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from infrastructure.rabbitmq.constants import (
    DEFAULT_RETRY_TTL_MS,
    EXCHANGE_DOMAIN_EVENTS,
    EXCHANGE_NOTIFICATION_DLX,
    EXCHANGE_NOTIFICATION_RETRY,
    EXCHANGE_NOTIFICATION_RETRY_RETURN,
    NOTIFICATION_BINDING_PATTERNS,
    QUEUE_NOTIFICATION_DLQ,
    QUEUE_NOTIFICATION_MAIN,
    QUEUE_NOTIFICATION_RETRY,
    ROUTING_KEY_DLQ,
    ROUTING_KEY_RETRY_QUEUE,
    ROUTING_KEY_RETRY_RETURN,
)


@dataclass(frozen=True)
class ExchangeDefinition:
    name: str
    type: str  # topic, direct, fanout
    durable: bool = True
    auto_delete: bool = False
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QueueDefinition:
    name: str
    durable: bool = True
    auto_delete: bool = False
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BindingDefinition:
    source_exchange: str
    destination_queue: str
    routing_key: str
    arguments: Dict[str, Any] = field(default_factory=dict)


def get_v1_topology(retry_ttl_ms: int = DEFAULT_RETRY_TTL_MS) -> Dict[str, Any]:
    """Return complete V1 RabbitMQ topology definition (TV4 Integration Ownership)."""

    exchanges = [
        # 1. Main Domain Topic Exchange
        ExchangeDefinition(
            name=EXCHANGE_DOMAIN_EVENTS,
            type="topic",
            durable=True,
            auto_delete=False,
        ),
        # 2. Notification Retry Exchange (Direct)
        ExchangeDefinition(
            name=EXCHANGE_NOTIFICATION_RETRY,
            type="direct",
            durable=True,
            auto_delete=False,
        ),
        # 3. Notification Retry-Return Exchange (Direct)
        ExchangeDefinition(
            name=EXCHANGE_NOTIFICATION_RETRY_RETURN,
            type="direct",
            durable=True,
            auto_delete=False,
        ),
        # 4. Notification Dead Letter Exchange (Direct)
        ExchangeDefinition(
            name=EXCHANGE_NOTIFICATION_DLX,
            type="direct",
            durable=True,
            auto_delete=False,
        ),
    ]

    queues = [
        # 1. Main Notification Queue (with dead-lettering to DLX upon rejection)
        QueueDefinition(
            name=QUEUE_NOTIFICATION_MAIN,
            durable=True,
            auto_delete=False,
            arguments={
                "x-dead-letter-exchange": EXCHANGE_NOTIFICATION_DLX,
                "x-dead-letter-routing-key": ROUTING_KEY_DLQ,
            },
        ),
        # 2. Retry Queue with dead-lettering back to Retry-Return exchange upon TTL expiration
        QueueDefinition(
            name=QUEUE_NOTIFICATION_RETRY,
            durable=True,
            auto_delete=False,
            arguments={
                "x-message-ttl": retry_ttl_ms,
                "x-dead-letter-exchange": EXCHANGE_NOTIFICATION_RETRY_RETURN,
                "x-dead-letter-routing-key": ROUTING_KEY_RETRY_RETURN,
            },
        ),
        # 3. Dead Letter Queue for permanently failed messages
        QueueDefinition(
            name=QUEUE_NOTIFICATION_DLQ,
            durable=True,
            auto_delete=False,
            arguments={},
        ),
    ]

    bindings = [
        # Bind Main Queue to Domain Events Exchange with canonical condition patterns
        *[
            BindingDefinition(
                source_exchange=EXCHANGE_DOMAIN_EVENTS,
                destination_queue=QUEUE_NOTIFICATION_MAIN,
                routing_key=pattern,
            )
            for pattern in NOTIFICATION_BINDING_PATTERNS
        ],
        # Bind Retry Queue to Retry Exchange
        BindingDefinition(
            source_exchange=EXCHANGE_NOTIFICATION_RETRY,
            destination_queue=QUEUE_NOTIFICATION_RETRY,
            routing_key=ROUTING_KEY_RETRY_QUEUE,
        ),
        # Bind Main Queue to Retry-Return Exchange (Allows expired retry messages to return cleanly!)
        BindingDefinition(
            source_exchange=EXCHANGE_NOTIFICATION_RETRY_RETURN,
            destination_queue=QUEUE_NOTIFICATION_MAIN,
            routing_key=ROUTING_KEY_RETRY_RETURN,
        ),
        # Bind DLQ to DLX
        BindingDefinition(
            source_exchange=EXCHANGE_NOTIFICATION_DLX,
            destination_queue=QUEUE_NOTIFICATION_DLQ,
            routing_key=ROUTING_KEY_DLQ,
        ),
    ]

    return {
        "exchanges": exchanges,
        "queues": queues,
        "bindings": bindings,
    }


__all__ = [
    "ExchangeDefinition",
    "QueueDefinition",
    "BindingDefinition",
    "get_v1_topology",
]
