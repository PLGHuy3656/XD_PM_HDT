"""Configuration and settings for Notification RabbitMQ Consumer & Redis Idempotency (CP7.5)."""
from __future__ import annotations

import os
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class RabbitMQSettings(BaseModel):
    """Configuration for RabbitMQ consumer adapter."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    enabled: bool = Field(default=False, description="Master switch for RabbitMQ consumer")
    host: str = Field(default="127.0.0.1", description="RabbitMQ broker hostname")
    port: int = Field(default=5672, description="RabbitMQ AMQP port")
    user: str = Field(default="swiftlet", description="RabbitMQ username")
    password: str = Field(default="swiftlet123", description="RabbitMQ password")
    vhost: str = Field(default="/", description="RabbitMQ virtual host")
    queue_name: str = Field(
        default="notification.alert-events.v1",
        description="Canonical notification alert events queue",
    )
    prefetch_count: int = Field(
        default=10,
        description="QoS prefetch count (10 default for dev; tuned for prod in CP7.5)",
    )
    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts before routing to DLQ (CP7.5 bounded retry)",
    )
    retry_ttl_ms: int = Field(
        default=5000,
        description="Delayed retry TTL in milliseconds (CP7.5)",
    )
    retry_exchange: str = Field(
        default="swiftlet.notification.retry",
        description="Retry exchange for delayed republishing",
    )
    retry_routing_key: str = Field(
        default="notification.alert-events.v1.retry",
        description="Routing key for retry queue",
    )
    dlx_exchange: str = Field(
        default="swiftlet.notification.dlx",
        description="Dead-letter exchange for permanent/exhausted failures",
    )
    dlq_routing_key: str = Field(
        default="notification.alert-events.v1.dlq",
        description="Routing key for DLQ",
    )
    max_defers: int = Field(
        default=120,
        description=(
            "Maximum deferrals (via the existing retry queue) while the idempotency lease is held by "
            "another delivery or the idempotency store is unavailable, before dead-lettering (CP8.5). "
            "Counted in header x-defer-count, independent of x-retry-count."
        ),
    )
    nack_backoff_base_ms: int = Field(
        default=500,
        description="Base delay before nack(requeue=True) when the broker cannot accept a deferral/retry publish (CP8.5)",
    )
    nack_backoff_max_ms: int = Field(
        default=30000,
        description="Upper bound for the exponential nack backoff (CP8.5)",
    )

    @classmethod
    def from_env(cls) -> "RabbitMQSettings":
        """Load settings from environment variables with safe defaults."""
        enabled_str = os.getenv("RABBITMQ_ENABLED", "false").strip().lower()
        enabled = enabled_str in ("true", "1", "yes", "on")

        host = os.getenv("RABBITMQ_HOST", "127.0.0.1").strip()
        port_str = os.getenv("RABBITMQ_PORT", os.getenv("RABBITMQ_AMQP_PORT", "5672")).strip()
        try:
            port = int(port_str)
        except ValueError:
            port = 5672

        user = os.getenv("RABBITMQ_USER", os.getenv("RABBITMQ_DEFAULT_USER", "swiftlet")).strip()
        password = os.getenv("RABBITMQ_PASSWORD", os.getenv("RABBITMQ_DEFAULT_PASS", "swiftlet123")).strip()
        vhost = os.getenv("RABBITMQ_VHOST", "/").strip()
        queue = os.getenv("RABBITMQ_NOTIFICATION_QUEUE", "notification.alert-events.v1").strip()

        prefetch_str = os.getenv("RABBITMQ_PREFETCH", "10").strip()
        try:
            prefetch = max(1, int(prefetch_str))
        except ValueError:
            prefetch = 10

        max_retries_str = os.getenv("RABBITMQ_MAX_RETRIES", "3").strip()
        try:
            max_retries = max(1, int(max_retries_str))
        except ValueError:
            max_retries = 3

        retry_ttl_str = os.getenv("RABBITMQ_RETRY_TTL_MS", "5000").strip()
        try:
            retry_ttl_ms = max(500, int(retry_ttl_str))
        except ValueError:
            retry_ttl_ms = 5000

        retry_exchange = os.getenv("RABBITMQ_RETRY_EXCHANGE", "swiftlet.notification.retry").strip()
        retry_routing_key = os.getenv("RABBITMQ_RETRY_ROUTING_KEY", "notification.alert-events.v1.retry").strip()
        dlx_exchange = os.getenv("RABBITMQ_DLX_EXCHANGE", "swiftlet.notification.dlx").strip()
        dlq_routing_key = os.getenv("RABBITMQ_DLQ_ROUTING_KEY", "notification.alert-events.v1.dlq").strip()

        def _int_env(name: str, default: int, minimum: int) -> int:
            try:
                return max(minimum, int(os.getenv(name, str(default)).strip()))
            except ValueError:
                return default

        max_defers = _int_env("RABBITMQ_MAX_DEFERS", 120, 1)
        nack_backoff_base_ms = _int_env("RABBITMQ_NACK_BACKOFF_BASE_MS", 500, 50)
        nack_backoff_max_ms = max(nack_backoff_base_ms, _int_env("RABBITMQ_NACK_BACKOFF_MAX_MS", 30000, 100))

        return cls(
            enabled=enabled,
            host=host,
            port=port,
            user=user,
            password=password,
            vhost=vhost,
            queue_name=queue,
            prefetch_count=prefetch,
            max_retries=max_retries,
            retry_ttl_ms=retry_ttl_ms,
            retry_exchange=retry_exchange,
            retry_routing_key=retry_routing_key,
            dlx_exchange=dlx_exchange,
            dlq_routing_key=dlq_routing_key,
            max_defers=max_defers,
            nack_backoff_base_ms=nack_backoff_base_ms,
            nack_backoff_max_ms=nack_backoff_max_ms,
        )


class RedisSettings(BaseModel):
    """Configuration for Redis-backed durable idempotency store (CP7.5)."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    enabled: bool = Field(default=True, description="Enable Redis for durable idempotency")
    host: str = Field(default="127.0.0.1", description="Redis hostname")
    port: int = Field(default=6379, description="Redis port")
    db: int = Field(default=0, description="Redis database index")
    password: Optional[str] = Field(default=None, description="Redis password if authentication enabled")
    idempotency_ttl_seconds: int = Field(
        default=86400,
        description="Retention TTL for processed eventIds (default 86400 = 24 hours)",
    )
    processing_claim_ttl_seconds: int = Field(
        default=60,
        description="Lease TTL for in-flight processing claims before lease expires (default 60s)",
    )

    @classmethod
    def from_env(cls) -> "RedisSettings":
        enabled_str = os.getenv("REDIS_ENABLED", "true").strip().lower()
        enabled = enabled_str in ("true", "1", "yes", "on")

        host = os.getenv("REDIS_HOST", "127.0.0.1").strip()
        port_str = os.getenv("REDIS_PORT", "6379").strip()
        try:
            port = int(port_str)
        except ValueError:
            port = 6379

        db_str = os.getenv("REDIS_DB", "0").strip()
        try:
            db = int(db_str)
        except ValueError:
            db = 0

        password = os.getenv("REDIS_PASSWORD", None)
        if password and not password.strip():
            password = None

        ttl_str = os.getenv("IDEMPOTENCY_TTL_SECONDS", "86400").strip()
        try:
            ttl_seconds = max(60, int(ttl_str))
        except ValueError:
            ttl_seconds = 86400

        claim_ttl_str = os.getenv("PROCESSING_CLAIM_TTL_SECONDS", "60").strip()
        try:
            claim_ttl = max(5, int(claim_ttl_str))
        except ValueError:
            claim_ttl = 60

        return cls(
            enabled=enabled,
            host=host,
            port=port,
            db=db,
            password=password,
            idempotency_ttl_seconds=ttl_seconds,
            processing_claim_ttl_seconds=claim_ttl,
        )


__all__ = ["RabbitMQSettings", "RedisSettings"]
