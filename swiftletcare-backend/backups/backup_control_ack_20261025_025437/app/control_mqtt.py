
import json
from typing import Any

import paho.mqtt.client as mqtt


COMMAND_TOPIC_TEMPLATE = "swiftlet/command/{node_id}"
ACK_TOPIC_TEMPLATE = "swiftlet/ack/{node_id}"


def build_command_topic(node_id: str) -> str:
    """Return the command topic for a device."""
    if not node_id or "/" in node_id or "+" in node_id or "#" in node_id:
        raise ValueError("Invalid node_id")
    return COMMAND_TOPIC_TEMPLATE.format(node_id=node_id)


def build_ack_topic(node_id: str) -> str:
    """Return the ACK topic for a device."""
    if not node_id or "/" in node_id or "+" in node_id or "#" in node_id:
        raise ValueError("Invalid node_id")
    return ACK_TOPIC_TEMPLATE.format(node_id=node_id)


def publish_command(
    client: mqtt.Client,
    node_id: str,
    payload: dict[str, Any],
) -> None:
    """
    Publish a command using an already-configured MQTT client.

    This function does not connect to a broker. The caller must explicitly
    decide when publishing is allowed.
    """
    if not client.is_connected():
        raise RuntimeError("MQTT client is not connected")

    if not payload.get("commandId"):
        raise ValueError("commandId is required")

    if payload.get("action") not in {"SET_RELAY", "UPDATE_THRESHOLDS"}:
        raise ValueError("Unsupported command action")

    topic = build_command_topic(node_id)
    result = client.publish(
        topic,
        json.dumps(payload, separators=(",", ":")),
        qos=1,
        retain=False,
    )

    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError(f"MQTT publish failed with code {result.rc}")


def subscribe_ack(
    client: mqtt.Client,
    node_id: str,
) -> None:
    """Subscribe to the ACK topic for a device."""
    if not client.is_connected():
        raise RuntimeError("MQTT client is not connected")

    result, _ = client.subscribe(build_ack_topic(node_id), qos=1)
    if result != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError(f"MQTT subscribe failed with code {result}")
