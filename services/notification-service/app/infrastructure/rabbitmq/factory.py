"""Factory and singleton providers for RabbitMQ consumer components (CP7.4 / CP7.5)."""
from __future__ import annotations

import logging
import threading
from typing import Optional

from app.dependencies import get_notification_service
from app.infrastructure.rabbitmq.config import RabbitMQSettings, RedisSettings
from app.infrastructure.rabbitmq.connection import RabbitMQConnectionManager
from app.infrastructure.rabbitmq.consumer import RabbitMQAlertConsumer
from app.infrastructure.rabbitmq.idempotency import (
    IdempotencyStore,
    InMemoryIdempotencyStore,
    RedisIdempotencyStore,
    default_idempotency_store,
)

logger = logging.getLogger("notification_service.infrastructure.rabbitmq.factory")

_lock = threading.Lock()
_consumer: Optional[RabbitMQAlertConsumer] = None
_idempotency_store: Optional[IdempotencyStore] = None


def create_idempotency_store(
    redis_settings: Optional[RedisSettings] = None,
    allow_memory_fallback: bool = False,
) -> IdempotencyStore:
    """Instantiates a durable RedisIdempotencyStore or fallback InMemoryIdempotencyStore."""
    r_cfg = redis_settings or RedisSettings.from_env()

    if r_cfg.enabled:
        try:
            import redis.asyncio as aioredis
            client = aioredis.Redis(
                host=r_cfg.host,
                port=r_cfg.port,
                db=r_cfg.db,
                password=r_cfg.password,
                decode_responses=False,
            )
            logger.info(
                "[IDEMPOTENCY FACTORY] Initialized RedisIdempotencyStore at %s:%d (db=%d, ttl=%ds)",
                r_cfg.host,
                r_cfg.port,
                r_cfg.db,
                r_cfg.idempotency_ttl_seconds,
            )
            return RedisIdempotencyStore(
                redis_client=client,
                idempotency_ttl_seconds=r_cfg.idempotency_ttl_seconds,
                processing_claim_ttl_seconds=r_cfg.processing_claim_ttl_seconds,
            )
        except Exception as exc:
            logger.warning("[IDEMPOTENCY FACTORY] Redis initialization failed: %s", exc)
            if not allow_memory_fallback:
                raise RuntimeError(f"Redis idempotency required but failed to initialize: {exc}") from exc

    logger.info("[IDEMPOTENCY FACTORY] Using InMemoryIdempotencyStore (test/fallback mode)")
    return InMemoryIdempotencyStore(default_ttl=r_cfg.idempotency_ttl_seconds)


def create_rabbitmq_consumer(
    settings: Optional[RabbitMQSettings] = None,
    redis_settings: Optional[RedisSettings] = None,
    idempotency_store: Optional[IdempotencyStore] = None,
) -> RabbitMQAlertConsumer:
    """Instantiates a new RabbitMQAlertConsumer with current dependencies."""
    cfg = settings or RabbitMQSettings.from_env()
    r_cfg = redis_settings or RedisSettings.from_env()
    conn_mgr = RabbitMQConnectionManager(cfg)
    service = get_notification_service()
    store = idempotency_store or create_idempotency_store(r_cfg, allow_memory_fallback=True)

    # CP8.5: durable PostgreSQL inbox whenever alerts are persisted in notification_db.
    from app.dependencies import get_alert_repo
    from app.infrastructure.rabbitmq.inbox import NullEventInbox, PostgresEventInbox
    from app.repositories.postgres_alert_repo import PostgreSQLAlertRepository

    alert_repo = get_alert_repo()
    if isinstance(alert_repo, PostgreSQLAlertRepository):
        inbox = PostgresEventInbox(database_url=getattr(alert_repo, "_database_url", None))
        logger.info("[CONSUMER FACTORY] Durable PostgreSQL inbox enabled (processed_events)")
    else:
        inbox = NullEventInbox()
        logger.info("[CONSUMER FACTORY] In-memory repositories: durable inbox disabled")

    return RabbitMQAlertConsumer(
        service=service,
        connection_manager=conn_mgr,
        idempotency_store=store,
        settings=cfg,
        redis_settings=r_cfg,
        inbox=inbox,
    )


def get_rabbitmq_consumer() -> RabbitMQAlertConsumer:
    """Returns singleton RabbitMQAlertConsumer instance."""
    global _consumer
    with _lock:
        if _consumer is None:
            _consumer = create_rabbitmq_consumer()
        return _consumer


def reset_rabbitmq_consumer() -> None:
    """Resets singleton consumer instance (for test fixtures)."""
    global _consumer, _idempotency_store
    with _lock:
        _consumer = None
        _idempotency_store = None


__all__ = [
    "create_idempotency_store",
    "create_rabbitmq_consumer",
    "get_rabbitmq_consumer",
    "reset_rabbitmq_consumer",
]
