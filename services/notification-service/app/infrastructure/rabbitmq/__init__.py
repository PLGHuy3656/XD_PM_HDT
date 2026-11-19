"""RabbitMQ infrastructure consumer package for Alert & Notification Service (CP7.4 / CP7.5)."""
from app.infrastructure.rabbitmq.config import RabbitMQSettings, RedisSettings
from app.infrastructure.rabbitmq.connection import RabbitMQConnectionManager
from app.infrastructure.rabbitmq.consumer import RabbitMQAlertConsumer
from app.infrastructure.rabbitmq.envelope import (
    CanonicalEnvelope,
    PermanentEnvelopeError,
    ProducerMismatchError,
    UnsupportedVersionError,
)
from app.infrastructure.rabbitmq.factory import (
    create_idempotency_store,
    create_rabbitmq_consumer,
    get_rabbitmq_consumer,
    reset_rabbitmq_consumer,
)
from app.infrastructure.rabbitmq.idempotency import (
    IdempotencyStore,
    InMemoryIdempotencyStore,
    RedisIdempotencyStore,
    default_idempotency_store,
)
from app.infrastructure.rabbitmq.mapper import EventMapper

__all__ = [
    "CanonicalEnvelope",
    "EventMapper",
    "IdempotencyStore",
    "InMemoryIdempotencyStore",
    "PermanentEnvelopeError",
    "ProducerMismatchError",
    "RabbitMQAlertConsumer",
    "RabbitMQConnectionManager",
    "RabbitMQSettings",
    "RedisIdempotencyStore",
    "RedisSettings",
    "UnsupportedVersionError",
    "create_idempotency_store",
    "create_rabbitmq_consumer",
    "default_idempotency_store",
    "get_rabbitmq_consumer",
    "reset_rabbitmq_consumer",
]
