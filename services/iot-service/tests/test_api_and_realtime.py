import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mqtt.dispatcher import MessageDispatcher
from app.mqtt.topics import MQTTTopic
from app.realtime.publisher import WebSocketConnectionManager, ws_manager
from app.repositories.command_repository import default_command_repository
from app.repositories.presence_repository import default_presence_repository
from app.repositories.telemetry_repository import default_telemetry_repository
from app.routes.dependencies import get_command_service
from app.schemas.api import RealtimeEvent
from app.services.ack_service import AckService, ack_service
from app.services.command_service import DeviceCommandService
from app.services.heartbeat_service import HeartbeatService, heartbeat_service
from app.services.presence_service import DevicePresenceService, presence_service
from app.services.status_service import StatusService, status_service
from app.services.telemetry_service import TelemetryService, telemetry_service


class StubPublisher:
    def __init__(self, succeed: bool = True):
        self.succeed = succeed
        self.published = []

    def publish(self, topic: str, payload: str | bytes, qos: int = 1, retain: bool = False) -> bool:
        self.published.append({"topic": topic, "payload": payload, "qos": qos, "retain": retain})
        return self.succeed


@pytest.fixture(autouse=True)
def clean_state():
    """Resets in-memory repositories, WebSocket connections, and dependency overrides before each test."""
    default_telemetry_repository.clear()
    default_presence_repository.clear()
    default_command_repository.clear()
    ws_manager.clear()
    app.dependency_overrides.clear()
    yield
    default_telemetry_repository.clear()
    default_presence_repository.clear()
    default_command_repository.clear()
    ws_manager.clear()
    app.dependency_overrides.clear()


@pytest.fixture
def stub_publisher():
    pub = StubPublisher(succeed=True)
    svc = DeviceCommandService(repository=default_command_repository, publisher=pub)
    app.dependency_overrides[get_command_service] = lambda: svc
    return pub


@pytest.fixture
def client(stub_publisher):
    return TestClient(app)


@pytest.fixture
def sample_telemetry_payload():
    return {
        "deviceId": "SWC-NODE-001",
        "metrics": {
            "temperature": 29.2,
            "humidity": 80.5,
            "lux": 15.0,
            "co2": 620.0,
            "audioRms": 0.31,
            "audioHealthy": True,
        },
        "actuators": {
            "misting": False,
            "fan": True,
            "heater": False,
            "alarm": False,
        },
        "state": {
            "mode": "AUTO",
            "networkRssi": -51,
            "freeHeap": 183420,
        },
    }


@pytest.fixture
def sample_heartbeat_payload():
    return {
        "deviceId": "SWC-NODE-001",
        "uptime": 360,
        "ip": "192.168.1.10",
        "freeHeap": 180000,
        "mockMode": False,
    }


# ==============================================================================
# REST TELEMETRY TESTS (1 - 5)
# ==============================================================================

def test_1_latest_telemetry_returns_canonical_data(client, sample_telemetry_payload):
    telemetry_service.process_message("SWC-NODE-001", json.dumps(sample_telemetry_payload).encode("utf-8"))

    res = client.get("/api/iot/devices/SWC-NODE-001/telemetry/latest")
    assert res.status_code == 200
    body = res.json()
    assert body["deviceId"] == "SWC-NODE-001"
    assert "receivedAt" in body
    assert body["metrics"]["temperature"] == 29.2
    assert body["metrics"]["humidity"] == 80.5
    assert body["actuators"]["fan"] is True
    assert body["state"]["mode"] == "AUTO"
    assert body["state"]["networkRssi"] == -51
    assert body["state"]["freeHeap"] == 183420


def test_2_missing_telemetry_returns_404(client):
    res = client.get("/api/iot/devices/UNKNOWN-DEVICE/telemetry/latest")
    assert res.status_code == 404


def test_3_history_returns_data(client, sample_telemetry_payload):
    sample_telemetry_payload["metrics"]["temperature"] = 28.0
    telemetry_service.process_message("SWC-NODE-001", json.dumps(sample_telemetry_payload).encode("utf-8"))

    sample_telemetry_payload["metrics"]["temperature"] = 29.5
    telemetry_service.process_message("SWC-NODE-001", json.dumps(sample_telemetry_payload).encode("utf-8"))

    res = client.get("/api/iot/devices/SWC-NODE-001/telemetry")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 2
    # Newest first
    assert items[0]["metrics"]["temperature"] == 29.5
    assert items[1]["metrics"]["temperature"] == 28.0


def test_4_history_limit_respected(client, sample_telemetry_payload):
    for i in range(5):
        sample_telemetry_payload["metrics"]["temperature"] = 25.0 + i
        telemetry_service.process_message("SWC-NODE-001", json.dumps(sample_telemetry_payload).encode("utf-8"))

    res = client.get("/api/iot/devices/SWC-NODE-001/telemetry?limit=2")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 2
    assert items[0]["metrics"]["temperature"] == 29.0
    assert items[1]["metrics"]["temperature"] == 28.0


@pytest.mark.parametrize("invalid_limit", [0, -5, 501, "not_an_int"])
def test_5_invalid_history_limit_rejected(client, invalid_limit):
    res = client.get(f"/api/iot/devices/SWC-NODE-001/telemetry?limit={invalid_limit}")
    assert res.status_code == 422


# ==============================================================================
# PRESENCE TESTS (6 - 8)
# ==============================================================================

def test_6_known_presence_returned(client, sample_heartbeat_payload):
    heartbeat_service.process_message("SWC-NODE-001", json.dumps(sample_heartbeat_payload).encode("utf-8"))

    res = client.get("/api/iot/devices/SWC-NODE-001/presence")
    assert res.status_code == 200
    body = res.json()
    assert body["deviceId"] == "SWC-NODE-001"
    assert body["status"] == "ONLINE"
    assert body["lastSeen"] is not None
    assert body["lastHeartbeatAt"] is not None
    assert body["uptime"] == 360
    assert body["ip"] == "192.168.1.10"
    assert body["freeHeap"] == 180000
    assert body["mockMode"] is False


def test_7_unknown_device_presence_returns_404(client):
    res = client.get("/api/iot/devices/UNKNOWN-DEVICE/presence")
    assert res.status_code == 404


def test_8_list_presence_works(client, sample_heartbeat_payload):
    heartbeat_service.process_message("SWC-NODE-001", json.dumps(sample_heartbeat_payload).encode("utf-8"))
    status_service.process_message("SWC-NODE-002", b'{"status": "offline"}')

    res = client.get("/api/iot/devices/presence")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 2
    by_id = {item["deviceId"]: item for item in items}
    assert by_id["SWC-NODE-001"]["status"] == "ONLINE"
    assert by_id["SWC-NODE-002"]["status"] == "OFFLINE"


# ==============================================================================
# CONTROL TESTS (9 - 15)
# ==============================================================================

def test_9_valid_relay_request_creates_command(client, stub_publisher):
    res = client.post(
        "/api/iot/devices/SWC-NODE-001/commands/relay",
        json={"target": "fan", "state": 1},
    )
    assert res.status_code == 202
    body = res.json()
    assert body["deviceId"] == "SWC-NODE-001"
    assert body["action"] == "SET_RELAY"
    assert body["status"] == "PUBLISHED"
    assert "commandId" in body
    assert "createdAt" in body
    assert len(stub_publisher.published) == 1
    assert stub_publisher.published[0]["topic"] == "swiftlet/command/SWC-NODE-001"


def test_10_api_does_not_require_or_accept_frontend_command_id(client):
    # Without commandId -> accepted
    res_ok = client.post(
        "/api/iot/devices/SWC-NODE-001/commands/relay",
        json={"target": "misting", "state": 0},
    )
    assert res_ok.status_code == 202

    # Client supplying commandId -> rejected by extra="forbid"
    res_bad = client.post(
        "/api/iot/devices/SWC-NODE-001/commands/relay",
        json={"commandId": "client-injected-id", "target": "misting", "state": 0},
    )
    assert res_bad.status_code == 422


def test_11_invalid_relay_target_rejected(client):
    res = client.post(
        "/api/iot/devices/SWC-NODE-001/commands/relay",
        json={"target": "sprinkler", "state": 1},
    )
    assert res.status_code == 422


def test_12_invalid_relay_state_rejected(client):
    res = client.post(
        "/api/iot/devices/SWC-NODE-001/commands/relay",
        json={"target": "fan", "state": 2},
    )
    assert res.status_code == 422


def test_13_valid_config_command(client, stub_publisher):
    res = client.post(
        "/api/iot/devices/SWC-NODE-001/commands/config",
        json={"targetTemp": 29.0, "targetHum": 80.0, "isAutoMode": True},
    )
    assert res.status_code == 202
    body = res.json()
    assert body["deviceId"] == "SWC-NODE-001"
    assert body["action"] == "UPDATE_THRESHOLDS"
    assert body["status"] == "PUBLISHED"
    assert body["payload"]["targetTemp"] == 29.0
    assert body["payload"]["targetHum"] == 80.0
    assert body["payload"]["isAutoMode"] is True


def test_14_invalid_config_rejected(client):
    res = client.post(
        "/api/iot/devices/SWC-NODE-001/commands/config",
        json={"targetTemp": 29.0, "targetHum": 120.0, "isAutoMode": True},
    )
    assert res.status_code == 422


def test_15_returned_command_is_not_falsely_success(client):
    res = client.post(
        "/api/iot/devices/SWC-NODE-001/commands/relay",
        json={"target": "heater", "state": 1},
    )
    assert res.status_code == 202
    body = res.json()
    # Must be PUBLISHED, NOT SUCCESS before ACK arrives
    assert body["status"] == "PUBLISHED"
    assert body["status"] != "SUCCESS"
    assert body["acknowledgedAt"] is None


# ==============================================================================
# COMMAND QUERY TESTS (16 - 18)
# ==============================================================================

def test_16_known_command_returned(client):
    post_res = client.post(
        "/api/iot/devices/SWC-NODE-001/commands/relay",
        json={"target": "fan", "state": 1},
    )
    cmd_id = post_res.json()["commandId"]

    get_res = client.get(f"/api/iot/commands/{cmd_id}")
    assert get_res.status_code == 200
    body = get_res.json()
    assert body["commandId"] == cmd_id
    assert body["status"] == "PUBLISHED"


def test_17_unknown_command_returns_404(client):
    res = client.get("/api/iot/commands/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404


def test_18_ack_lifecycle_reflected_in_query(client):
    post_res = client.post(
        "/api/iot/devices/SWC-NODE-001/commands/relay",
        json={"target": "fan", "state": 1},
    )
    cmd_id = post_res.json()["commandId"]

    # Simulate ACK arrival from device
    ack_payload = {
        "commandId": cmd_id,
        "deviceId": "SWC-NODE-001",
        "status": "SUCCESS",
        "mode": "MANUAL",
        "message": "Relay switched",
    }
    ack_service.process_message("SWC-NODE-001", json.dumps(ack_payload).encode("utf-8"))

    get_res = client.get(f"/api/iot/commands/{cmd_id}")
    assert get_res.status_code == 200
    body = get_res.json()
    assert body["status"] == "SUCCESS"
    assert body["ackStatus"] == "SUCCESS"
    assert body["ackMode"] == "MANUAL"
    assert body["ackMessage"] == "Relay switched"
    assert body["acknowledgedAt"] is not None


# ==============================================================================
# WEBSOCKET / REALTIME TESTS (19 - 25)
# ==============================================================================

def test_19_telemetry_accepted_emits_telemetry_updated_ws(client, sample_telemetry_payload):
    with client.websocket_connect("/ws/iot") as ws:
        telemetry_service.process_message(
            "SWC-NODE-001", json.dumps(sample_telemetry_payload).encode("utf-8")
        )
        event = ws.receive_json()
        assert event["type"] == "telemetry.updated"
        assert event["deviceId"] == "SWC-NODE-001"
        assert "timestamp" in event
        assert event["data"]["deviceId"] == "SWC-NODE-001"
        assert event["data"]["metrics"]["temperature"] == 29.2


def test_20_presence_change_emits_presence_updated_ws(client, sample_heartbeat_payload):
    with client.websocket_connect("/ws/iot") as ws:
        heartbeat_service.process_message(
            "SWC-NODE-001", json.dumps(sample_heartbeat_payload).encode("utf-8")
        )
        event = ws.receive_json()
        assert event["type"] == "presence.updated"
        assert event["deviceId"] == "SWC-NODE-001"
        assert event["data"]["status"] == "ONLINE"
        assert event["data"]["uptime"] == 360


def test_21_ack_emits_command_updated_ws(client):
    post_res = client.post(
        "/api/iot/devices/SWC-NODE-001/commands/relay",
        json={"target": "fan", "state": 1},
    )
    cmd_id = post_res.json()["commandId"]

    with client.websocket_connect("/ws/iot") as ws:
        ack_payload = {
            "commandId": cmd_id,
            "deviceId": "SWC-NODE-001",
            "status": "SUCCESS",
            "mode": "MANUAL",
            "message": "Executed",
        }
        ack_service.process_message("SWC-NODE-001", json.dumps(ack_payload).encode("utf-8"))
        event = ws.receive_json()
        assert event["type"] == "command.updated"
        assert event["deviceId"] == "SWC-NODE-001"
        assert event["data"]["commandId"] == cmd_id
        assert event["data"]["status"] == "SUCCESS"
        assert event["data"]["ackMode"] == "MANUAL"


def test_22_event_envelope_uses_expected_structure(client, sample_telemetry_payload):
    with client.websocket_connect("/ws/iot") as ws:
        telemetry_service.process_message(
            "SWC-NODE-001", json.dumps(sample_telemetry_payload).encode("utf-8")
        )
        event = ws.receive_json()
        assert set(event.keys()) == {"type", "deviceId", "timestamp", "data"}
        assert isinstance(event["data"], dict)


def test_23_disconnected_ws_client_does_not_break_publisher(sample_telemetry_payload):
    manager = WebSocketConnectionManager()

    # Broken/disconnected WebSocket mock that raises on send_json
    broken_ws = MagicMock()
    async def broken_send(payload):
        raise RuntimeError("Socket closed abruptly")
    broken_ws.send_json = broken_send

    # Healthy WebSocket mock
    healthy_ws = MagicMock()
    received_messages = []
    async def healthy_send(payload):
        received_messages.append(payload)
    healthy_ws.send_json = healthy_send

    manager._connections.extend([broken_ws, healthy_ws])

    event = RealtimeEvent(
        type="telemetry.updated",
        deviceId="SWC-NODE-001",
        timestamp=datetime.now(timezone.utc),
        data={"deviceId": "SWC-NODE-001"},
    )
    # Publish should prune broken_ws and still deliver to healthy_ws without raising
    manager.publish(event)

    assert broken_ws not in manager.active_connections
    assert healthy_ws in manager.active_connections
    assert len(received_messages) == 1
    assert received_messages[0]["deviceId"] == "SWC-NODE-001"


def test_24_multiple_clients_supported(client, sample_telemetry_payload):
    with client.websocket_connect("/ws/iot") as ws1:
        with client.websocket_connect("/ws/iot") as ws2:
            telemetry_service.process_message(
                "SWC-NODE-001", json.dumps(sample_telemetry_payload).encode("utf-8")
            )
            ev1 = ws1.receive_json()
            ev2 = ws2.receive_json()
            assert ev1["type"] == "telemetry.updated"
            assert ev2["type"] == "telemetry.updated"
            assert ev1["deviceId"] == "SWC-NODE-001"
            assert ev2["deviceId"] == "SWC-NODE-001"


def test_25_domain_processing_succeeds_even_when_realtime_publishing_fails(
    sample_telemetry_payload, sample_heartbeat_payload
):
    class FailingRealtimePublisher:
        def publish(self, event: RealtimeEvent) -> None:
            raise RuntimeError("Simulated catastrophic realtime failure")

    failing_pub = FailingRealtimePublisher()

    t_svc = TelemetryService(
        repository=default_telemetry_repository,
        realtime_publisher=failing_pub,
    )
    p_svc = DevicePresenceService(
        repository=default_presence_repository,
        realtime_publisher=failing_pub,
    )
    h_svc = HeartbeatService(presence_svc=p_svc)
    a_svc = AckService(
        repository=default_command_repository,
        realtime_publisher=failing_pub,
    )

    # 1. Telemetry succeeds despite publisher exception
    t_res = t_svc.process_message(
        "SWC-NODE-001", json.dumps(sample_telemetry_payload).encode("utf-8")
    )
    assert t_res.success is True
    assert default_telemetry_repository.get_latest("SWC-NODE-001") is not None

    # 2. Heartbeat / presence succeeds despite publisher exception
    h_res = h_svc.process_message(
        "SWC-NODE-001", json.dumps(sample_heartbeat_payload).encode("utf-8")
    )
    assert h_res.success is True
    assert default_presence_repository.get("SWC-NODE-001").status == "ONLINE"

    # 3. ACK correlation succeeds despite publisher exception
    c_svc = DeviceCommandService(
        repository=default_command_repository,
        publisher=StubPublisher(succeed=True),
    )
    cmd = c_svc.send_set_relay_command("SWC-NODE-001", "fan", 1)
    ack_res = a_svc.process_message(
        "SWC-NODE-001",
        json.dumps(
            {
                "commandId": cmd.command_id,
                "deviceId": "SWC-NODE-001",
                "status": "SUCCESS",
                "mode": "MANUAL",
            }
        ).encode("utf-8"),
    )
    assert ack_res.success is True
    assert default_command_repository.get(cmd.command_id).status == "SUCCESS"


# ==============================================================================
# REGRESSION TESTS (26 - 30)
# ==============================================================================

def test_26_mqtt_telemetry_still_works(sample_telemetry_payload):
    dispatcher = MessageDispatcher()
    dispatcher.dispatch(
        MQTTTopic(channel="telemetry", device_code="SWC-NODE-001"),
        json.dumps(sample_telemetry_payload).encode("utf-8"),
    )
    assert default_telemetry_repository.get_latest("SWC-NODE-001") is not None


def test_27_mqtt_heartbeat_still_works(sample_heartbeat_payload):
    dispatcher = MessageDispatcher()
    dispatcher.dispatch(
        MQTTTopic(channel="heartbeat", device_code="SWC-NODE-001"),
        json.dumps(sample_heartbeat_payload).encode("utf-8"),
    )
    assert default_presence_repository.get("SWC-NODE-001").status == "ONLINE"


def test_28_mqtt_status_still_works():
    dispatcher = MessageDispatcher()
    dispatcher.dispatch(
        MQTTTopic(channel="status", device_code="SWC-NODE-001"),
        b'{"status": "offline"}',
    )
    assert default_presence_repository.get("SWC-NODE-001").status == "OFFLINE"


def test_29_mqtt_ack_still_works():
    c_svc = DeviceCommandService(
        repository=default_command_repository,
        publisher=StubPublisher(succeed=True),
    )
    cmd = c_svc.send_set_relay_command("SWC-NODE-001", "fan", 1)

    dispatcher = MessageDispatcher()
    dispatcher.dispatch(
        MQTTTopic(channel="ack", device_code="SWC-NODE-001"),
        json.dumps(
            {
                "commandId": cmd.command_id,
                "deviceId": "SWC-NODE-001",
                "status": "SUCCESS",
                "mode": "MANUAL",
            }
        ).encode("utf-8"),
    )
    assert default_command_repository.get(cmd.command_id).status == "SUCCESS"


def test_30_health_endpoint_remains_passing(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "service": "iot-service"}
