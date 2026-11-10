import asyncio
import json
import logging

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from app import repositories
from app.delivery import send_email, send_fcm, send_web_push
from app.realtime import notification_connections
from app.schemas import NotificationEvent

logger = logging.getLogger(__name__)
SUPPORTED_EVENT_TYPES = {
    "management.technician_assigned",
    "device.command.acknowledged",
    "environment.threshold_exceeded",
    "device.offline",
    "device.sensor.timeout",
    "device.actuator.failed",
    "ai.threat.detected",
    "management.work_request.created",
    "management.work_request.status_changed",
}
MAX_RETRY_COUNT = 3
RETRY_DELAY_MS = 5000
MAX_DELIVERY_ATTEMPTS = 5
DELIVERY_POLL_SECONDS = 1


def _retry_queue_arguments(queue_name: str) -> dict:
    return {
        "x-message-ttl": RETRY_DELAY_MS,
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": queue_name,
    }


def _build_retry_message(
    message: AbstractIncomingMessage,
    retry_count: int,
) -> aio_pika.Message:
    headers = dict(message.headers or {})
    headers["x-notification-retry"] = retry_count + 1
    return aio_pika.Message(
        body=message.body,
        content_type=message.content_type,
        delivery_mode=message.delivery_mode or aio_pika.DeliveryMode.PERSISTENT,
        headers=headers,
        message_id=message.message_id,
        correlation_id=message.correlation_id,
    )


async def process_event(event: dict) -> None:
    event_type = event.get("event_type")
    if event_type not in SUPPORTED_EVENT_TYPES:
        return

    validated_event = NotificationEvent.model_validate(event)
    event = validated_event.model_dump(mode="json")
    recipients = event["recipient_user_ids"]

    for user_id in dict.fromkeys(recipients):
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


async def deliver_pending_notifications() -> None:
    while True:
        try:
            delivery = await asyncio.to_thread(
                repositories.claim_pending_delivery,
            )
            if delivery is None:
                await asyncio.sleep(DELIVERY_POLL_SECONDS)
                continue

            notification = delivery["notification"]
            user_id = notification["user_id"]
            try:
                if delivery["channel"] == "email":
                    recipient = await asyncio.to_thread(
                        repositories.get_user_email,
                        user_id,
                    )
                    delivered = (
                        await asyncio.to_thread(
                            send_email,
                            notification,
                            recipient,
                        )
                        if recipient
                        else False
                    )
                elif delivery["channel"] == "web_push":
                    delivered = await asyncio.to_thread(
                        send_web_push,
                        notification,
                        user_id,
                    )
                elif delivery["channel"] == "fcm":
                    delivered = await asyncio.to_thread(
                        send_fcm,
                        notification,
                        user_id,
                    )
                else:
                    raise ValueError(
                        f"Unsupported notification channel: {delivery['channel']}"
                    )
            except Exception as exc:
                attempts = delivery["attempts"]
                retry_delay = min(300, 5 * (2 ** max(0, attempts - 1)))
                await asyncio.to_thread(
                    repositories.finish_delivery,
                    delivery["delivery_id"],
                    status="failed",
                    error=str(exc)[:1000],
                    retry_delay_seconds=retry_delay,
                )
                logger.exception(
                    "%s delivery failed for notification %s (attempt %s/%s)",
                    delivery["channel"],
                    notification["id"],
                    attempts,
                    MAX_DELIVERY_ATTEMPTS,
                )
                continue

            await asyncio.to_thread(
                repositories.finish_delivery,
                delivery["delivery_id"],
                status="delivered" if delivered else "skipped",
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Notification delivery worker failed")
            await asyncio.sleep(DELIVERY_POLL_SECONDS)


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
                f"{queue_name}.retry.v3",
                durable=True,
                arguments=_retry_queue_arguments(queue_name),
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
            await queue.bind(exchange, routing_key="environment.#")
            await queue.bind(exchange, routing_key="ai.#")
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
                            retry_message = _build_retry_message(
                                message,
                                retry_count,
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
