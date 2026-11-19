import io
import json
import urllib.error
from datetime import datetime, timezone
from unittest.mock import patch

from app.domain_events.metadata_resolver import DeviceLocation, DeviceMetadataResolver
from app.repositories.telemetry_repository import InMemoryTelemetryRepository
from app.services.telemetry_service import TelemetryService


class _FakeHttpResponse:
    def __init__(self, status: int, body: dict):
        self.status = status
        self._body = json.dumps(body).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_metadata_resolver_queries_management_with_psk_and_caches():
    resolver = DeviceMetadataResolver(
        management_service_url="http://management-service:8001",
        internal_service_key="A" * 40,
    )
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value = _FakeHttpResponse(
            200,
            {
                "deviceId": "11111111-1111-1111-1111-111111111111",
                "nodeId": "SWC-INT01-NODE-01",
                "farmId": "22222222-2222-2222-2222-222222222222",
                "status": "ACTIVE",
                "isActive": True,
            },
        )
        loc1 = resolver.resolve("SWC-INT01-NODE-01")
        loc2 = resolver.resolve("SWC-INT01-NODE-01")

    assert loc1 == DeviceLocation(farm_id="22222222-2222-2222-2222-222222222222", zone_id="UNASSIGNED")
    assert loc2 == loc1
    assert mock_open.call_count == 1
    req = mock_open.call_args.args[0]
    assert req.full_url == "http://management-service:8001/internal/v1/devices/SWC-INT01-NODE-01"
    assert req.get_header("X-internal-service-key") == "A" * 40


def test_metadata_resolver_fails_closed_on_404_inactive_or_management_down():
    resolver = DeviceMetadataResolver(
        management_service_url="http://management-service:8001",
        internal_service_key="B" * 40,
    )
    # 1. 404 unregistered device -> None
    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.HTTPError("http://x", 404, "Not Found", {}, io.BytesIO(b"")),
    ):
        assert resolver.resolve("UNKNOWN-NODE") is None

    # 2. Inactive device -> None
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value = _FakeHttpResponse(
            200,
            {"deviceId": "id", "nodeId": "INACTIVE-NODE", "farmId": "farm-1", "status": "DISABLED", "isActive": False},
        )
        assert resolver.resolve("INACTIVE-NODE") is None

    # 3. Management unreachable -> fail-closed None
    with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
        assert resolver.resolve("DOWN-NODE") is None


def test_telemetry_service_populates_authoritative_farm_id_and_blocks_rogue_device():
    repo = InMemoryTelemetryRepository()
    resolver = DeviceMetadataResolver(
        management_service_url="http://management-service:8001",
        internal_service_key="C" * 40,
    )
    svc = TelemetryService(repository=repo, metadata_resolver=resolver)

    payload_good = json.dumps({
        "deviceId": "SWC-REG-01",
        "metrics": {"temperature": 28.5, "humidity": 80.0, "lux": 0.4, "co2": 450.0, "audioRms": 0.3, "audioHealthy": True},
        "actuators": {"misting": False, "fan": False, "heater": False, "alarm": False},
        "state": {"mode": "AUTO", "networkRssi": -60, "freeHeap": 200000},
    })
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value = _FakeHttpResponse(
            200,
            {"deviceId": "d1", "nodeId": "SWC-REG-01", "farmId": "farm-alpha", "status": "ACTIVE", "isActive": True},
        )
        res = svc.process_message("SWC-REG-01", payload_good)
    assert res.success is True
    assert repo.get_latest_by_farm("farm-alpha").device_id == "SWC-REG-01"

    # Unregistered device must stay unmapped (never leak into farm-alpha)
    payload_rogue = payload_good.replace("SWC-REG-01", "ROGUE-99")
    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.HTTPError("http://x", 404, "Not Found", {}, io.BytesIO(b"")),
    ):
        res2 = svc.process_message("ROGUE-99", payload_rogue)
    assert res2.success is True
    assert repo.get_latest("ROGUE-99").farm_id is None
    assert len(repo.list_by_farm("farm-alpha")) == 1
