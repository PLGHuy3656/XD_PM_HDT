import pytest

from app.mqtt.topics import (
    MQTT_NAMESPACE,
    MQTTTopic,
    TopicParseError,
    build_topic,
    get_subscription_topics,
    parse_topic,
    validate_device_code,
)


# ==============================================================================
# VALID TOPIC PARSING TESTS
# ==============================================================================

@pytest.mark.parametrize(
    "topic_str, expected_channel, expected_device, is_inbound, is_outbound",
    [
        ("swiftlet/telemetry/SWC-NODE-001", "telemetry", "SWC-NODE-001", True, False),
        ("swiftlet/heartbeat/SWC-NODE-001", "heartbeat", "SWC-NODE-001", True, False),
        ("swiftlet/status/SWC-NODE-001", "status", "SWC-NODE-001", True, False),
        ("swiftlet/command/SWC-NODE-001", "command", "SWC-NODE-001", False, True),
        ("swiftlet/ack/SWC-NODE-001", "ack", "SWC-NODE-001", True, False),
    ],
)
def test_parse_valid_topics(topic_str, expected_channel, expected_device, is_inbound, is_outbound):
    parsed = parse_topic(topic_str)
    assert isinstance(parsed, MQTTTopic)
    assert parsed.namespace == MQTT_NAMESPACE
    assert parsed.channel == expected_channel
    assert parsed.device_code == expected_device
    assert parsed.is_inbound is is_inbound
    assert parsed.is_outbound is is_outbound


# ==============================================================================
# INVALID TOPIC PARSING TESTS
# ==============================================================================

@pytest.mark.parametrize(
    "invalid_topic, expected_error_snippet",
    [
        ("swiftlet/telemetry", "expected 3 levels"),
        ("swiftlet/telemetry/farm/device", "expected 3 levels"),
        ("swiftlet", "expected 3 levels"),
        ("other/telemetry/SWC-NODE-001", "Invalid MQTT namespace"),
        ("backend/telemetry/SWC-NODE-001", "Invalid MQTT namespace"),
        ("swiftlet/unknown/SWC-NODE-001", "Unsupported MQTT channel"),
        ("swiftlet/sensors/SWC-NODE-001", "Unsupported MQTT channel"),
        ("swiftlet/telemetry/", "empty device code"),
        ("swiftlet/telemetry/   ", "empty device code"),
        ("swiftlet/telemetry/ SWC-001", "leading or trailing whitespace"),
        ("swiftlet/telemetry/SWC-001 ", "leading or trailing whitespace"),
        ("swiftlet/telemetry/+", "invalid characters"),
        ("swiftlet/telemetry/#", "invalid characters"),
        ("swiftlet/telemetry/SWC+01", "invalid characters"),
        ("swiftlet/telemetry/SWC#01", "invalid characters"),
    ],
)
def test_parse_invalid_topics(invalid_topic, expected_error_snippet):
    with pytest.raises(TopicParseError) as exc_info:
        parse_topic(invalid_topic)
    assert expected_error_snippet.lower() in str(exc_info.value).lower()


def test_parse_non_string_topic_raises_error():
    with pytest.raises(TopicParseError):
        parse_topic(None)  # type: ignore
    with pytest.raises(TopicParseError):
        parse_topic(12345)  # type: ignore


# ==============================================================================
# DEVICE IDENTITY VALIDATION TESTS
# ==============================================================================

@pytest.mark.parametrize(
    "valid_device_code",
    [
        "SWC-NODE-001",
        "esp32_device_42",
        "DEVICE-A",
        "NODE.01",
        "SENSOR-100",
    ],
)
def test_validate_valid_device_code(valid_device_code):
    validate_device_code(valid_device_code)  # Should not raise


@pytest.mark.parametrize(
    "invalid_device_code",
    [
        "",
        "   ",
        " SWC-001",
        "SWC-001 ",
        "+",
        "#",
        "SWC/001",
        "SWC+001",
        "SWC#001",
        "SWC 001",
        "SWC$001",
    ],
)
def test_validate_invalid_device_code(invalid_device_code):
    with pytest.raises(TopicParseError):
        validate_device_code(invalid_device_code)


# ==============================================================================
# TOPIC BUILDER TESTS
# ==============================================================================

def test_build_topic_valid():
    assert build_topic("telemetry", "SWC-NODE-001") == "swiftlet/telemetry/SWC-NODE-001"
    assert build_topic("heartbeat", "SWC-NODE-001") == "swiftlet/heartbeat/SWC-NODE-001"
    assert build_topic("status", "SWC-NODE-001") == "swiftlet/status/SWC-NODE-001"
    assert build_topic("command", "SWC-NODE-001") == "swiftlet/command/SWC-NODE-001"
    assert build_topic("ack", "SWC-NODE-001") == "swiftlet/ack/SWC-NODE-001"


def test_build_topic_invalid_channel():
    with pytest.raises(TopicParseError) as exc_info:
        build_topic("unsupported_channel", "SWC-NODE-001")
    assert "unsupported mqtt channel" in str(exc_info.value).lower()


def test_build_topic_invalid_device_code():
    with pytest.raises(TopicParseError) as exc_info:
        build_topic("telemetry", "SWC/NODE/001")
    assert "invalid characters" in str(exc_info.value).lower()


# ==============================================================================
# WILDCARD SUBSCRIPTION TESTS
# ==============================================================================

def test_wildcard_subscriptions():
    subscriptions = get_subscription_topics()

    assert set(subscriptions) == {
        "swiftlet/telemetry/+",
        "swiftlet/heartbeat/+",
        "swiftlet/status/+",
        "swiftlet/ack/+",
    }

    # Explicitly ensure backend does NOT subscribe to command channel
    assert "swiftlet/command/+" not in subscriptions
    assert "swiftlet/command/#" not in subscriptions
