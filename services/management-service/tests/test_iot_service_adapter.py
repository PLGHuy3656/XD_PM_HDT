from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

from app.adapters.iot_service_adapter import IoTServiceAdapter
from app.adapters.legacy_iot_adapter import LegacyIoTAdapter
from app.repositories.device_repository import DeviceRepository
from app.repositories.technician_repository import TechnicianRepository


def test_iot_service_adapter_queries_canonical_presence_endpoints():
    called_urls: list[str] = []

    def fake_http_get(url: str, timeout: float) -> tuple[int, Any]:
        called_urls.append(url)
        if url.endswith("/api/iot/devices/presence"):
            return 200, [
                {
                    "deviceId": "SWC-NODE-001",
                    "status": "ONLINE",
                    "lastSeen": "2026-11-03T10:00:00Z",
                    "uptime": 420,
                    "ip": "192.168.1.21",
                    "freeHeap": 182000,
                    "mockMode": False,
                },
                {
                    "deviceId": "SWC-NODE-002",
                    "status": "OFFLINE",
                    "lastSeen": "2026-11-03T09:50:00Z",
                    "uptime": None,
                    "ip": None,
                    "freeHeap": None,
                    "mockMode": None,
                },
            ]
        if url.endswith("/api/iot/devices/SWC-NODE-001/presence"):
            return 200, {
                "deviceId": "SWC-NODE-001",
                "status": "ONLINE",
                "lastSeen": "2026-11-03T10:00:00Z",
                "uptime": 420,
                "ip": "192.168.1.21",
                "freeHeap": 182000,
                "mockMode": False,
            }
        return 404, None

    adapter = IoTServiceAdapter(
        base_url="http://127.0.0.1:8002",
        timeout_seconds=2.0,
        http_get=fake_http_get,
    )

    single = adapter.get_device_presence("SWC-NODE-001")
    assert single is not None
    assert single["status"] == "ONLINE"
    assert single["is_online"] is True

    missing = adapter.get_device_presence("UNKNOWN-NODE")
    assert missing is None

    active_states = adapter.get_devices_runtime_state(["SWC-NODE-001", "SWC-NODE-002"])
    assert "SWC-NODE-001" in active_states
    assert "SWC-NODE-002" not in active_states

    online_count, offline_count = adapter.get_devices_presence_counts(
        ["SWC-NODE-001", "SWC-NODE-002"]
    )
    assert online_count == 1
    assert offline_count == 1
    assert "http://127.0.0.1:8002/api/iot/devices/SWC-NODE-001/presence" in called_urls
    assert "http://127.0.0.1:8002/api/iot/devices/presence" in called_urls


def test_iot_service_adapter_gracefully_handles_unreachable_iot_service():
    def failing_http_get(url: str, timeout: float) -> tuple[int, Any]:
        raise ConnectionError("IoT Service unreachable")

    adapter = IoTServiceAdapter(
        base_url="http://127.0.0.1:8002",
        http_get=failing_http_get,
    )

    assert adapter.get_device_presence("SWC-NODE-001") is None
    assert adapter.get_devices_runtime_state(["SWC-NODE-001"]) == {}
    assert adapter.get_devices_presence_counts(["SWC-NODE-001", "SWC-NODE-002"]) == (0, 2)


def test_device_and_technician_repositories_use_http_adapter_not_legacy_sql():
    def fake_http_get(url: str, timeout: float) -> tuple[int, Any]:
        if url.endswith("/api/iot/devices/presence"):
            return 200, [
                {
                    "deviceId": "ESP32-NODE-01",
                    "status": "ONLINE",
                    "lastSeen": "2026-11-03T10:15:00Z",
                    "uptime": 600,
                    "ip": "192.168.1.101",
                    "freeHeap": 175000,
                    "mockMode": False,
                }
            ]
        if url.endswith("/api/iot/devices/ESP32-NODE-01/presence"):
            return 200, {
                "deviceId": "ESP32-NODE-01",
                "status": "ONLINE",
                "lastSeen": "2026-11-03T10:15:00Z",
                "uptime": 600,
                "ip": "192.168.1.101",
                "freeHeap": 175000,
                "mockMode": False,
            }
        return 404, None

    adapter = IoTServiceAdapter(base_url="http://127.0.0.1:8002", http_get=fake_http_get)
    dev_repo = DeviceRepository(iot_adapter=adapter)
    tech_repo = TechnicianRepository(iot_adapter=adapter)

    fake_created_at = datetime(2026, 11, 1, 8, 0, 0, tzinfo=timezone.utc)
    fake_device_rows = [
        (
            "uuid-dev-1",
            "ESP32-NODE-01",
            "Controller 1",
            "CONTROLLER",
            "uuid-farm-1",
            "uuid-zone-1",
            "Zone A",
            "192.168.1.101",
            "v1.0.0",
            True,
            fake_created_at,
        ),
        (
            "uuid-dev-2",
            "ESP32-NODE-02",
            "Controller 2",
            "CONTROLLER",
            "uuid-farm-1",
            "uuid-zone-1",
            "Zone A",
            "192.168.1.102",
            "v1.0.0",
            True,
            fake_created_at,
        ),
    ]

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    with patch("app.repositories.device_repository.get_connection", return_value=mock_conn):
        mock_cur.fetchall.return_value = fake_device_rows
        devices = dev_repo.list_devices()
        assert len(devices) == 2
        assert devices[0]["node_id"] == "ESP32-NODE-01"
        assert devices[0]["status"] == "ONLINE"
        assert devices[1]["node_id"] == "ESP32-NODE-02"
        assert devices[1]["status"] == "OFFLINE"

        mock_cur.fetchone.return_value = fake_device_rows[0]
        single_dev = dev_repo.get_device_by_id("uuid-dev-1")
        assert single_dev is not None
        assert single_dev["status"] == "ONLINE"

    with patch("app.repositories.technician_repository.get_connection", return_value=mock_conn):
        mock_cur.fetchone.return_value = (
            1,
            2,
            2,
            ["uuid-dev-1", "uuid-dev-2"],
            ["ESP32-NODE-01", "ESP32-NODE-02"],
        )
        summary = tech_repo.get_dashboard_summary("tech-001")
        assert summary["device_count"] == 2
        assert summary["online_device_count"] == 1
        assert summary["offline_device_count"] == 1


def test_legacy_iot_adapter_shim_has_no_sql_and_delegates_to_http_adapter():
    adapter = IoTServiceAdapter(
        base_url="http://127.0.0.1:8002",
        http_get=lambda url, timeout: (
            200,
            [{"deviceId": "SWC-NODE-001", "status": "ONLINE", "lastSeen": "2026-11-03T10:00:00Z"}],
        ),
    )
    shim = LegacyIoTAdapter(adapter=adapter)
    assert shim.get_devices_presence_counts(["SWC-NODE-001", "SWC-NODE-002"]) == (1, 1)


def test_iot_service_adapter_distinguishes_confirmed_offline_from_unknown_unavailable_presence():
    def fake_http_get(url: str, timeout: float) -> tuple[int, Any]:
        if url.endswith("/api/iot/devices/presence"):
            return 200, [
                {
                    "deviceId": "SWC-NODE-ONLINE",
                    "status": "ONLINE",
                    "lastSeen": "2026-11-04T12:00:00Z",
                    "uptime": 300,
                    "ip": "192.168.1.10",
                    "freeHeap": 180000,
                    "mockMode": False,
                },
                {
                    "deviceId": "SWC-NODE-CONFIRMED-OFF",
                    "status": "OFFLINE",
                    "lastSeen": "2026-11-04T11:55:00Z",
                    "uptime": None,
                    "ip": None,
                    "freeHeap": None,
                    "mockMode": None,
                },
                {
                    "deviceId": "SWC-NODE-STALE",
                    "status": "STALE",
                    "lastSeen": "2026-11-04T11:50:00Z",
                    "uptime": 240,
                    "ip": "192.168.1.12",
                    "freeHeap": 179000,
                    "mockMode": False,
                },
            ]
        if url.endswith("/api/iot/devices/SWC-NODE-CONFIRMED-OFF/presence"):
            return 200, {
                "deviceId": "SWC-NODE-CONFIRMED-OFF",
                "status": "OFFLINE",
                "lastSeen": "2026-11-04T11:55:00Z",
            }
        if url.endswith("/api/iot/devices/SWC-NODE-FLUSHED/presence"):
            return 200, {
                "deviceId": "SWC-NODE-FLUSHED",
                "status": "UNKNOWN",
                "lastSeen": "2026-11-04T11:58:00Z",
            }
        return 404, None

    adapter = IoTServiceAdapter(base_url="http://127.0.0.1:8002", http_get=fake_http_get)

    confirmed_off = adapter.resolve_device_presence("SWC-NODE-CONFIRMED-OFF")
    assert confirmed_off["status"] == "OFFLINE"
    assert confirmed_off["is_confirmed_offline"] is True
    assert confirmed_off["is_unknown"] is False

    flushed_unknown = adapter.resolve_device_presence("SWC-NODE-FLUSHED")
    assert flushed_unknown["status"] == "UNKNOWN"
    assert flushed_unknown["is_confirmed_offline"] is False
    assert flushed_unknown["is_unknown"] is True

    never_seen = adapter.resolve_device_presence("SWC-NODE-NEVER-SEEN")
    assert never_seen["status"] == "UNKNOWN"
    assert never_seen["is_confirmed_offline"] is False
    assert never_seen["is_unknown"] is True
    assert never_seen["reason"] == "PRESENCE_NOT_FOUND"

    breakdown = adapter.get_devices_presence_breakdown(
        [
            "SWC-NODE-ONLINE",
            "SWC-NODE-CONFIRMED-OFF",
            "SWC-NODE-STALE",
            "SWC-NODE-FLUSHED",
            "SWC-NODE-NEVER-SEEN",
        ]
    )
    assert breakdown == {
        "online": 1,
        "offline": 1,
        "stale": 1,
        "unknown": 2,
    }


def test_technician_dashboard_when_iot_service_down_counts_unknown_not_offline():
    def failing_http_get(url: str, timeout: float) -> tuple[int, Any]:
        raise ConnectionError("IoT Service unreachable")

    adapter = IoTServiceAdapter(base_url="http://127.0.0.1:8002", http_get=failing_http_get)
    tech_repo = TechnicianRepository(iot_adapter=adapter)

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    with patch("app.repositories.technician_repository.get_connection", return_value=mock_conn):
        mock_cur.fetchone.return_value = (
            2,
            4,
            3,
            ["uuid-dev-1", "uuid-dev-2", "uuid-dev-3"],
            ["ESP32-NODE-01", "ESP32-NODE-02", "ESP32-NODE-03"],
        )
        summary = tech_repo.get_dashboard_summary("tech-001")
        assert summary["device_count"] == 3
        assert summary["online_device_count"] == 0
        assert summary["offline_device_count"] == 0
        assert summary["unknown_device_count"] == 3


def test_technician_devices_when_iot_service_down_returns_unknown():
    def failing_http_get(url: str, timeout: float) -> tuple[int, Any]:
        raise ConnectionError("IoT Service unreachable")

    adapter = IoTServiceAdapter(base_url="http://127.0.0.1:8002", http_get=failing_http_get)
    tech_repo = TechnicianRepository(iot_adapter=adapter)

    fake_device_rows = [
        (
            "uuid-dev-1",
            "ESP32-NODE-01",
            "Controller 1",
            "CONTROLLER",
            "uuid-farm-1",
            "uuid-zone-1",
            "Zone A",
            "192.168.1.101",
            "v1.0.0",
        ),
        (
            "uuid-dev-2",
            "ESP32-NODE-02",
            "Sensor 2",
            "SENSOR",
            "uuid-farm-1",
            "uuid-zone-1",
            "Zone A",
            "192.168.1.102",
            "v1.0.0",
        ),
    ]

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    with patch("app.repositories.technician_repository.get_connection", return_value=mock_conn):
        mock_cur.fetchall.return_value = fake_device_rows
        devices = tech_repo.get_assigned_farm_devices("tech-001", "uuid-farm-1")
        assert len(devices) == 2
        for dev in devices:
            assert dev["status"] == "UNKNOWN"
            assert dev["mqtt_status"] == "Unknown"
            assert dev["rssi"] is None
            assert dev["last_seen"] is None

        detail = tech_repo.get_assigned_farm_device_detail("tech-001", "uuid-farm-1", "uuid-dev-1")
        assert detail is not None
        assert detail["status"] == "UNKNOWN"
        assert detail["mqtt_status"] == "Unknown"


def test_technician_dashboard_and_devices_when_iot_service_up_mixed():
    def fake_http_get(url: str, timeout: float) -> tuple[int, Any]:
        if url.endswith("/api/iot/devices/presence"):
            return 200, [
                {
                    "deviceId": "ESP32-NODE-01",
                    "status": "ONLINE",
                    "rssi": -65,
                    "lastSeen": "2026-11-04T12:00:00Z",
                },
                {
                    "deviceId": "ESP32-NODE-02",
                    "status": "OFFLINE",
                    "rssi": None,
                    "lastSeen": "2026-11-04T11:00:00Z",
                },
                {
                    "deviceId": "ESP32-NODE-03",
                    "status": "STALE",
                    "rssi": -80,
                    "lastSeen": "2026-11-04T10:00:00Z",
                },
            ]
        return 404, None

    adapter = IoTServiceAdapter(base_url="http://127.0.0.1:8002", http_get=fake_http_get)
    tech_repo = TechnicianRepository(iot_adapter=adapter)

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    with patch("app.repositories.technician_repository.get_connection", return_value=mock_conn):
        mock_cur.fetchone.return_value = (
            2,
            4,
            4,
            ["uuid-dev-1", "uuid-dev-2", "uuid-dev-3", "uuid-dev-4"],
            ["ESP32-NODE-01", "ESP32-NODE-02", "ESP32-NODE-03", "ESP32-NODE-04"],
        )
        summary = tech_repo.get_dashboard_summary("tech-001")
        assert summary["device_count"] == 4
        assert summary["online_device_count"] == 1
        assert summary["offline_device_count"] == 3
        assert summary["unknown_device_count"] == 0


