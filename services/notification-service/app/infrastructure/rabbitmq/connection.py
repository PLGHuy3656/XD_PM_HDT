"""RabbitMQ connection manager using aio-pika robust connection for Notification Service (CP7.4)."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import aio_pika
from aio_pika.abc import (
    AbstractQueue,
    AbstractRobustChannel,
    AbstractRobustConnection,
)

from app.infrastructure.rabbitmq.config import RabbitMQSettings

logger = logging.getLogger("notification_service.infrastructure.rabbitmq.connection")


class RabbitMQConnectionManager:
    """Manages an async, reconnect-resilient aio-pika connection and consumer channel."""

    def __init__(self, settings: Optional[RabbitMQSettings] = None) -> None:
        self.settings = settings or RabbitMQSettings.from_env()

        self._connection: Optional[AbstractRobustConnection] = None
        self._channel: Optional[AbstractRobustChannel] = None
        self._queue: Optional[AbstractQueue] = None
        self._lock = asyncio.Lock()
        self._is_closing = False

    @property
    def is_connected(self) -> bool:
        return self._connection is not None and not self._connection.is_closed

    async def connect(self) -> None:
        """Establishes robust connection, configures QoS prefetch, and verifies queue binding."""
        async with self._lock:
            if self.is_connected:
                return

            self._is_closing = False
            logger.info(
                "[NOTIFICATION RABBITMQ CONNECTING] amqp://%s:***@%s:%s/%s (queue=%s, prefetch=%d)",
                self.settings.user,
                self.settings.host,
                self.settings.port,
                self.settings.vhost,
                self.settings.queue_name,
                self.settings.prefetch_count,
            )

            try:
                self._connection = await aio_pika.connect_robust(
                    host=self.settings.host,
                    port=self.settings.port,
                    login=self.settings.user,
                    password=self.settings.password,
                    virtualhost=self.settings.vhost,
                )
                self._channel = await self._connection.channel()
                # Set QoS prefetch count
                await self._channel.set_qos(prefetch_count=self.settings.prefetch_count)

                # Passive queue declaration ensures we bind to existing CP7.1 topology without mutating arguments
                self._queue = await self._channel.declare_queue(
                    name=self.settings.queue_name,
                    durable=True,
                    passive=True,
                )
                logger.info(
                    "[NOTIFICATION RABBITMQ CONNECTED] Queue '%s' bound with prefetch %d",
                    self.settings.queue_name,
                    self.settings.prefetch_count,
                )
            except Exception as exc:
                logger.error("[NOTIFICATION RABBITMQ CONNECT FAILED] Could not connect to RabbitMQ: %s", exc)
                self._connection = None
                self._channel = None
                self._queue = None
                raise

    async def get_channel(self) -> AbstractRobustChannel:
        if not self.is_connected or self._channel is None:
            await self.connect()
        if self._channel is None:
            raise RuntimeError("RabbitMQ channel is not initialized")
        return self._channel

    async def get_queue(self) -> AbstractQueue:
        if not self.is_connected or self._queue is None:
            await self.connect()
        if self._queue is None:
            raise RuntimeError("RabbitMQ queue is not initialized")
        return self._queue

    async def close(self) -> None:
        """Gracefully closes channel and connection."""
        async with self._lock:
            self._is_closing = True
            if self._channel and not self._channel.is_closed:
                try:
                    await self._channel.close()
                except Exception as exc:
                    logger.debug("[NOTIFICATION RABBITMQ CLOSE] Channel close error: %s", exc)
            if self._connection and not self._connection.is_closed:
                try:
                    await self._connection.close()
                except Exception as exc:
                    logger.debug("[NOTIFICATION RABBITMQ CLOSE] Connection close error: %s", exc)
            self._queue = None
            self._channel = None
            self._connection = None
            logger.info("[NOTIFICATION RABBITMQ CLOSED] Connection closed cleanly")


__all__ = ["RabbitMQConnectionManager"]
