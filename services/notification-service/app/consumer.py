import asyncio
import json
import logging

import aio_pika

from app import repositories
from app.delivery import send_email, send_web_push
from app.realtime import notification_connections

logger = logging.getLogger(__name__)
SUPPORTED_EVENT_TYPES = {
    "management.technician_assigned",
    "device.command.acknowledged",
}
MAX_RETRY_COUNT = 3


async def process_event(event: dict) -> None:
    event_type = event.get("event_type")
    if event_type not in SUPPORTED_EVENT_TYPES:
        return

    recipients = event.get("recipient_user_ids")
    if not isinstance(recipients, list):
        raise ValueError("Event recipient_user_ids must be an array")

    for user_id in dict.fromkeys(str(value) for value in recipients):
        notification = await asyncio.to_thread(
            repositories.create_notification,
            event,
            user_id,
        )
        if notification is None:
            continue

        await notification_connections.broadcast(
            user_id,
            {"type": "notification", "notification": notification},
        )
        await _deliver_channels(notification, user_id)


async def _deliver_channels(notification: dict, user_id: str) -> None:
    try:
        recipient = await asyncio.to_thread(
            repositories.get_user_email,
            user_id,
        )
        if recipient:
            await asyncio.to_thread(send_email, notification, recipient)
    except Exception:
        logger.exception("Email delivery failed for notification %s", notification["id"])

    try:
        await asyncio.to_thread(
            send_web_push,
            notification,
            user_id,
        )
    except Exception:
        logger.exception("Web push delivery failed for notification %s", notification["id"])


async def consume_events(
    rabbitmq_url: str,
    exchange_name: str,
    queue_name: str,
) -> None:
    while True:
        connection = None
        try:
            connection = await aio_pika.connect_robust(
                rabbitmq_url,
                timeout=5,
            )
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=10)
            exchange = await channel.declare_exchange(
                exchange_name,
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )
            dead_letter_exchange = await channel.declare_exchange(
                f"{exchange_name}.dead",
                aio_pika.ExchangeType.DIRECT,
                durable=True,
            )
            dead_letter_queue = await channel.declare_queue(
                f"{queue_name}.dead",
                durable=True,
            )
            retry_queue = await channel.declare_queue(
                f"{queue_name}.retry",
                durable=True,
                arguments={
                    "x-dead-letter-exchange": exchange_name,
                },
            )
            await dead_letter_queue.bind(
                dead_letter_exchange,
                routing_key=f"{queue_name}.dead",
            )
            queue = await channel.declare_queue(
                queue_name,
                durable=True,
                arguments={
                    "x-dead-letter-exchange": f"{exchange_name}.dead",
                    "x-dead-letter-routing-key": f"{queue_name}.dead",
                },
            )
            await queue.bind(exchange, routing_key="management.#")
            await queue.bind(exchange, routing_key="device.#")
            logger.info("Consuming RabbitMQ events from %s", queue_name)

            async with queue.iterator() as iterator:
                async for message in iterator:
                    try:
                        event = json.loads(message.body)
                        if not isinstance(event, dict):
                            raise ValueError("Event must be a JSON object")
                        await process_event(event)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        logger.exception("Notification event processing failed")
                        retry_count = (message.headers or {}).get(
                            "x-notification-retry",
                            0,
                        )
                        if (
                            isinstance(retry_count, int)
                            and retry_count < MAX_RETRY_COUNT
                        ):
                            headers = dict(message.headers or {})
                            headers["x-notification-retry"] = retry_count + 1
                            retry_message = aio_pika.Message(
                                body=message.body,
                                content_type=message.content_type,
                                delivery_mode=message.delivery_mode,
                                headers=headers,
                                message_id=message.message_id,
                                correlation_id=message.correlation_id,
                                expiration=5,
                            )
                            try:
                                await channel.default_exchange.publish(
                                    retry_message,
                                    routing_key=retry_queue.name,
                                    mandatory=True,
                                )
                                await message.ack()
                            except Exception:
                                logger.exception(
                                    "Failed to enqueue notification retry"
                                )
                                await message.reject(requeue=False)
                        else:
                            await message.reject(requeue=False)
                    else:
                        await message.ack()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Notification RabbitMQ consumer disconnected")
            await asyncio.sleep(5)
        finally:
            if connection and not connection.is_closed:
                await connection.close()
