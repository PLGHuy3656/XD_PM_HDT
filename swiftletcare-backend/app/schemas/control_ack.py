
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ControlAck(BaseModel):
    model_config = ConfigDict(extra="ignore")

    commandId: str = Field(min_length=1, max_length=100)
    nodeId: str = Field(min_length=1, max_length=100)
    status: str = Field(min_length=1, max_length=30)
    mode: str | None = None
    message: str | None = None
    timestamp: int | None = None


def parse_ack(payload: bytes | str) -> ControlAck:
    """Parse and validate an ACK payload without changing any state."""
    try:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")

        data: Any = json.loads(payload)
        if not isinstance(data, dict):
            raise ValueError("ACK payload must be a JSON object")

        ack = ControlAck.model_validate(data)

        if ack.mode is not None and ack.mode not in {"AUTO", "MANUAL"}:
            raise ValueError("ACK contains an unsupported mode")

        if ack.status not in {"SUCCESS", "FAILED", "ERROR"}:
            raise ValueError("ACK contains an unsupported status")

        return ack

    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError("Invalid ACK payload") from exc


def match_ack(
    ack: ControlAck,
    *,
    expected_command_id: str,
    expected_node_id: str,
) -> bool:
    """Check whether an ACK belongs to the expected command and device."""
    return (
        ack.commandId == expected_command_id
        and ack.nodeId == expected_node_id
    )
