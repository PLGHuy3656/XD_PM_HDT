
import json
import logging
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from typing import Any

from pydantic import ValidationError

from app.schemas.control_ack import ControlAck

from uuid import UUID

from app.repositories.control_repository import (
    get_device_notification_context,
    get_active_device_id_by_node_id,
    record_command_ack,
)

ACK_TOPIC_PREFIX = "swiftlet/ack/"
logger = logging.getLogger(__name__)


def parse_ack_message(
    topic: str,
    payload: bytes,
) -> tuple[str, ControlAck]:
    """Parse an ACK message and validate its topic and payload."""
    if not topic.startswith(ACK_TOPIC_PREFIX):
        raise ValueError("Unexpected ACK topic")

    node_id = topic[len(ACK_TOPIC_PREFIX):]

    if not node_id or "/" in node_id or "+" in node_id or "#" in node_id:
        raise ValueError("Invalid node ID in ACK topic")

    try:
        decoded: Any = json.loads(payload.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("ACK payload must be a JSON object")

        ack = ControlAck.model_validate(decoded)

    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError("Invalid ACK payload") from exc

    if ack.nodeId != node_id:
        raise ValueError("ACK nodeId does not match topic")

    if ack.mode is not None and ack.mode not in {"AUTO", "MANUAL"}:
        raise ValueError("Unsupported ACK mode")

    if ack.status not in {"SUCCESS", "FAILED", "ERROR"}:
        raise ValueError("Unsupported ACK status")

    return node_id, ack

def process_ack_message(
    topic: str,
    payload: bytes,
    event_publisher=None,
    event_loop: asyncio.AbstractEventLoop | None = None,
) -> bool:
    """Validate an MQTT ACK and record it for the matching active device."""
    try:
        node_id, ack = parse_ack_message(topic, payload)
    except (ValueError, ValidationError) as exc:
        logger.warning("Rejected MQTT ACK: %s", exc)
        return False

    device_id = get_active_device_id_by_node_id(node_id)

    if device_id is None:
        logger.warning(
            "Rejected ACK: no active device registered for node_id=%s",
            node_id,
        )
        return False

    recorded = record_command_ack(
        command_id=ack.commandId,
        expected_device_id=UUID(str(device_id)),
        status=ack.status,
        response=ack.model_dump(mode="json", exclude_none=True),
    )

    if not recorded:
        logger.warning(
            "ACK did not match a pending command: command_id=%s node_id=%s",
            ack.commandId,
            node_id,
        )
        return False

    if event_publisher and event_loop and event_loop.is_running():
        try:
            context = get_device_notification_context(UUID(str(device_id)))
            if context and context["recipient_user_ids"]:
                event_id = str(uuid4())
                event = {
                    "event_id": event_id,
                    "event_type": "device.command.acknowledged",
                    "occurred_at": datetime.now(timezone.utc).isoformat(),
                    "recipient_user_ids": context["recipient_user_ids"],
                    "data": {
                        "command_id": ack.commandId,
                        "node_id": context["node_id"],
                        "status": ack.status,
                        "farm_id": context["farm_id"],
                        "farm_code": context["farm_code"],
                        "farm_name": context["farm_name"],
                        "zone_name": context["zone_name"],
                    },
                }
                future = asyncio.run_coroutine_threadsafe(
                    event_publisher.publish(
                        "device.command.acknowledged",
                        event,
                    ),
                    event_loop,
                )
                future.add_done_callback(_log_event_publish_result)
        except Exception:
            logger.exception(
                "ACK was saved but its notification event could not be prepared"
            )

    logger.info(
        "Recorded ACK: command_id=%s node_id=%s status=%s",
        ack.commandId,
        node_id,
        ack.status,
    )
    return True


def _log_event_publish_result(future) -> None:
    try:
        future.result()
    except Exception:
        logger.exception("Failed to publish command ACK notification event")