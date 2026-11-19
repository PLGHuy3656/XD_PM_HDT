import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.mqtt.dispatcher import MessageDispatcher
from app.mqtt.topics import MQTTTopic
from app.repositories.presence_repository import InMemoryDevicePresenceRepository
from app.repositories.telemetry_repository import InMemoryTelemetryRepository
from app.schemas.presence import DevicePresence, HeartbeatPayload, StatusPayload
from app.services.heartbeat_service import HeartbeatService
from app.services.presence_service import DevicePresenceService
from app.services.status_service import StatusService
from app.services.telemetry_service import TelemetryService


@pytest.fixture
def presence_repo():
    return InMemoryDevicePresenceRepository()


@pytest.fixture
def presence_service(presence_repo):
    return DevicePresenceService(repository=presence_repo, stale_timeout_seconds=90)


@pytest.fixture
def heartbeat_service(presence_service):
    return HeartbeatService(presence_svc=presence_service)


@pytest.fixture
def status_service(presence_service):
    return StatusService(presence_svc=presence_service)


@pytest.fixture
def valid_heartbeat_dict():
    return {
        "deviceId": "SWC-NODE-001",
        "uptime": 123,
        "ip": "192.168.1.10",
        "freeHeap": 183420,
        "mockMode": False,
    }


# ==============================================================================
# HEARTBEAT TESTS (1 - 12)
# ==============================================================================

def test_1_valid_heartbeat_accepted(heartbeat_service, presence_repo, valid_heartbeat_dict):
    payload_bytes = json.dumps(valid_heartbeat_dict).encode("utf-8")
    result = heartbeat_service.process_message("SWC-NODE-001", payload_bytes)

    assert result.success is True
    assert result.presence is not None
    assert result.error is None
    assert result.presence.device_id == "SWC-NODE-001"
    assert result.presence.status == "ONLINE"
    assert result.presence.uptime == 123
    assert result.presence.ip == "192.168.1.10"
    assert result.presence.free_heap == 183420
    assert result.presence.mock_mode is False


def test_2_server_assigns_last_seen(heartbeat_service, valid_heartbeat_dict):
    before = datetime.now(timezone.utc)
    payload_bytes = json.dumps(valid_heartbeat_dict).encode("utf-8")
    result = heartbeat_service.process_message("SWC-NODE-001", payload_bytes)
    after = datetime.now(timezone.utc)

    assert result.success is True
    last_seen = result.presence.last_seen
    assert last_seen is not None
    assert last_seen.tzinfo == timezone.utc
    assert before <= last_seen <= after


def test_3_uptime_accepted_as_non_negative_duration(heartbeat_service, valid_heartbeat_dict):
    valid_heartbeat_dict["uptime"] = 0  # Just booted
    payload_bytes = json.dumps(valid_heartbeat_dict).encode("utf-8")
    result = heartbeat_service.process_message("SWC-NODE-001", payload_bytes)

    assert result.success is True
    assert result.presence.uptime == 0


def test_4_uptime_is_not_treated_as_unix_epoch(heartbeat_service, valid_heartbeat_dict):
    # Device uptime of 3600s (1 hour running) is stored as an integer duration,
    # while last_seen is the actual server UTC timestamp.
    valid_heartbeat_dict["uptime"] = 3600
    payload_bytes = json.dumps(valid_heartbeat_dict).encode("utf-8")
    result = heartbeat_service.process_message("SWC-NODE-001", payload_bytes)

    assert result.success is True
    assert result.presence.uptime == 3600
    assert result.presence.last_seen.year >= 2026


def test_5_topic_payload_identity_mismatch_rejected(heartbeat_service, presence_repo, valid_heartbeat_dict):
    payload_bytes = json.dumps(valid_heartbeat_dict).encode("utf-8")
    result = heartbeat_service.process_message("SWC-NODE-099", payload_bytes)

    assert result.success is False
    assert result.presence is None
    assert "Device identity mismatch" in result.error
    assert presence_repo.get("SWC-NODE-001") is None
    assert presence_repo.get("SWC-NODE-099") is None


def test_6_negative_uptime_rejected(heartbeat_service, valid_heartbeat_dict):
    valid_heartbeat_dict["uptime"] = -5
    payload_bytes = json.dumps(valid_heartbeat_dict).encode("utf-8")
    result = heartbeat_service.process_message("SWC-NODE-001", payload_bytes)

    assert result.success is False
    assert "Schema validation failed" in result.error


def test_7_negative_free_heap_rejected(heartbeat_service, valid_heartbeat_dict):
    valid_heartbeat_dict["freeHeap"] = -1024
    payload_bytes = json.dumps(valid_heartbeat_dict).encode("utf-8")
    result = heartbeat_service.process_message("SWC-NODE-001", payload_bytes)

    assert result.success is False
    assert "Schema validation failed" in result.error


def test_8_invalid_json_rejected(heartbeat_service):
    result = heartbeat_service.process_message("SWC-NODE-001", b"{invalid json")
    assert result.success is False
    assert "Invalid JSON" in result.error


def test_9_extra_fields_rejected_if_strict(heartbeat_service, valid_heartbeat_dict):
    valid_heartbeat_dict["type"] = "HEARTBEAT"  # Extra legacy field forbidden in strict V1
    payload_bytes = json.dumps(valid_heartbeat_dict).encode("utf-8")
    result = heartbeat_service.process_message("SWC-NODE-001", payload_bytes)

    assert result.success is False
    assert "extra_forbidden" in result.error or "extra" in result.error.lower()


def test_10_valid_heartbeat_marks_device_online(heartbeat_service, presence_repo, valid_heartbeat_dict):
    # Device initially unknown
    assert presence_repo.get("SWC-NODE-001") is None

    payload_bytes = json.dumps(valid_heartbeat_dict).encode("utf-8")
    result = heartbeat_service.process_message("SWC-NODE-001", payload_bytes)

    assert result.success is True
    assert result.presence.status == "ONLINE"
    assert presence_repo.get("SWC-NODE-001").status == "ONLINE"


def test_11_heartbeat_updates_last_heartbeat_at(heartbeat_service, valid_heartbeat_dict):
    payload_bytes = json.dumps(valid_heartbeat_dict).encode("utf-8")
    result = heartbeat_service.process_message("SWC-NODE-001", payload_bytes)

    assert result.success is True
    assert result.presence.last_heartbeat_at is not None
    assert result.presence.last_heartbeat_at == result.presence.last_seen


def test_12_repeated_heartbeat_updates_presence(heartbeat_service, valid_heartbeat_dict):
    payload_1 = json.dumps(valid_heartbeat_dict).encode("utf-8")
    res_1 = heartbeat_service.process_message("SWC-NODE-001", payload_1)
    t1 = res_1.presence.last_heartbeat_at

    # Second heartbeat with higher uptime
    valid_heartbeat_dict["uptime"] = 153
    valid_heartbeat_dict["freeHeap"] = 175000
    payload_2 = json.dumps(valid_heartbeat_dict).encode("utf-8")
    res_2 = heartbeat_service.process_message("SWC-NODE-001", payload_2)

    assert res_2.success is True
    assert res_2.presence.uptime == 153
    assert res_2.presence.free_heap == 175000
    assert res_2.presence.last_heartbeat_at >= t1


# ==============================================================================
# STATUS / LWT TESTS (13 - 19)
# ==============================================================================

def test_13_online_status_accepted(status_service):
    payload_bytes = b'{"status": "online"}'
    result = status_service.process_message("SWC-NODE-001", payload_bytes)

    assert result.success is True
    assert result.presence.status == "ONLINE"


def test_14_offline_status_accepted(status_service):
    payload_bytes = b'{"status": "offline"}'
    result = status_service.process_message("SWC-NODE-001", payload_bytes)

    assert result.success is True
    assert result.presence.status == "OFFLINE"


def test_15_invalid_status_rejected(status_service):
    payload_bytes = b'{"status": "sleeping"}'
    result = status_service.process_message("SWC-NODE-001", payload_bytes)

    assert result.success is False
    assert "Schema validation failed" in result.error


def test_16_online_marks_device_online(status_service, presence_repo):
    status_service.process_message("SWC-NODE-001", b'{"status": "online"}')
    stored = presence_repo.get("SWC-NODE-001")
    assert stored is not None
    assert stored.status == "ONLINE"


def test_17_offline_marks_device_offline(status_service, presence_repo):
    # Device initially online
    status_service.process_message("SWC-NODE-001", b'{"status": "online"}')
    assert presence_repo.get("SWC-NODE-001").status == "ONLINE"

    # LWT offline received
    status_service.process_message("SWC-NODE-001", b'{"status": "offline"}')
    assert presence_repo.get("SWC-NODE-001").status == "OFFLINE"


def test_18_last_status_at_updated(status_service):
    before = datetime.now(timezone.utc)
    res = status_service.process_message("SWC-NODE-001", b'{"status": "online"}')
    after = datetime.now(timezone.utc)

    assert res.success is True
    assert res.presence.last_status_at is not None
    assert before <= res.presence.last_status_at <= after


def test_19_retained_status_semantics_do_not_require_special_parsing(status_service):
    # Broker-retained messages deliver standard payload bytes without transport flags
    payload = b'{"status": "online"}'
    result = status_service.process_message("SWC-NODE-001", payload)
    assert result.success is True
    assert result.presence.status == "ONLINE"


# ==============================================================================
# STALE EVALUATION TESTS (20 - 24)
# ==============================================================================

def test_20_recent_heartbeat_remains_online(presence_service, heartbeat_service, valid_heartbeat_dict):
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc)
    presence_service.record_heartbeat(
        "SWC-NODE-001",
        HeartbeatPayload.model_validate(valid_heartbeat_dict),
        timestamp=now,
    )

    # 30 seconds later (well within 90s timeout)
    eval_time = now + timedelta(seconds=30)
    stale = presence_service.evaluate_stale_devices(now=eval_time, timeout_seconds=90)

    assert len(stale) == 0
    assert presence_service.get_presence("SWC-NODE-001").status == "ONLINE"


def test_21_missing_heartbeat_past_timeout_becomes_stale(presence_service, valid_heartbeat_dict):
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc)
    presence_service.record_heartbeat(
        "SWC-NODE-001",
        HeartbeatPayload.model_validate(valid_heartbeat_dict),
        timestamp=now,
    )

    # 91 seconds later (> 90s timeout)
    eval_time = now + timedelta(seconds=91)
    stale = presence_service.evaluate_stale_devices(now=eval_time, timeout_seconds=90)

    assert len(stale) == 1
    assert stale[0].device_id == "SWC-NODE-001"
    assert stale[0].status == "STALE"
    assert presence_service.get_presence("SWC-NODE-001").status == "STALE"


def test_22_explicit_offline_remains_offline(presence_service):
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc)
    presence_service.record_offline_status("SWC-NODE-001", timestamp=now)

    # 500 seconds later
    eval_time = now + timedelta(seconds=500)
    stale = presence_service.evaluate_stale_devices(now=eval_time, timeout_seconds=90)

    assert len(stale) == 0
    # Must remain OFFLINE, NOT become STALE!
    assert presence_service.get_presence("SWC-NODE-001").status == "OFFLINE"


def test_23_new_heartbeat_after_stale_restores_online(presence_service, heartbeat_service, valid_heartbeat_dict):
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc)
    presence_service.record_heartbeat(
        "SWC-NODE-001",
        HeartbeatPayload.model_validate(valid_heartbeat_dict),
        timestamp=now,
    )

    # Transition to STALE
    presence_service.evaluate_stale_devices(now=now + timedelta(seconds=120), timeout_seconds=90)
    assert presence_service.get_presence("SWC-NODE-001").status == "STALE"

    # New heartbeat arrives
    payload_bytes = json.dumps(valid_heartbeat_dict).encode("utf-8")
    res = heartbeat_service.process_message("SWC-NODE-001", payload_bytes)

    assert res.success is True
    assert res.presence.status == "ONLINE"
    assert presence_service.get_presence("SWC-NODE-001").status == "ONLINE"


def test_24_configurable_timeout_is_respected(presence_service, valid_heartbeat_dict):
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc)
    presence_service.record_heartbeat(
        "SWC-NODE-001",
        HeartbeatPayload.model_validate(valid_heartbeat_dict),
        timestamp=now,
    )

    # Check with custom timeout of 45 seconds at 50 seconds:
    eval_time = now + timedelta(seconds=50)
    # Default 90s would not trigger:
    assert len(presence_service.evaluate_stale_devices(now=eval_time, timeout_seconds=90)) == 0

    # Custom 45s triggers:
    stale = presence_service.evaluate_stale_devices(now=eval_time, timeout_seconds=45)
    assert len(stale) == 1
    assert stale[0].status == "STALE"


# ==============================================================================
# DISPATCHER TESTS (25 - 28)
# ==============================================================================

def test_25_heartbeat_routes_to_heartbeat_service(presence_repo, valid_heartbeat_dict):
    p_service = DevicePresenceService(repository=presence_repo)
    h_service = HeartbeatService(presence_svc=p_service)
    dispatcher = MessageDispatcher(heartbeat_svc=h_service)

    topic = MQTTTopic(channel="heartbeat", device_code="SWC-NODE-001")
    payload_bytes = json.dumps(valid_heartbeat_dict).encode("utf-8")

    dispatcher.dispatch(topic, payload_bytes)

    presence = presence_repo.get("SWC-NODE-001")
    assert presence is not None
    assert presence.status == "ONLINE"
    assert presence.uptime == 123


def test_26_status_routes_to_status_service(presence_repo):
    p_service = DevicePresenceService(repository=presence_repo)
    s_service = StatusService(presence_svc=p_service)
    dispatcher = MessageDispatcher(status_svc=s_service)

    topic = MQTTTopic(channel="status", device_code="SWC-NODE-001")
    dispatcher.dispatch(topic, b'{"status": "online"}')

    assert presence_repo.get("SWC-NODE-001").status == "ONLINE"

    # LWT offline
    dispatcher.dispatch(topic, b'{"status": "offline"}')
    assert presence_repo.get("SWC-NODE-001").status == "OFFLINE"


def test_27_telemetry_still_routes_correctly():
    telemetry_repo = InMemoryTelemetryRepository()
    t_service = TelemetryService(repository=telemetry_repo)
    dispatcher = MessageDispatcher(telemetry_svc=t_service)

    sample_telemetry = {
        "deviceId": "SWC-NODE-001",
        "metrics": {
            "temperature": 28.0,
            "humidity": 75.0,
            "lux": 10.0,
            "co2": 500.0,
            "audioRms": 0.2,
            "audioHealthy": True,
        },
        "actuators": {"misting": False, "fan": False, "heater": False, "alarm": False},
        "state": {"mode": "AUTO", "networkRssi": -55, "freeHeap": 150000},
    }

    topic = MQTTTopic(channel="telemetry", device_code="SWC-NODE-001")
    dispatcher.dispatch(topic, json.dumps(sample_telemetry).encode("utf-8"))

    latest = telemetry_repo.get_latest("SWC-NODE-001")
    assert latest is not None
    assert latest.metrics.temperature == 28.0


def test_28_ack_dispatches_cleanly():
    dispatcher = MessageDispatcher()
    topic = MQTTTopic(channel="ack", device_code="SWC-NODE-001")

    # ACK routes to AckService and rejects invalid input safely without crashing
    dispatcher.dispatch(topic, b'{"cmdId": "123", "status": "OK"}')
