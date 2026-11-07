"""RabbitMQ connection manager using aio-pika robust connection for AI Service."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import aio_pika
from aio_pika.abc import (
    AbstractExchange,
    AbstractRobustChannel,
    AbstractRobustConnection,
)

from app.domain_events.constants import CANONICAL_EXCHANGE

logger = logging.getLogger("ai_service.infrastructure.rabbitmq.connection")


class RabbitMQConnectionManager:
    """Manages an async, reconnect-resilient aio-pika connection and confirm channel."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5672,
        user: str = "swiftlet",
        password: str = "swiftlet123",
        vhost: str = "/",
        exchange_name: str = CANONICAL_EXCHANGE,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.vhost = vhost
        self.exchange_name = exchange_name

        self._connection: Optional[AbstractRobustConnection] = None
        self._channel: Optional[AbstractRobustChannel] = None
        self._exchange: Optional[AbstractExchange] = None
        self._lock = asyncio.Lock()
        self._is_closing = False

    @property
    def is_connected(self) -> bool:
        return self._connection is not None and not self._connection.is_closed

    async def connect(self) -> None:
        """Establishes robust connection and declares topic exchange with publisher confirms."""
        async with self._lock:
            if self.is_connected:
                return

            self._is_closing = False
            logger.info(
                "[AI RABBITMQ CONNECTING] amqp://%s:***@%s:%s/%s",
                self.user,
                self.host,
                self.port,
                self.vhost,
            )

            try:
                self._connection = await aio_pika.connect_robust(
                    host=self.host,
                    port=self.port,
                    login=self.user,
                    password=self.password,
                    virtualhost=self.vhost,
                )
                self._channel = await self._connection.channel(publisher_confirms=True)
                self._exchange = await self._channel.declare_exchange(
                    name=self.exchange_name,
                    type=aio_pika.ExchangeType.TOPIC,
                    durable=True,
                )
                logger.info(
                    "[AI RABBITMQ CONNECTED] Exchange '%s' ready with publisher confirms",
                    self.exchange_name,
                )
            except Exception as exc:
                logger.error("[AI RABBITMQ CONNECT FAILED] Could not connect to RabbitMQ: %s", exc)
                self._connection = None
                self._channel = None
                self._exchange = None
                raise

    async def get_exchange(self) -> AbstractExchange:
        """Retrieves active exchange, reconnecting if needed."""
        if not self.is_connected or self._exchange is None:
            await self.connect()
        if self._exchange is None:
            raise RuntimeError("RabbitMQ exchange is not initialized")
        return self._exchange

    async def close(self) -> None:
        """Gracefully closes channel and connection."""
        async with self._lock:
            self._is_closing = True
            if self._channel and not self._channel.is_closed:
                try:
                    await self._channel.close()
                except Exception as exc:
                    logger.debug("[AI RABBITMQ CLOSE] Channel close error: %s", exc)
            if self._connection and not self._connection.is_closed:
                try:
                    await self._connection.close()
                except Exception as exc:
                    logger.debug("[AI RABBITMQ CLOSE] Connection close error: %s", exc)
            self._exchange = None
            self._channel = None
            self._connection = None
            logger.info("[AI RABBITMQ CLOSED] Connection closed cleanly")


__all__ = ["RabbitMQConnectionManager"]
