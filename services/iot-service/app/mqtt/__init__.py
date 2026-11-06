"""MQTT package for SwiftletCare IoT Service.

Topics taxonomy (V1):
- swiftlet/telemetry/{device_code}
- swiftlet/heartbeat/{device_code}
- swiftlet/status/{device_code}
- swiftlet/command/{device_code}
- swiftlet/ack/{device_code}
"""

from app.mqtt.client import CommandPublisher, MQTTManager, mqtt_manager
from app.mqtt.dispatcher import MessageDispatcher, default_dispatcher
from app.mqtt.topics import (
    ALL_CHANNELS,
    INBOUND_CHANNELS,
    MQTT_NAMESPACE,
    OUTBOUND_CHANNELS,
    MQTTTopic,
    TopicParseError,
    build_topic,
    get_subscription_topics,
    parse_topic,
    validate_device_code,
)

__all__ = [
    "ALL_CHANNELS",
    "INBOUND_CHANNELS",
    "MQTT_NAMESPACE",
    "OUTBOUND_CHANNELS",
    "CommandPublisher",
    "MQTTManager",
    "MQTTTopic",
    "MessageDispatcher",
    "TopicParseError",
    "build_topic",
    "default_dispatcher",
    "get_subscription_topics",
    "mqtt_manager",
    "parse_topic",
    "validate_device_code",
]
