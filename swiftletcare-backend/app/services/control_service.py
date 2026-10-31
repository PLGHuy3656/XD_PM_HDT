
from typing import Any
from uuid import UUID, uuid4

import paho.mqtt.client as mqtt

from app.repositories.control_repository import (
    create_command,
    get_active_device_commands,
    get_active_device_control_state,
    get_active_device_node_id,
    mark_command_failed,
    mark_command_sent,
)
from app.mqtt.control import publish_command
from app.schemas.control import (
    RelayCommandRequest,
    ThresholdCommandRequest,
)


def get_control_state(device_id: UUID) -> dict[str, Any] | None:
    row = get_active_device_control_state(device_id)
    if row is None:
        return None

    return {
        "deviceId": str(row[0]),
        "nodeId": row[1],
        "config": (
            {
                "mode": row[2],
                "targetTemp": row[3],
                "targetHum": row[4],
                "tempDeadband": row[5],
                "humDeadband": row[6],
                "co2Threshold": row[7],
                "updatedAt": row[8].isoformat() if row[8] else None,
            }
            if row[2] is not None
            else None
        ),
    }


def get_control_commands(
    device_id: UUID,
    limit: int,
) -> dict[str, Any] | None:
    rows = get_active_device_commands(device_id, limit)
    if rows is None:
        return None

    return {
        "deviceId": str(device_id),
        "items": [
            {
                "commandId": row[0],
                "action": row[1],
                "status": row[2],
                "payload": row[3],
                "response": row[4],
                "createdAt": row[5].isoformat(),
                "sentAt": row[6].isoformat() if row[6] else None,
                "acknowledgedAt": (
                    row[7].isoformat() if row[7] else None
                ),
            }
            for row in rows
        ],
    }


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



def send_prepared_command(
    device_id: UUID,
    prepared: dict[str, Any],
    mqtt_client: mqtt.Client,
) -> dict[str, Any]:
    """Publish a prepared command to the active device."""
    command = prepared["command"]
    command_id = command["commandId"]

    node_id = get_active_device_node_id(device_id)
    if node_id is None:
        raise ValueError("Active device not found")

    try:
        publish_command(mqtt_client, node_id, command)
    except Exception as exc:
        try:
            mark_command_failed(command_id, str(exc))
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "Failed to mark command %s as FAILED",
                command_id,
            )
        raise

    marked = mark_command_sent(command_id)

    return {
        "command": command,
        "record": prepared["record"],
        "nodeId": node_id,
        "sent": marked,
    }
