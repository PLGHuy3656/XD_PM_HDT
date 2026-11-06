import re
from dataclasses import dataclass
from typing import Literal

MQTT_NAMESPACE = "swiftlet"

INBOUND_CHANNELS = ("telemetry", "heartbeat", "status", "ack")
OUTBOUND_CHANNELS = ("command",)
ALL_CHANNELS = INBOUND_CHANNELS + OUTBOUND_CHANNELS

MQTTChannel = Literal[
    "telemetry",
    "heartbeat",
    "status",
    "command",
    "ack",
]

FORBIDDEN_DEVICE_CODE_CHARS = {"+", "#", "/", " ", "\t", "\r", "\n", "$"}


class TopicParseError(ValueError):
    """Raised when an MQTT topic fails validation or cannot be parsed."""
    pass


@dataclass(frozen=True)
class MQTTTopic:
    """Represents a validated SwiftletCare MQTT topic."""
    channel: str
    device_code: str
    namespace: str = MQTT_NAMESPACE

    @property
    def is_inbound(self) -> bool:
        """True if the channel is device-to-server."""
        return self.channel in INBOUND_CHANNELS

    @property
    def is_outbound(self) -> bool:
        """True if the channel is server-to-device."""
        return self.channel in OUTBOUND_CHANNELS


def validate_device_code(device_code: str) -> None:
    """Validates that a device_code conforms to SwiftletCare identity rules.

    Rejects:
    - Empty or whitespace-only strings
    - Leading or trailing whitespace
    - MQTT wildcards ('+', '#')
    - Path separators ('/')
    - Control/forbidden characters
    """
    if not isinstance(device_code, str):
        raise TopicParseError("Device code must be a string")

    trimmed = device_code.strip()
    if not trimmed or len(device_code) == 0:
        raise TopicParseError("Missing or empty device code")

    if len(device_code) != len(trimmed):
        raise TopicParseError("Device code cannot contain leading or trailing whitespace")

    if any(char in device_code for char in FORBIDDEN_DEVICE_CODE_CHARS):
        raise TopicParseError(
            f"Device code '{device_code}' contains invalid characters (MQTT wildcards, separators, or whitespace)"
        )


def build_topic(channel: str, device_code: str) -> str:
    """Builds a canonical SwiftletCare MQTT topic string.

    Format: swiftlet/{channel}/{device_code}
    """
    if channel not in ALL_CHANNELS:
        raise TopicParseError(
            f"Unsupported MQTT channel: '{channel}'. Allowed: {ALL_CHANNELS}"
        )

    validate_device_code(device_code)
    return f"{MQTT_NAMESPACE}/{channel}/{device_code}"


def parse_topic(topic: str) -> MQTTTopic:
    """Parses and validates a SwiftletCare MQTT topic string.

    Format: swiftlet/{channel}/{device_code}
    Expected levels: exactly 3.
    """
    if not isinstance(topic, str):
        raise TopicParseError("Topic must be a string")

    parts = topic.split("/")

    if len(parts) != 3:
        raise TopicParseError(
            f"Invalid MQTT topic structure: expected 3 levels, got {len(parts)} in '{topic}'"
        )

    namespace, channel, device_code = parts

    if namespace != MQTT_NAMESPACE:
        raise TopicParseError(
            f"Invalid MQTT namespace: expected '{MQTT_NAMESPACE}', got '{namespace}'"
        )

    if channel not in ALL_CHANNELS:
        raise TopicParseError(
            f"Unsupported MQTT channel: '{channel}'. Allowed: {ALL_CHANNELS}"
        )

    validate_device_code(device_code)

    return MQTTTopic(
        channel=channel,
        device_code=device_code,
        namespace=namespace,
    )


def get_subscription_topics() -> list[str]:
    """Returns the list of wildcard subscription topics expected for IoT Service.

    Only subscribes to inbound (device-to-server) topics:
    - swiftlet/telemetry/+
    - swiftlet/heartbeat/+
    - swiftlet/status/+
    - swiftlet/ack/+

    Does NOT subscribe to swiftlet/command/+ because command is server-to-device.
    """
    return [f"{MQTT_NAMESPACE}/{channel}/+" for channel in INBOUND_CHANNELS]
