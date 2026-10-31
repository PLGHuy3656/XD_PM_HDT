
from typing import Any
from uuid import UUID, uuid4

from app.control_repository import create_command
from app.control_schemas import (
    RelayCommandRequest,
    ThresholdCommandRequest,
)


def prepare_relay_command(
    device_id: UUID,
    request: RelayCommandRequest,
) -> dict[str, Any]:
    command_id = str(uuid4())

    payload = {
        "commandId": command_id,
        "action": request.action,
        "target": request.target,
        "state": request.state,
    }

    record = create_command(
        command_id=command_id,
        device_id=device_id,
        action=request.action,
        payload=payload,
    )

    return {
        "command": payload,
        "record": record,
    }


def prepare_threshold_command(
    device_id: UUID,
    request: ThresholdCommandRequest,
) -> dict[str, Any]:
    command_id = str(uuid4())

    payload: dict[str, Any] = {
        "commandId": command_id,
        "action": request.action,
    }

    if request.targetTemp is not None:
        payload["targetTemp"] = request.targetTemp

    if request.targetHum is not None:
        payload["targetHum"] = request.targetHum

    if request.isAutoMode is not None:
        payload["isAutoMode"] = request.isAutoMode

    record = create_command(
        command_id=command_id,
        device_id=device_id,
        action=request.action,
        payload=payload,
    )

    return {
        "command": payload,
        "record": record,
    }
