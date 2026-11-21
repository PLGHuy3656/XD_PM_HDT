import asyncio
import json
import logging
from typing import Any
from uuid import UUID

import aio_pika
from aio_pika.abc import AbstractIncomingMessage
import httpx
from pydantic import ValidationError

from app import repositories
from app.config import settings
from app.delivery import send_email, send_fcm, send_web_push
from app.realtime import notification_connections
from app.schemas import NotificationEvent

logger = logging.getLogger(__name__)

# Legacy snake_case event types (HaoHoc) + Canonical V1 event types (IoT PR #24 & AI PR #23)
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
    # Canonical V1 IoT & AI Domain Events
    "iot.environment.high_temperature.started",
    "iot.environment.high_temperature.recovered",
    "iot.environment.low_temperature.started",
    "iot.environment.low_temperature.recovered",
    "iot.environment.high_humidity.started",
    "iot.environment.high_humidity.recovered",
    "iot.environment.low_humidity.started",
    "iot.environment.low_humidity.recovered",
    "iot.audio.fault.started",
    "iot.audio.fault.recovered",
    "iot.device.offline",
    "iot.device.online",
    "iot.command.failed",
    "ai.predator.detected",
    # INT03-R1 Management business events (recipients resolved by Management, explicit recipientUserIds)
    "management.user.created",
    "management.farm.approval_requested",
    "management.farm.approved",
    "management.farm.rejected",
    "management.technician.assigned",
    "management.technician.unassigned",
    "management.device.registered",
    "management.inspection_request.created",
    "management.inspection_request.assigned",
    "management.inspection_request.status_changed",
    "management.inspection_request.requeued",
}
SUPPORTED_CANONICAL_VERSIONS = {"1.0"}
MANAGEMENT_PRODUCER = "management-service"
MAX_RETRY_COUNT = 3
RETRY_DELAY_MS = 5000
MAX_DELIVERY_ATTEMPTS = 5
DELIVERY_POLL_SECONDS = 1
_SENSITIVE_KEYS = {"password", "secret", "token", "authorization", "access_token", "refresh_token", "database_url", "rabbitmq_url"}


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


def _sanitize_payload_data(raw: dict[str, Any]) -> dict[str, Any]:
    """Strip secrets/credentials and sanitize local filesystem paths before persisting."""
    clean: dict[str, Any] = {}
    for k, v in (raw or {}).items():
        if str(k).lower() in _SENSITIVE_KEYS:
            continue
        if isinstance(v, str) and (
            v.startswith(("/tmp/", "/var/", "/home/", "/etc/", "/app/"))
            or (len(v) >= 3 and v[1:3] in (":\\", ":/"))
        ):
            v = v.replace("\\", "/").rsplit("/", 1)[-1]
        elif isinstance(v, dict):
            v = _sanitize_payload_data(v)
        clean[k] = v
    return clean


async def resolve_farm_recipients(farm_id: str) -> list[str]:
    """Resolve authorized recipient user UUIDs for a farm from Management Service."""
    if not farm_id or not settings.management_service_url:
        return []
    url = f"{settings.management_service_url.rstrip('/')}/internal/v1/farms/{farm_id}/recipients"
    headers = {}
    if settings.internal_service_token:
        # INT03: Management internal routes accept ONLY X-Internal-Service-Key (service_auth.py)
        headers["X-Internal-Service-Key"] = settings.internal_service_token
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            logger.warning("Farm recipient lookup for '%s' returned HTTP %s", farm_id, resp.status_code)
            return []
        body = resp.json()
        # Management contract (InternalFarmRecipientsResponse): owner_id + technician_ids
        # (technician ids are user ids). Legacy shapes are still accepted.
        raw_ids = body.get("recipient_user_ids") or body.get("recipients") or []
        if not raw_ids:
            raw_ids = ([body.get("owner_id")] if body.get("owner_id") else []) + list(body.get("technician_ids") or [])
        valid: list[str] = []
        for item in raw_ids:
            uid = item.get("user_id") or item.get("id") if isinstance(item, dict) else item
            if uid:
                try:
                    valid.append(str(UUID(str(uid))))
                except ValueError:
                    continue
        return list(dict.fromkeys(valid))
    except Exception as exc:
        logger.warning("Failed to resolve farm recipients for '%s': %s", farm_id, exc)
        return []


async def resolve_device_location(device_ref: str) -> dict | None:
    """INT03-R1 (R1-08): authoritative farm/zone display location of a device from Management.

    Returns None when the lookup is not possible; never guesses a zone.
    """
    if not device_ref or not settings.management_service_url:
        return None
    url = f"{settings.management_service_url.rstrip('/')}/internal/v1/devices/{device_ref}/location"
    headers = {}
    if settings.internal_service_token:
        headers["X-Internal-Service-Key"] = settings.internal_service_token
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            return None
        body = resp.json()
        return body if isinstance(body, dict) else None
    except Exception as exc:
        logger.warning("Device location lookup for '%s' failed: %s", device_ref, exc)
        return None


async def enrich_location(event_type: str, payload: dict) -> dict:
    """Add farmName/zoneId/zoneName/deviceName for IoT/AI events when Management confirms them.

    The event's own farmId is authoritative: if Management reports a different farm the
    enrichment is discarded (no cross-farm leakage). zoneLabel is set only when the device is
    known to Management and has no zone ("Chưa phân bổ khu vực").
    """
    if not (event_type.startswith("iot.") or event_type.startswith("ai.") or event_type.startswith("device.")):
        return payload
    if payload.get("zoneName") or payload.get("zone_name"):
        return payload
    device_ref = payload.get("deviceId") or payload.get("device_id") or payload.get("cameraId") or payload.get("camera_id") or payload.get("node_id")
    if not device_ref:
        return payload
    loc = await resolve_device_location(str(device_ref))
    if not loc:
        return payload
    event_farm = str(payload.get("farmId") or payload.get("farm_id") or "")
    if event_farm and loc.get("farmId") and str(loc["farmId"]) != event_farm:
        logger.warning("Device %s location farm mismatch (event %s vs registry %s); not enriching", device_ref, event_farm, loc.get("farmId"))
        return payload
    enriched = dict(payload)
    enriched.setdefault("farmName", loc.get("farmName"))
    enriched.setdefault("deviceName", loc.get("deviceName"))
    if loc.get("zoneId"):
        enriched["zoneId"] = loc["zoneId"]
        enriched["zoneName"] = loc.get("zoneName")
    else:
        enriched["zoneLabel"] = "Chưa phân bổ khu vực"
    enriched["locationSource"] = "management"
    return enriched


async def adapt_incoming_event(event: dict) -> dict | None:
    """Adapt either Canonical Domain Event Envelope V1 or legacy snake_case event."""
    if "eventType" in event or "eventId" in event:
        version = str(event.get("eventVersion") or "")
        if version not in SUPPORTED_CANONICAL_VERSIONS:
            raise ValueError(f"Unsupported canonical eventVersion: '{version}'")
        event_type = event.get("eventType")
        if event_type not in SUPPORTED_EVENT_TYPES:
            return None
        payload = event.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("Canonical event payload must be a JSON object")

        explicit_recipients = payload.get("recipientUserIds") or payload.get("recipient_user_ids")
        # INT03-R1 security: explicit recipient lists are trusted ONLY for Management business events
        # (Management resolves them from management_db). IoT/AI events are always farm-scoped via the
        # Management recipients contract, so a producer cannot redirect alerts to arbitrary users.
        trusts_explicit = (
            str(event_type).startswith("management.")
            and event.get("producer") == MANAGEMENT_PRODUCER
        )
        if trusts_explicit and isinstance(explicit_recipients, list) and explicit_recipients:
            recipients = [str(r) for r in explicit_recipients]
        elif str(event_type).startswith("management."):
            recipients = []  # management events without a trusted explicit list are not fanned out
        else:
            farm_id = payload.get("farmId") or payload.get("farm_id")
            recipients = await resolve_farm_recipients(str(farm_id)) if farm_id else []

        if not recipients:
            logger.warning(
                "No resolvable recipients for canonical event '%s' (%s); skipping",
                event_type,
                event.get("eventId"),
            )
            return None

        payload = await enrich_location(event_type, payload)

        return {
            "event_id": event.get("eventId"),
            "event_type": event_type,
            "recipient_user_ids": recipients,
            "data": _sanitize_payload_data(
                {
                    # recipient lists are routing metadata; never persist other users' ids in a notification
                    **{k: v for k, v in payload.items() if k not in ("recipientUserIds", "recipient_user_ids")},
                    "producer": event.get("producer"),
                    "occurredAt": event.get("occurredAt"),
                    "correlationId": event.get("correlationId"),
                }
            ),
        }

    event_type = event.get("event_type")
    if event_type not in SUPPORTED_EVENT_TYPES:
        return None
    sanitized = dict(event)
    sanitized["data"] = _sanitize_payload_data(event.get("data") or {})
    return sanitized


async def process_event(event: dict) -> None:
    adapted = await adapt_incoming_event(event)
    if adapted is None:
        return

    validated_event = NotificationEvent.model_validate(adapted)
    normalized = validated_event.model_dump(mode="json")
    recipients = normalized["recipient_user_ids"]

    for user_id in dict.fromkeys(recipients):
        notification = await asyncio.to_thread(
            repositories.create_notification,
            normalized,
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
            await queue.bind(exchange, routing_key="iot.#")
            await queue.bind(exchange, routing_key="ai.#")
            logger.info("Consuming RabbitMQ events from %s on exchange %s", queue_name, exchange_name)

            async with queue.iterator() as iterator:
                async for message in iterator:
                    try:
                        event = json.loads(message.body)
                        if not isinstance(event, dict):
                            raise ValueError("Event must be a JSON object")
                        await process_event(event)
                    except asyncio.CancelledError:
                        raise
                    except (json.JSONDecodeError, ValueError, ValidationError) as exc:
                        # Poison/malformed message -> route straight to DLQ without wasting retries
                        logger.warning("Rejecting poison/invalid notification message straight to DLQ: %s", exc)
                        await message.reject(requeue=False)
                    except Exception:
                        logger.exception("Notification event processing failed (transient)")
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
