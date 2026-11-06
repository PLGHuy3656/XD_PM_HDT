import json
import time
from unittest.mock import MagicMock

import pytest

from app.schemas.telemetry import TelemetryPayload
from app.services.telemetry_service import TelemetryService


class FakeTelemetryRepository:
    def __init__(self):
        self.saved_records = []

    def save_telemetry(self, house_code, payload, recorded_at):
        self.saved_records.append({
            "house_code": house_code,
            "payload": payload,
            "recorded_at": recorded_at,
        })


class FakeRealtimeManager:
    def __init__(self):
        self.broadcasts = []

    async def broadcast(self, data):
        self.broadcasts.append(data)


@pytest.fixture
def repo():
    return FakeTelemetryRepository()


@pytest.fixture
def realtime():
    return FakeRealtimeManager()


@pytest.fixture
def telemetry_service(repo, realtime):
    return TelemetryService(repository=repo, realtime=realtime)


@pytest.fixture
def valid_payload_dict():
    return {
        "nodeId": "device01",
        "timestamp": int(time.time()),
        "metrics": {
            "temperature": 28.5,
            "humidity": 75.0,
            "lux": 150.0,
            "co2": 420.0,
            "audioRms": 0.05,
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
            "networkRssi": -65,
            "freeHeap": 120000,
        },
    }


def test_process_valid_telemetry(telemetry_service, repo, valid_payload_dict):
    topic = "swiftlet/telemetry/house01/device01"
    payload_json = json.dumps(valid_payload_dict)

    success = telemetry_service.process_message(
        topic=topic,
        payload_bytes=payload_json,
        event_loop=None,
    )

    assert success is True
    assert len(repo.saved_records) == 1
    assert repo.saved_records[0]["house_code"] == "house01"
    assert repo.saved_records[0]["payload"].nodeId == "device01"


def test_reject_topic_node_id_mismatch(telemetry_service, repo, valid_payload_dict):
    topic = "swiftlet/telemetry/house01/different_node"
    payload_json = json.dumps(valid_payload_dict)

    success = telemetry_service.process_message(
        topic=topic,
        payload_bytes=payload_json,
        event_loop=None,
    )

    assert success is False
    assert len(repo.saved_records) == 0


def test_reject_invalid_topic_format(telemetry_service, repo, valid_payload_dict):
    topic = "invalid/topic/format"
    payload_json = json.dumps(valid_payload_dict)

    success = telemetry_service.process_message(
        topic=topic,
        payload_bytes=payload_json,
        event_loop=None,
    )

    assert success is False
    assert len(repo.saved_records) == 0


def test_reject_future_timestamp(telemetry_service, repo, valid_payload_dict):
    # Timestamp > 300 seconds in the future
    valid_payload_dict["timestamp"] = int(time.time()) + 1000
    topic = "swiftlet/telemetry/house01/device01"
    payload_json = json.dumps(valid_payload_dict)

    success = telemetry_service.process_message(
        topic=topic,
        payload_bytes=payload_json,
        event_loop=None,
    )

    assert success is False
    assert len(repo.saved_records) == 0


def test_reject_malformed_json(telemetry_service, repo):
    topic = "swiftlet/telemetry/house01/device01"
    payload_bytes = b"not-a-valid-json"

    success = telemetry_service.process_message(
        topic=topic,
        payload_bytes=payload_bytes,
        event_loop=None,
    )

    assert success is False
    assert len(repo.saved_records) == 0
