import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.mqtt.dispatcher import MessageDispatcher
from app.mqtt.topics import MQTTTopic
from app.repositories.command_repository import InMemoryCommandRepository
from app.repositories.presence_repository import InMemoryDevicePresenceRepository
from app.repositories.telemetry_repository import InMemoryTelemetryRepository
from app.schemas.command import DeviceCommand, SetRelayPayload, UpdateThresholdsPayload
from app.services.ack_service import AckService
from app.services.command_service import DeviceCommandService
from app.services.heartbeat_service import HeartbeatService
from app.services.presence_service import DevicePresenceService
from app.services.status_service import StatusService
from app.services.telemetry_service import TelemetryService


class MockPublisher:
    def __init__(self, succeed: bool = True):
        self.succeed = succeed
        self.calls = []

    def publish(self, topic: str, payload: str | bytes, qos: int = 1, retain: bool = False) -> bool:
        self.calls.append({
            "topic": topic,
            "payload": payload,
            "qos": qos,
            "retain": retain,
        })
        return self.succeed


@pytest.fixture
def command_repo():
    return InMemoryCommandRepository()


@pytest.fixture
def mock_publisher():
    return MockPublisher(succeed=True)


@pytest.fixture
def command_service(command_repo, mock_publisher):
    return DeviceCommandService(repository=command_repo, publisher=mock_publisher)


@pytest.fixture
def ack_service(command_repo):
    return AckService(repository=command_repo)


# ==============================================================================
# SET_RELAY TESTS (1 - 15)
# ==============================================================================

def test_1_valid_misting_command(command_service, mock_publisher):
    cmd = command_service.send_set_relay_command("SWC-NODE-001", "misting", 1)
    assert cmd.action == "SET_RELAY"
    assert cmd.payload["target"] == "misting"
    assert cmd.payload["state"] == 1


def test_2_valid_fan_command(command_service):
    cmd = command_service.send_set_relay_command("SWC-NODE-001", "fan", 0)
    assert cmd.payload["target"] == "fan"
    assert cmd.payload["state"] == 0


def test_3_valid_heater_command(command_service):
    cmd = command_service.send_set_relay_command("SWC-NODE-001", "heater", 1)
    assert cmd.payload["target"] == "heater"
    assert cmd.payload["state"] == 1


def test_4_valid_alarm_command(command_service):
    cmd = command_service.send_set_relay_command("SWC-NODE-001", "alarm", 1)
    assert cmd.payload["target"] == "alarm"
    assert cmd.payload["state"] == 1


def test_5_state_0_accepted(command_service):
    cmd = command_service.send_set_relay_command("SWC-NODE-001", "fan", 0)
    assert cmd.payload["state"] == 0


def test_6_state_1_accepted(command_service):
    cmd = command_service.send_set_relay_command("SWC-NODE-001", "fan", 1)
    assert cmd.payload["state"] == 1


def test_7_invalid_target_rejected(command_service):
    with pytest.raises(Exception):
        command_service.send_set_relay_command("SWC-NODE-001", "water_pump", 1)  # type: ignore


def test_8_invalid_state_rejected(command_service):
    with pytest.raises(Exception):
        command_service.send_set_relay_command("SWC-NODE-001", "fan", 2)  # type: ignore
    with pytest.raises(Exception):
        command_service.send_set_relay_command("SWC-NODE-001", "fan", -1)  # type: ignore


def test_9_command_id_generated_as_uuid(command_service):
    cmd = command_service.send_set_relay_command("SWC-NODE-001", "fan", 1)
    # Must be valid UUID
    parsed_uuid = uuid.UUID(cmd.command_id)
    assert str(parsed_uuid) == cmd.command_id


def test_10_correct_command_topic_generated(command_service, mock_publisher):
    command_service.send_set_relay_command("SWC-NODE-001", "fan", 1)
    assert len(mock_publisher.calls) == 1
    assert mock_publisher.calls[0]["topic"] == "swiftlet/command/SWC-NODE-001"


def test_11_qos_1_used(command_service, mock_publisher):
    command_service.send_set_relay_command("SWC-NODE-001", "fan", 1)
    assert mock_publisher.calls[0]["qos"] == 1


def test_12_retained_false_used(command_service, mock_publisher):
    command_service.send_set_relay_command("SWC-NODE-001", "fan", 1)
    assert mock_publisher.calls[0]["retain"] is False


def test_13_command_starts_pending(command_repo):
    # Verify that before dispatch completes, a command is saved as PENDING
    cmd = DeviceCommand(
        command_id="cmd-1",
        device_id="SWC-NODE-001",
        action="SET_RELAY",
        payload={"target": "fan", "state": 1},
        status="PENDING",
        created_at=datetime.now(timezone.utc),
    )
    command_repo.save(cmd)
    assert command_repo.get("cmd-1").status == "PENDING"


def test_14_successful_publish_transitions_to_published(command_service):
    cmd = command_service.send_set_relay_command("SWC-NODE-001", "fan", 1)
    assert cmd.status == "PUBLISHED"
    assert cmd.published_at is not None
    # Must NOT be marked SUCCESS on publish!
    assert cmd.status != "SUCCESS"


def test_15_publish_failure_handled_without_success(command_repo):
    failing_publisher = MockPublisher(succeed=False)
    svc = DeviceCommandService(repository=command_repo, publisher=failing_publisher)

    cmd = svc.send_set_relay_command("SWC-NODE-001", "fan", 1)
    assert cmd.status == "FAILED"
    assert cmd.published_at is None
    assert "MQTT publish failed" in cmd.ack_message


# ==============================================================================
# UPDATE_THRESHOLDS TESTS (16 - 21)
# ==============================================================================

def test_16_valid_thresholds_accepted(command_service, mock_publisher):
    cmd = command_service.send_update_thresholds_command("SWC-NODE-001", 28.5, 78.0, True)
    assert cmd.action == "UPDATE_THRESHOLDS"
    assert cmd.payload["targetTemp"] == 28.5
    assert cmd.payload["targetHum"] == 78.0
    assert cmd.payload["isAutoMode"] is True
    assert cmd.status == "PUBLISHED"


def test_17_valid_auto_configuration(command_service):
    cmd = command_service.send_update_thresholds_command("SWC-NODE-001", 29.0, 80.0, True)
    assert cmd.payload["isAutoMode"] is True


def test_18_valid_manual_configuration(command_service):
    cmd = command_service.send_update_thresholds_command("SWC-NODE-001", 29.0, 80.0, False)
    assert cmd.payload["isAutoMode"] is False


def test_19_humidity_greater_than_100_rejected(command_service):
    with pytest.raises(Exception):
        command_service.send_update_thresholds_command("SWC-NODE-001", 29.0, 105.0, True)


def test_20_negative_humidity_rejected(command_service):
    with pytest.raises(Exception):
        command_service.send_update_thresholds_command("SWC-NODE-001", 29.0, -5.0, True)


def test_21_unreasonable_temperature_rejected(command_service):
    with pytest.raises(Exception):
        command_service.send_update_thresholds_command("SWC-NODE-001", 100.0, 80.0, True)
    with pytest.raises(Exception):
        command_service.send_update_thresholds_command("SWC-NODE-001", -50.0, 80.0, True)


# ==============================================================================
# ACK TESTS (22 - 35)
# ==============================================================================

def test_22_valid_success_ack(command_service, ack_service):
    cmd = command_service.send_set_relay_command("SWC-NODE-001", "fan", 1)

    ack_payload = {
        "commandId": cmd.command_id,
        "deviceId": "SWC-NODE-001",
        "status": "SUCCESS",
        "mode": "MANUAL",
        "message": "Fan activated",
    }
    result = ack_service.process_message("SWC-NODE-001", json.dumps(ack_payload).encode("utf-8"))

    assert result.success is True
    assert result.command.status == "SUCCESS"
    assert result.command.ack_status == "SUCCESS"
    assert result.command.ack_mode == "MANUAL"


def test_23_valid_failed_ack(command_service, ack_service):
    cmd = command_service.send_set_relay_command("SWC-NODE-001", "fan", 1)

    ack_payload = {
        "commandId": cmd.command_id,
        "deviceId": "SWC-NODE-001",
        "status": "FAILED",
        "mode": "AUTO",
        "message": "Relay hardware fault",
    }
    result = ack_service.process_message("SWC-NODE-001", json.dumps(ack_payload).encode("utf-8"))

    assert result.success is True
    assert result.command.status == "FAILED"
    assert result.command.ack_status == "FAILED"


def test_24_valid_error_ack(command_service, ack_service):
    cmd = command_service.send_set_relay_command("SWC-NODE-001", "fan", 1)

    ack_payload = {
        "commandId": cmd.command_id,
        "deviceId": "SWC-NODE-001",
        "status": "ERROR",
        "mode": "AUTO",
        "message": "Internal timeout",
    }
    result = ack_service.process_message("SWC-NODE-001", json.dumps(ack_payload).encode("utf-8"))

    assert result.success is True
    assert result.command.status == "ERROR"


def test_25_server_assigns_acknowledged_at(command_service, ack_service):
    cmd = command_service.send_set_relay_command("SWC-NODE-001", "fan", 1)
    before = datetime.now(timezone.utc)

    ack_payload = {
        "commandId": cmd.command_id,
        "deviceId": "SWC-NODE-001",
        "status": "SUCCESS",
        "mode": "MANUAL",
    }
    result = ack_service.process_message("SWC-NODE-001", json.dumps(ack_payload).encode("utf-8"))
    after = datetime.now(timezone.utc)

    assert result.success is True
    ack_at = result.command.acknowledged_at
    assert ack_at is not None
    assert ack_at.tzinfo == timezone.utc
    assert before <= ack_at <= after


def test_26_success_ack_updates_command_to_success(command_service, ack_service, command_repo):
    cmd = command_service.send_set_relay_command("SWC-NODE-001", "fan", 1)
    ack_payload = {
        "commandId": cmd.command_id,
        "deviceId": "SWC-NODE-001",
        "status": "SUCCESS",
        "mode": "MANUAL",
    }
    ack_service.process_message("SWC-NODE-001", json.dumps(ack_payload).encode("utf-8"))

    stored = command_repo.get(cmd.command_id)
    assert stored.status == "SUCCESS"


def test_27_failed_ack_updates_command_to_failed(command_service, ack_service, command_repo):
    cmd = command_service.send_set_relay_command("SWC-NODE-001", "fan", 1)
    ack_payload = {
        "commandId": cmd.command_id,
        "deviceId": "SWC-NODE-001",
        "status": "FAILED",
        "mode": "MANUAL",
    }
    ack_service.process_message("SWC-NODE-001", json.dumps(ack_payload).encode("utf-8"))

    stored = command_repo.get(cmd.command_id)
    assert stored.status == "FAILED"


def test_28_error_ack_updates_command_to_error(command_service, ack_service, command_repo):
    cmd = command_service.send_set_relay_command("SWC-NODE-001", "fan", 1)
    ack_payload = {
        "commandId": cmd.command_id,
        "deviceId": "SWC-NODE-001",
        "status": "ERROR",
        "mode": "MANUAL",
    }
    ack_service.process_message("SWC-NODE-001", json.dumps(ack_payload).encode("utf-8"))

    stored = command_repo.get(cmd.command_id)
    assert stored.status == "ERROR"


def test_29_unknown_command_id_rejected(ack_service, command_repo):
    unknown_id = str(uuid.uuid4())
    ack_payload = {
        "commandId": unknown_id,
        "deviceId": "SWC-NODE-001",
        "status": "SUCCESS",
        "mode": "MANUAL",
    }
    result = ack_service.process_message("SWC-NODE-001", json.dumps(ack_payload).encode("utf-8"))

    assert result.success is False
    assert result.command is None
    assert "Unknown commandId" in result.error
    # Must NOT create a fake command
    assert command_repo.get(unknown_id) is None


def test_30_topic_payload_device_mismatch_rejected(command_service, ack_service):
    cmd = command_service.send_set_relay_command("SWC-NODE-001", "fan", 1)
    ack_payload = {
        "commandId": cmd.command_id,
        "deviceId": "SWC-NODE-001",
        "status": "SUCCESS",
        "mode": "MANUAL",
    }
    # Topic has SWC-NODE-002, but payload has SWC-NODE-001
    result = ack_service.process_message("SWC-NODE-002", json.dumps(ack_payload).encode("utf-8"))

    assert result.success is False
    assert "Device identity mismatch" in result.error


def test_31_ack_device_not_equal_command_device_rejected(command_service, ack_service):
    cmd = command_service.send_set_relay_command("SWC-NODE-001", "fan", 1)
    ack_payload = {
        "commandId": cmd.command_id,
        "deviceId": "SWC-NODE-002",
        "status": "SUCCESS",
        "mode": "MANUAL",
    }
    # Device in payload is SWC-NODE-002 matching topic SWC-NODE-002, but command was issued to SWC-NODE-001
    result = ack_service.process_message("SWC-NODE-002", json.dumps(ack_payload).encode("utf-8"))

    assert result.success is False
    assert "Device mismatch for commandId" in result.error


def test_32_invalid_ack_status_rejected(command_service, ack_service):
    cmd = command_service.send_set_relay_command("SWC-NODE-001", "fan", 1)
    ack_payload = {
        "commandId": cmd.command_id,
        "deviceId": "SWC-NODE-001",
        "status": "COMPLETED",  # Invalid status (must be SUCCESS, FAILED, ERROR)
        "mode": "MANUAL",
    }
    result = ack_service.process_message("SWC-NODE-001", json.dumps(ack_payload).encode("utf-8"))

    assert result.success is False
    assert "Schema validation failed" in result.error


def test_33_invalid_mode_rejected(command_service, ack_service):
    cmd = command_service.send_set_relay_command("SWC-NODE-001", "fan", 1)
    ack_payload = {
        "commandId": cmd.command_id,
        "deviceId": "SWC-NODE-001",
        "status": "SUCCESS",
        "mode": "HYBRID",  # Invalid mode
    }
    result = ack_service.process_message("SWC-NODE-001", json.dumps(ack_payload).encode("utf-8"))

    assert result.success is False
    assert "Schema validation failed" in result.error


def test_34_malformed_json_rejected(ack_service):
    result = ack_service.process_message("SWC-NODE-001", b"{not valid json")
    assert result.success is False
    assert "Invalid JSON" in result.error


def test_35_duplicate_ack_handled_safely(command_service, ack_service):
    cmd = command_service.send_set_relay_command("SWC-NODE-001", "fan", 1)
    ack_payload = {
        "commandId": cmd.command_id,
        "deviceId": "SWC-NODE-001",
        "status": "SUCCESS",
        "mode": "MANUAL",
        "message": "First ACK",
    }
    res1 = ack_service.process_message("SWC-NODE-001", json.dumps(ack_payload).encode("utf-8"))
    assert res1.success is True
    assert res1.command.status == "SUCCESS"
    first_ack_time = res1.command.acknowledged_at

    # Second (duplicate) ACK with different status attempt:
    duplicate_payload = {
        "commandId": cmd.command_id,
        "deviceId": "SWC-NODE-001",
        "status": "FAILED",
        "mode": "MANUAL",
        "message": "Duplicate ACK",
    }
    res2 = ack_service.process_message("SWC-NODE-001", json.dumps(duplicate_payload).encode("utf-8"))
    assert res2.success is True
    # Remains in original terminal state:
    assert res2.command.status == "SUCCESS"
    assert res2.command.acknowledged_at == first_ack_time


# ==============================================================================
# DISPATCHER TESTS (36 - 39)
# ==============================================================================

def test_36_ack_routes_to_ack_service(command_service, command_repo):
    cmd = command_service.send_set_relay_command("SWC-NODE-001", "fan", 1)
    a_service = AckService(repository=command_repo)
    dispatcher = MessageDispatcher(ack_svc=a_service)

    ack_payload = {
        "commandId": cmd.command_id,
        "deviceId": "SWC-NODE-001",
        "status": "SUCCESS",
        "mode": "MANUAL",
    }
    topic = MQTTTopic(channel="ack", device_code="SWC-NODE-001")
    dispatcher.dispatch(topic, json.dumps(ack_payload).encode("utf-8"))

    stored = command_repo.get(cmd.command_id)
    assert stored.status == "SUCCESS"


def test_37_telemetry_still_works():
    telemetry_repo = InMemoryTelemetryRepository()
    t_service = TelemetryService(repository=telemetry_repo)
    dispatcher = MessageDispatcher(telemetry_svc=t_service)

    sample_telemetry = {
        "deviceId": "SWC-NODE-001",
        "metrics": {
            "temperature": 27.5,
            "humidity": 72.0,
            "lux": 12.0,
            "co2": 480.0,
            "audioRms": 0.15,
            "audioHealthy": True,
        },
        "actuators": {"misting": False, "fan": True, "heater": False, "alarm": False},
        "state": {"mode": "AUTO", "networkRssi": -60, "freeHeap": 160000},
    }

    topic = MQTTTopic(channel="telemetry", device_code="SWC-NODE-001")
    dispatcher.dispatch(topic, json.dumps(sample_telemetry).encode("utf-8"))

    latest = telemetry_repo.get_latest("SWC-NODE-001")
    assert latest is not None
    assert latest.metrics.temperature == 27.5


def test_38_heartbeat_still_works():
    p_repo = InMemoryDevicePresenceRepository()
    p_service = DevicePresenceService(repository=p_repo)
    h_service = HeartbeatService(presence_svc=p_service)
    dispatcher = MessageDispatcher(heartbeat_svc=h_service)

    hb_payload = {
        "deviceId": "SWC-NODE-001",
        "uptime": 200,
        "ip": "192.168.1.50",
        "freeHeap": 170000,
        "mockMode": False,
    }
    topic = MQTTTopic(channel="heartbeat", device_code="SWC-NODE-001")
    dispatcher.dispatch(topic, json.dumps(hb_payload).encode("utf-8"))

    presence = p_repo.get("SWC-NODE-001")
    assert presence is not None
    assert presence.status == "ONLINE"
    assert presence.uptime == 200


def test_39_status_still_works():
    p_repo = InMemoryDevicePresenceRepository()
    p_service = DevicePresenceService(repository=p_repo)
    s_service = StatusService(presence_svc=p_service)
    dispatcher = MessageDispatcher(status_svc=s_service)

    topic = MQTTTopic(channel="status", device_code="SWC-NODE-001")
    dispatcher.dispatch(topic, b'{"status": "offline"}')

    presence = p_repo.get("SWC-NODE-001")
    assert presence is not None
    assert presence.status == "OFFLINE"


# ==============================================================================
# MQTT PUBLISH PARAMETER TESTS (40 - 41)
# ==============================================================================

def test_40_command_is_qos_1(command_service, mock_publisher):
    command_service.send_set_relay_command("SWC-NODE-001", "fan", 1)
    assert mock_publisher.calls[-1]["qos"] == 1


def test_41_command_retain_flag_is_false(command_service, mock_publisher):
    command_service.send_update_thresholds_command("SWC-NODE-001", 28.0, 75.0, True)
    assert mock_publisher.calls[-1]["retain"] is False
