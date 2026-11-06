"""Tests for the CP4.6A Local E2E Demo Harness (Simulator, Local Broker, E2E Flow)."""

import asyncio
import json
from pathlib import Path
import struct
import uuid

import pytest

from app.mqtt.dispatcher import MessageDispatcher
from app.mqtt.topics import parse_topic
from app.repositories.command_repository import InMemoryCommandRepository
from app.repositories.presence_repository import InMemoryDevicePresenceRepository
from app.repositories.telemetry_repository import InMemoryTelemetryRepository
from app.schemas.command import AckPayload
from app.schemas.presence import HeartbeatPayload
from app.schemas.telemetry import TelemetryPayload
from app.services.ack_service import AckService
from app.services.command_service import DeviceCommandService
from app.services.heartbeat_service import HeartbeatService
from app.services.presence_service import DevicePresenceService
from app.services.status_service import StatusService
from app.services.telemetry_service import TelemetryService
from demo.device_simulator import ESP32DeviceSimulator
from demo.local_broker import (
    LocalMQTTBroker,
    MalformedMQTTPacketError,
    encode_remaining_length,
    read_bytes_field,
    read_utf8_string,
    topic_matches_filter,
    unpack_u16,
)


class FakeMQTTCommandBridge:
    """Bridges DeviceCommandService.publisher directly to ESP32DeviceSimulator and MessageDispatcher."""

    def __init__(self, simulator: ESP32DeviceSimulator, dispatcher: MessageDispatcher):
        self.simulator = simulator
        self.dispatcher = dispatcher
        self.published_messages: list[tuple[str, str, int, bool]] = []

    def publish(
        self,
        topic: str,
        payload: str | bytes,
        qos: int = 1,
        retain: bool = False,
    ) -> bool:
        raw_str = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        self.published_messages.append((topic, raw_str, qos, retain))

        # Deliver command to simulator and forward returned ACK to IoT Service dispatcher
        ack_payload = self.simulator.handle_command_payload(raw_str)
        if ack_payload is not None:
            ack_topic = parse_topic(f"swiftlet/ack/{self.simulator.device_id}")
            self.dispatcher.dispatch(ack_topic, json.dumps(ack_payload).encode("utf-8"))
        return True


def test_simulator_builds_valid_canonical_v1_payloads():
    """Verify simulator telemetry and heartbeat payloads strictly conform to Canonical V1 schemas."""
    sim = ESP32DeviceSimulator(device_id="SWC-NODE-001")

    telemetry_raw = sim.build_telemetry_payload()
    validated_telemetry = TelemetryPayload.model_validate(telemetry_raw)
    assert validated_telemetry.deviceId == "SWC-NODE-001"
    assert validated_telemetry.state.mode == "AUTO"
    assert validated_telemetry.actuators.misting is False
    assert validated_telemetry.actuators.fan is False

    heartbeat_raw = sim.build_heartbeat_payload()
    validated_hb = HeartbeatPayload.model_validate(heartbeat_raw)
    assert validated_hb.deviceId == "SWC-NODE-001"
    assert validated_hb.uptime >= 0
    assert validated_hb.mockMode is True


def test_simulator_set_relay_and_update_thresholds_contract():
    """Verify simulator command handling for SET_RELAY and UPDATE_THRESHOLDS."""
    sim = ESP32DeviceSimulator(device_id="SWC-NODE-001")
    assert sim.mode == "AUTO"
    assert sim.actuators["misting"] is False

    cmd_id_1 = str(uuid.uuid4())
    # 1. SET_RELAY misting -> 1 switches mode to MANUAL and turns misting ON
    ack1 = sim.handle_command_payload(
        json.dumps(
            {
                "commandId": cmd_id_1,
                "action": "SET_RELAY",
                "target": "misting",
                "state": 1,
            }
        )
    )
    assert ack1 is not None
    validated_ack1 = AckPayload.model_validate(ack1)
    assert validated_ack1.commandId == cmd_id_1
    assert validated_ack1.status == "SUCCESS"
    assert validated_ack1.mode == "MANUAL"
    assert sim.actuators["misting"] is True
    assert sim.mode == "MANUAL"

    cmd_id_2 = str(uuid.uuid4())
    # 2. UPDATE_THRESHOLDS -> isAutoMode=True updates targets and restores AUTO mode
    ack2 = sim.handle_command_payload(
        json.dumps(
            {
                "commandId": cmd_id_2,
                "action": "UPDATE_THRESHOLDS",
                "targetTemp": 28.5,
                "targetHum": 82.0,
                "isAutoMode": True,
            }
        )
    )
    assert ack2 is not None
    validated_ack2 = AckPayload.model_validate(ack2)
    assert validated_ack2.commandId == cmd_id_2
    assert validated_ack2.status == "SUCCESS"
    assert validated_ack2.mode == "AUTO"
    assert sim.mode == "AUTO"
    assert sim.target_temp == 28.5
    assert sim.target_hum == 82.0

    cmd_id_3 = str(uuid.uuid4())
    # 3. Unknown relay target returns FAILED ACK
    ack3 = sim.handle_command_payload(
        json.dumps(
            {
                "commandId": cmd_id_3,
                "action": "SET_RELAY",
                "target": "siren",
                "state": 1,
            }
        )
    )
    assert ack3 is not None
    validated_ack3 = AckPayload.model_validate(ack3)
    assert validated_ack3.status == "FAILED"


def test_fast_ack_race_preserves_terminal_status_and_published_at():
    """Verify fast ACK arriving before publisher.publish() returns is not overwritten to PUBLISHED."""
    command_repo = InMemoryCommandRepository()
    ack_service = AckService(repository=command_repo)
    sim = ESP32DeviceSimulator(device_id="SWC-NODE-001")
    dispatcher = MessageDispatcher(ack_svc=ack_service)
    bridge = FakeMQTTCommandBridge(simulator=sim, dispatcher=dispatcher)
    command_service = DeviceCommandService(repository=command_repo, publisher=bridge)

    # Because FakeMQTTCommandBridge processes the command and dispatches the ACK
    # synchronously inside publish(), the command is already SUCCESS when publish() returns.
    returned_cmd = command_service.send_set_relay_command("SWC-NODE-001", "fan", 1)
    stored_cmd = command_service.get_command(returned_cmd.command_id)

    assert returned_cmd.status == "SUCCESS"
    assert returned_cmd.published_at is not None
    assert returned_cmd.acknowledged_at is not None
    assert returned_cmd.ack_status == "SUCCESS"
    assert returned_cmd.ack_mode == "MANUAL"

    assert stored_cmd is not None
    assert stored_cmd.status == "SUCCESS"
    assert stored_cmd.published_at is not None
    assert stored_cmd.acknowledged_at is not None


def test_full_e2e_simulator_to_iot_service_flow():
    """Verify full E2E flow: status/heartbeat/telemetry -> command -> simulator ACK -> SUCCESS."""
    telemetry_repo = InMemoryTelemetryRepository()
    presence_repo = InMemoryDevicePresenceRepository()
    command_repo = InMemoryCommandRepository()

    captured_events = []

    class CapturingPublisher:
        def publish(self, event):
            captured_events.append(event)

    pub = CapturingPublisher()
    telemetry_service = TelemetryService(repository=telemetry_repo, realtime_publisher=pub)
    presence_service = DevicePresenceService(repository=presence_repo, realtime_publisher=pub)
    heartbeat_service = HeartbeatService(presence_svc=presence_service)
    status_service = StatusService(presence_svc=presence_service)
    ack_service = AckService(repository=command_repo, realtime_publisher=pub)

    dispatcher = MessageDispatcher(
        telemetry_svc=telemetry_service,
        heartbeat_svc=heartbeat_service,
        status_svc=status_service,
        ack_svc=ack_service,
    )

    sim = ESP32DeviceSimulator(device_id="SWC-NODE-001")
    bridge = FakeMQTTCommandBridge(simulator=sim, dispatcher=dispatcher)
    command_service = DeviceCommandService(repository=command_repo, publisher=bridge)

    # Step A: Simulator connects and publishes online status + heartbeat + telemetry
    dispatcher.dispatch(parse_topic("swiftlet/status/SWC-NODE-001"), b'{"status":"online"}')
    dispatcher.dispatch(
        parse_topic("swiftlet/heartbeat/SWC-NODE-001"),
        json.dumps(sim.build_heartbeat_payload()).encode("utf-8"),
    )
    dispatcher.dispatch(
        parse_topic("swiftlet/telemetry/SWC-NODE-001"),
        json.dumps(sim.build_telemetry_payload()).encode("utf-8"),
    )

    presence = presence_service.get_presence("SWC-NODE-001")
    assert presence is not None
    assert presence.status == "ONLINE"

    latest_telemetry = telemetry_repo.get_latest("SWC-NODE-001")
    assert latest_telemetry is not None
    assert latest_telemetry.state.mode == "AUTO"
    assert latest_telemetry.actuators.misting is False

    # Step B: Issue SET_RELAY command -> Simulator flips misting=True, mode=MANUAL & returns ACK
    dispatched_cmd = command_service.send_set_relay_command("SWC-NODE-001", "misting", 1)
    final_cmd = command_service.get_command(dispatched_cmd.command_id)
    assert final_cmd is not None
    assert final_cmd.status == "SUCCESS"
    assert final_cmd.ack_mode == "MANUAL"
    assert sim.actuators["misting"] is True
    assert sim.mode == "MANUAL"

    # Step C: Next telemetry reflects updated actuator and MANUAL mode
    dispatcher.dispatch(
        parse_topic("swiftlet/telemetry/SWC-NODE-001"),
        json.dumps(sim.build_telemetry_payload()).encode("utf-8"),
    )
    updated_telemetry = telemetry_repo.get_latest("SWC-NODE-001")
    assert updated_telemetry is not None
    assert updated_telemetry.actuators.misting is True
    assert updated_telemetry.state.mode == "MANUAL"

    # Step D: Simulator goes offline
    dispatcher.dispatch(parse_topic("swiftlet/status/SWC-NODE-001"), b'{"status":"offline"}')
    offline_presence = presence_service.get_presence("SWC-NODE-001")
    assert offline_presence is not None
    assert offline_presence.status == "OFFLINE"

    event_types = [e.type for e in captured_events]
    assert "presence.updated" in event_types
    assert "telemetry.updated" in event_types
    assert "command.updated" in event_types


def test_broker_bounds_helpers_reject_truncated_buffers():
    """Verify packet parsing helpers raise MalformedMQTTPacketError instead of struct.error."""
    with pytest.raises(MalformedMQTTPacketError):
        unpack_u16(b"\x00", 0)

    # Declared string length 8779 bytes in a 10-byte buffer
    bad_buf = struct.pack(">H", 8779) + b"short"
    with pytest.raises(MalformedMQTTPacketError):
        read_utf8_string(bad_buf, 0)

    with pytest.raises(MalformedMQTTPacketError):
        read_bytes_field(bad_buf, 0)


def test_local_mqtt_broker_survives_malformed_and_http_clients():
    """Verify non-MQTT (e.g. Chrome HTTP) and truncated packets do not crash broker or disrupt MQTT clients."""
    assert topic_matches_filter("swiftlet/telemetry/SWC-NODE-001", "swiftlet/telemetry/+")
    assert topic_matches_filter("swiftlet/ack/SWC-NODE-001", "swiftlet/#")
    assert not topic_matches_filter("swiftlet/telemetry/SWC-NODE-001", "swiftlet/status/+")
    assert not topic_matches_filter("other/telemetry/SWC-NODE-001", "swiftlet/telemetry/+")

    def build_connect_pkt(client_id: str) -> bytes:
        proto = b"\x00\x04MQTT\x04\x02\x00\x3c"
        cid_bytes = client_id.encode("utf-8")
        body = proto + struct.pack(">H", len(cid_bytes)) + cid_bytes
        return b"\x10" + encode_remaining_length(len(body)) + body

    def build_subscribe_pkt(packet_id: int, topic_filter: str, qos: int = 1) -> bytes:
        tf_bytes = topic_filter.encode("utf-8")
        body = struct.pack(">H", packet_id) + struct.pack(">H", len(tf_bytes)) + tf_bytes + bytes([qos])
        return b"\x82" + encode_remaining_length(len(body)) + body

    async def run_resilience_scenario():
        broker = LocalMQTTBroker(host="127.0.0.1", port=0)
        await broker.start()
        port = broker.port

        try:
            # 1. Valid subscriber connects and subscribes to swiftlet/telemetry/+
            sub_reader, sub_writer = await asyncio.open_connection("127.0.0.1", port)
            sub_writer.write(build_connect_pkt("valid-sub"))
            await sub_writer.drain()
            connack = await asyncio.wait_for(sub_reader.readexactly(4), timeout=2.0)
            assert connack == b"\x20\x02\x00\x00"

            sub_writer.write(build_subscribe_pkt(1, "swiftlet/telemetry/+", 1))
            await sub_writer.drain()
            suback = await asyncio.wait_for(sub_reader.readexactly(5), timeout=2.0)
            assert suback[:2] == b"\x90\x03"

            # 2. Simulate Chrome browser sending HTTP GET request to port 1883
            http_reader, http_writer = await asyncio.open_connection("127.0.0.1", port)
            http_writer.write(b"GET / HTTP/1.1\r\nHost: 127.0.0.1:1883\r\n\r\n")
            await http_writer.drain()
            eof_data = await asyncio.wait_for(http_reader.read(64), timeout=2.0)
            assert eof_data == b""
            http_writer.close()

            # 3. Simulate malformed CONNECT with bogus 8779-byte string length in 8-byte body
            bad_reader, bad_writer = await asyncio.open_connection("127.0.0.1", port)
            bad_body = struct.pack(">H", 8779) + b"MQTT\x04\x02"
            bad_writer.write(b"\x10" + encode_remaining_length(len(bad_body)) + bad_body)
            await bad_writer.drain()
            bad_eof = await asyncio.wait_for(bad_reader.read(64), timeout=2.0)
            assert bad_eof == b""
            bad_writer.close()

            # 4. Valid publisher connects and publishes telemetry -> valid subscriber still receives it
            pub_reader, pub_writer = await asyncio.open_connection("127.0.0.1", port)
            pub_writer.write(build_connect_pkt("valid-pub"))
            await pub_writer.drain()
            pub_connack = await asyncio.wait_for(pub_reader.readexactly(4), timeout=2.0)
            assert pub_connack == b"\x20\x02\x00\x00"

            topic_bytes = b"swiftlet/telemetry/SWC-NODE-001"
            payload_bytes = b'{"ok":true}'
            pub_body = struct.pack(">H", len(topic_bytes)) + topic_bytes + payload_bytes
            pub_writer.write(b"\x30" + encode_remaining_length(len(pub_body)) + pub_body)
            await pub_writer.drain()

            # Subscriber receives the published packet
            first_b = await asyncio.wait_for(sub_reader.readexactly(1), timeout=2.0)
            assert (first_b[0] & 0xF0) == 0x30
            rem_b = await asyncio.wait_for(sub_reader.readexactly(1), timeout=2.0)
            delivered_body = await asyncio.wait_for(sub_reader.readexactly(rem_b[0]), timeout=2.0)
            assert payload_bytes in delivered_body

            # Clean disconnect
            pub_writer.write(b"\xE0\x00")
            sub_writer.write(b"\xE0\x00")
            await pub_writer.drain()
            await sub_writer.drain()
            pub_writer.close()
            sub_writer.close()
        finally:
            await broker.stop()

    asyncio.run(run_resilience_scenario())


def test_esp32_firmware_sketch_static_contract_v1_alignment():
    """Verify firmware/esp32/sketch.ino is aligned with Canonical MQTT Contract V1."""
    repo_root = Path(__file__).resolve().parents[3]
    sketch_path = repo_root / "firmware" / "esp32" / "sketch.ino"
    assert sketch_path.exists(), f"Missing firmware sketch at {sketch_path}"

    source = sketch_path.read_text(encoding="utf-8")

    # 1. Canonical device ID and topics
    assert 'const char* DEVICE_ID       = "SWC-NODE-001";' in source
    for ch in ("telemetry", "heartbeat", "command", "ack", "status"):
        topic_str = f"swiftlet/{ch}/SWC-NODE-001"
        assert f'"{topic_str}"' in source
        parsed = parse_topic(topic_str)
        assert parsed.channel == ch and parsed.device_code == "SWC-NODE-001"

    # 2. Legacy fields removed
    assert '"nodeId"' not in source
    assert 'metrics["temp"]' not in source
    assert 'metrics["soundOk"]' not in source
    assert 'state["wifiRssi"]' not in source
    assert 'doc["timestamp"]' not in source
    assert 'ack["timestamp"]' not in source
    assert 'hb["type"]' not in source

    # 3. Canonical V1 fields present
    assert 'doc["deviceId"] = DEVICE_ID;' in source
    assert 'hb["deviceId"] = DEVICE_ID;' in source
    assert 'ack["deviceId"] = DEVICE_ID;' in source
    assert 'metrics["temperature"]' in source
    assert 'metrics["humidity"]' in source
    assert 'metrics["lux"]' in source
    assert 'metrics["co2"]' in source
    assert 'metrics["audioRms"]' in source
    assert 'metrics["audioHealthy"]' in source
    assert 'state["networkRssi"]' in source
    assert 'state["freeHeap"]' in source

    # 4. PubSubClient 512-byte buffer size & invalid relay target FAILED ACK
    assert "mqttClient.setBufferSize(512);" in source
    assert 'sendAck(cmdId, "FAILED", "Unsupported relay target");' in source

