from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.telemetry_repository import default_telemetry_repository
from app.schemas.telemetry import (
    AcceptedTelemetry,
    ActuatorState,
    DeviceRuntimeState,
    TelemetryMetrics,
)


@pytest.fixture(autouse=True)
def clean_repository():
    default_telemetry_repository.clear()
    yield
    default_telemetry_repository.clear()


@pytest.fixture
def client():
    return TestClient(app)


def _make_sample_telemetry(device_id: str, farm_id: str | None = None, temp: float = 28.5):
    return AcceptedTelemetry(
        device_id=device_id,
        received_at=datetime.now(timezone.utc),
        metrics=TelemetryMetrics(
            temperature=temp,
            humidity=75.0,
            lux=150.0,
            co2=450.0,
            audioRms=12.5,
            audioHealthy=True,
        ),
        actuators=ActuatorState(
            misting=False,
            fan=True,
            heater=False,
            alarm=False,
        ),
        state=DeviceRuntimeState(
            mode="AUTO",
            networkRssi=-65,
            freeHeap=128000,
        ),
        farm_id=farm_id,
    )


def test_get_farm_telemetry_latest_not_found(client):
    resp = client.get("/api/iot/farms/farm-empty/telemetry/latest")
    assert resp.status_code == 404
    assert "No telemetry found for farm 'farm-empty'" in resp.json()["detail"]


def test_list_farm_telemetry_empty(client):
    resp = client.get("/api/iot/farms/farm-empty/telemetry")
    assert resp.status_code == 200
    assert resp.json() == []


def test_farm_telemetry_explicit_farm_id(client):
    t1 = _make_sample_telemetry("SWC-NODE-001", farm_id="farm-binh-an", temp=27.5)
    default_telemetry_repository.save(t1)

    # Query latest
    resp = client.get("/api/iot/farms/farm-binh-an/telemetry/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["deviceId"] == "SWC-NODE-001"
    assert data["farmId"] == "farm-binh-an"
    assert data["metrics"]["temperature"] == 27.5

    # Query history
    resp_list = client.get("/api/iot/farms/farm-binh-an/telemetry?limit=10")
    assert resp_list.status_code == 200
    items = resp_list.json()
    assert len(items) == 1
    assert items[0]["deviceId"] == "SWC-NODE-001"


def test_farm_telemetry_registered_device(client):
    default_telemetry_repository.register_device_farm("SWC-NODE-002", "farm-phu-an")
    t = _make_sample_telemetry("SWC-NODE-002", farm_id=None, temp=29.0)
    default_telemetry_repository.save(t)

    resp = client.get("/api/iot/farms/farm-phu-an/telemetry/latest")
    assert resp.status_code == 200
    assert resp.json()["deviceId"] == "SWC-NODE-002"
    assert resp.json()["farmId"] == "farm-phu-an"


def test_cross_farm_isolation(client):
    t_a = _make_sample_telemetry("DEV-A", farm_id="farm-A", temp=26.0)
    t_b = _make_sample_telemetry("DEV-B", farm_id="farm-B", temp=31.0)
    default_telemetry_repository.save(t_a)
    default_telemetry_repository.save(t_b)

    # Farm A query must not see Farm B
    resp_a = client.get("/api/iot/farms/farm-A/telemetry")
    assert resp_a.status_code == 200
    items_a = resp_a.json()
    assert len(items_a) == 1
    assert items_a[0]["deviceId"] == "DEV-A"
    assert items_a[0]["metrics"]["temperature"] == 26.0

    # Farm B query must not see Farm A
    resp_b = client.get("/api/iot/farms/farm-B/telemetry")
    assert resp_b.status_code == 200
    items_b = resp_b.json()
    assert len(items_b) == 1
    assert items_b[0]["deviceId"] == "DEV-B"


def test_list_farm_telemetry_limit_validation(client):
    # Test invalid limits
    resp_zero = client.get("/api/iot/farms/farm-1/telemetry?limit=0")
    assert resp_zero.status_code == 422

    resp_excess = client.get("/api/iot/farms/farm-1/telemetry?limit=501")
    assert resp_excess.status_code == 422
