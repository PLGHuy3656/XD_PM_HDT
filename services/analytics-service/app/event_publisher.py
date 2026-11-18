import asyncio
import json

import aio_pika


class AnalyticsEventPublisher:
    def __init__(self, rabbitmq_url: str, exchange_name: str):
        self.rabbitmq_url = rabbitmq_url
        self.exchange_name = exchange_name
        self.connection = None
        self.channel = None
        self.exchange = None
        self.lock = asyncio.Lock()

    async def publish(self, event_type: str, payload: dict) -> None:
        async with self.lock:
            if not self.connection or self.connection.is_closed:
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

            await self.exchange.publish(
                aio_pika.Message(
                    body=json.dumps(payload, separators=(",", ":")).encode(),
                    content_type="application/json",
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    message_id=str(payload["event_id"]),
                ),
                routing_key=event_type,
                mandatory=True,
            )

    async def close(self) -> None:
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
