import logging
from unittest.mock import MagicMock

from app.mqtt.client import MQTTManager
from app.mqtt.dispatcher import MessageDispatcher
from app.mqtt.topics import MQTTTopic, parse_topic


class DummyMessage:
    def __init__(self, topic: str, payload: bytes):
        self.topic = topic
        self.payload = payload


def test_dispatcher_placeholder_handlers_execute_cleanly():
    dispatcher = MessageDispatcher()

    # Placeholders should execute without raising exceptions
    dispatcher.handle_telemetry("SWC-NODE-001", b'{"temp": 28.5}')
    dispatcher.handle_heartbeat("SWC-NODE-001", b'{"rssi": -65}')
    dispatcher.handle_status("SWC-NODE-001", b'{"online": true}')
    dispatcher.handle_ack("SWC-NODE-001", b'{"cmd_id": "c1", "status": "ok"}')


def test_dispatcher_custom_handler_registration():
    dispatcher = MessageDispatcher()
    mock_telemetry_handler = MagicMock()
    dispatcher.register_handler("telemetry", mock_telemetry_handler)

    parsed = parse_topic("swiftlet/telemetry/SWC-NODE-001")
    payload = b'{"temp": 30.1}'
    dispatcher.dispatch(parsed, payload)

    mock_telemetry_handler.assert_called_once_with("SWC-NODE-001", payload)


def test_dispatcher_inbound_command_ignored(caplog):
    dispatcher = MessageDispatcher()
    parsed = MQTTTopic(channel="command", device_code="SWC-NODE-001")

    with caplog.at_level(logging.WARNING):
        dispatcher.dispatch(parsed, b'{"action": "turn_on"}')

    assert "ignoring inbound command" in caplog.text


def test_manager_on_message_routes_valid_telemetry():
    mock_dispatcher = MagicMock(spec=MessageDispatcher)
    manager = MQTTManager(dispatcher=mock_dispatcher)

    msg = DummyMessage("swiftlet/telemetry/SWC-NODE-001", b'{"temp": 28}')
    manager.on_message(None, None, msg)

    mock_dispatcher.dispatch.assert_called_once()
    called_topic, called_payload = mock_dispatcher.dispatch.call_args[0]
    assert called_topic.channel == "telemetry"
    assert called_topic.device_code == "SWC-NODE-001"
    assert called_payload == b'{"temp": 28}'


def test_manager_on_message_rejects_malformed_topic(caplog):
    mock_dispatcher = MagicMock(spec=MessageDispatcher)
    manager = MQTTManager(dispatcher=mock_dispatcher)

    # Malformed topic: only 2 parts
    msg = DummyMessage("swiftlet/telemetry", b'{"temp": 28}')
    with caplog.at_level(logging.WARNING):
        manager.on_message(None, None, msg)

    # Must NOT call dispatcher
    mock_dispatcher.dispatch.assert_not_called()
    assert "Rejected malformed MQTT message" in caplog.text


def test_manager_on_message_rejects_wildcard_device(caplog):
    mock_dispatcher = MagicMock(spec=MessageDispatcher)
    manager = MQTTManager(dispatcher=mock_dispatcher)

    # Malformed topic: device code contains wildcard '+'
    msg = DummyMessage("swiftlet/telemetry/+", b'{"temp": 28}')
    with caplog.at_level(logging.WARNING):
        manager.on_message(None, None, msg)

    mock_dispatcher.dispatch.assert_not_called()
    assert "Rejected malformed MQTT message" in caplog.text
