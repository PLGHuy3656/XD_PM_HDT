"""Factory and singleton providers for RabbitMQ components in AI Service."""
from __future__ import annotations

from app.config import settings
from app.infrastructure.rabbitmq.connection import RabbitMQConnectionManager
from app.infrastructure.rabbitmq.publisher import RabbitMQEventPublisher
from app.ports.domain_event_publisher import (
    DomainEventPublisher,
    noop_domain_event_publisher,
)

rabbitmq_connection_manager = RabbitMQConnectionManager(
    host=settings.rabbitmq_host,
    port=settings.rabbitmq_port,
    user=settings.rabbitmq_user,
    password=settings.rabbitmq_password,
    vhost=settings.rabbitmq_vhost,
    exchange_name=settings.rabbitmq_exchange,
)

rabbitmq_event_publisher = RabbitMQEventPublisher(
    connection_manager=rabbitmq_connection_manager,
    host=settings.rabbitmq_host,
    port=settings.rabbitmq_port,
    user=settings.rabbitmq_user,
    password=settings.rabbitmq_password,
    vhost=settings.rabbitmq_vhost,
    exchange_name=settings.rabbitmq_exchange,
)


def get_domain_event_publisher() -> DomainEventPublisher:
    """Returns RabbitMQEventPublisher when rabbitmq_enabled is True, else NoOpDomainEventPublisher."""
    if settings.rabbitmq_enabled:
        return rabbitmq_event_publisher
    return noop_domain_event_publisher


__all__ = [
    "get_domain_event_publisher",
    "rabbitmq_connection_manager",
    "rabbitmq_event_publisher",
]
