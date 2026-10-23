
import json
from typing import Any

from pydantic import ValidationError

from app.control_ack import ControlAck


ACK_TOPIC_PREFIX = "swiftlet/ack/"


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
