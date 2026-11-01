import asyncio
import json
import logging

import aio_pika

from app.repositories.event_outbox_repository import (
    claim_pending_events,
    mark_event_published,
    release_event_for_retry,
)

logger = logging.getLogger(__name__)


class EventOutboxPublisher:
    def __init__(self, rabbitmq_url: str, exchange_name: str):
        self.rabbitmq_url = rabbitmq_url
        self.exchange_name = exchange_name
        self.connection = None
        self.channel = None
        self.exchange = None

    async def close(self) -> None:
        if self.connection and not self.connection.is_closed:
            await self.connection.close()

    async def _connect(self) -> None:
        if self.connection and not self.connection.is_closed:
            return

        self.connection = await aio_pika.connect_robust(
            self.rabbitmq_url,
            timeout=5,
        )
        self.channel = await self.connection.channel(
            publisher_confirms=True,
        )
        self.exchange = await self.channel.declare_exchange(
            self.exchange_name,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )
        logger.info("Connected to RabbitMQ exchange %s", self.exchange_name)

    async def run(self) -> None:
        while True:
            try:
                await self._connect()
                events = await asyncio.to_thread(claim_pending_events)
                for event in events:
                    await self._publish(event)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("RabbitMQ outbox polling failed")

            await asyncio.sleep(0.5 if self.exchange else 5)

    async def _publish(self, event: dict) -> None:
        try:
            body = json.dumps(
                event["payload"],
                separators=(",", ":"),
            ).encode("utf-8")
            await self.exchange.publish(
                aio_pika.Message(
                    body=body,
                    content_type="application/json",
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    message_id=event["event_id"],
                ),
                routing_key=event["event_type"],
                mandatory=True,
            )
            await asyncio.to_thread(mark_event_published, event["event_id"])
        except Exception as exc:
            logger.exception(
                "Failed to publish management event %s",
                event["event_id"],
            )
            await asyncio.to_thread(
                release_event_for_retry,
                event["event_id"],
                str(exc),
            )
