"""INT01-R1: Management device presence semantics and IoT service-to-service authentication."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from app.adapters import iot_service_adapter as adapter_mod
from app.adapters.iot_service_adapter import IoTServiceAdapter
from app.repositories.device_repository import DeviceRepository


def test_never_seen_device_is_unknown_not_offline():
    assert IoTServiceAdapter.resolve_status(None, iot_reachable=True)[0] == "UNKNOWN"


def test_confirmed_offline_and_stale_stay_offline():
    assert IoTServiceAdapter.resolve_status({"status": "OFFLINE"}, True)[0] == "OFFLINE"
    assert IoTServiceAdapter.resolve_status({"status": "STALE"}, True)[0] == "OFFLINE"
    assert IoTServiceAdapter.resolve_status({"status": "ONLINE"}, True)[0] == "ONLINE"


def test_unreachable_iot_is_unknown_with_presence_source_unavailable():
    assert IoTServiceAdapter.resolve_status(None, iot_reachable=False)[0] == "UNKNOWN"
    assert IoTServiceAdapter.is_presence_source_available({"reason": "IOT_SERVICE_UNREACHABLE"}) is False
    assert IoTServiceAdapter.is_presence_source_available({"reason": "HTTP_401"}) is False
    assert IoTServiceAdapter.is_presence_source_available({"reason": "UNCONFIGURED"}) is False
    assert IoTServiceAdapter.is_presence_source_available({"reason": "PRESENCE_NOT_FOUND"}) is True
    assert IoTServiceAdapter.is_presence_source_available({"status": "ONLINE"}) is True


def _row():
    from datetime import datetime, timezone

    return ("uuid-dev-9", "SWC-INT01-UNSEEN-99", "Unseen", "CONTROLLER", "uuid-farm-1",
            None, None, None, "v1", True, datetime(2026, 11, 1, tzinfo=timezone.utc))


def _repo_with(http_get):
    return DeviceRepository(iot_adapter=IoTServiceAdapter(base_url="http://iot-service:8002", http_get=http_get))


def _run(repo, fetch_one=False):
    mock_conn, mock_cur = MagicMock(), MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchall.return_value = [_row()]
    mock_cur.fetchone.return_value = _row()
    with patch("app.repositories.device_repository.get_connection", return_value=mock_conn):
        return repo.get_device_by_id("uuid-dev-9") if fetch_one else repo.list_devices()


def test_list_and_detail_agree_for_never_seen_device():
    def http_get(url: str, timeout: float) -> tuple[int, Any]:
        return (200, []) if url.endswith("/presence") and "/devices/presence" in url else (404, None)

    repo = _repo_with(http_get)
    listed = _run(repo)[0]
    detail = _run(repo, fetch_one=True)
    assert listed["status"] == detail["status"] == "UNKNOWN"
    assert listed["iot_available"] is True and detail["iot_available"] is True
    assert listed["health_metadata"]["lastSeen"] is None


def test_unreachable_iot_marks_iot_available_false():
    def http_get(url: str, timeout: float):
        raise OSError("connection refused")

    repo = _repo_with(http_get)
    listed = _run(repo)[0]
    detail = _run(repo, fetch_one=True)
    assert listed["status"] == "UNKNOWN" and listed["iot_available"] is False
    assert detail["status"] == "UNKNOWN" and detail["iot_available"] is False


def test_auth_rejected_by_iot_marks_iot_available_false():
    repo = _repo_with(lambda url, timeout: (401, None))
    assert _run(repo, fetch_one=True)["iot_available"] is False


def test_default_http_get_sends_internal_service_key(monkeypatch):
    captured = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def getcode(self):
            return 200

        def read(self):
            return b"[]"

    def fake_urlopen(req, timeout):
        captured["headers"] = dict(req.header_items())
        return _Resp()

    monkeypatch.setattr(adapter_mod.settings, "internal_service_token", "k" * 40)
    monkeypatch.setattr(adapter_mod.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(adapter_mod, "_ensure_resolvable", lambda url, timeout: None)
    status, body = adapter_mod._default_http_get("http://iot-service:8002/api/iot/devices/presence", 1.0)
    assert status == 200 and body == []
    assert captured["headers"].get("X-internal-service-key") == "k" * 40


def test_slow_dns_for_stopped_iot_is_bounded(monkeypatch):
    """INT01-R1: a stopped IoT container must not block Management past its IoT timeout."""
    import time as _time

    adapter_mod._DNS_NEGATIVE_CACHE.clear()

    def slow_getaddrinfo(*args, **kwargs):
        _time.sleep(3)
        raise OSError("Temporary failure in name resolution")

    monkeypatch.setattr(adapter_mod.socket, "getaddrinfo", slow_getaddrinfo)
    adapter = IoTServiceAdapter(base_url="http://iot-service-r1-test:8002", timeout_seconds=0.5)
    started = _time.monotonic()
    assert adapter.list_devices_presence() is None
    first = _time.monotonic() - started
    started = _time.monotonic()
    assert adapter.resolve_device_presence("SWC-INT01-NODE-01")["reason"] == "IOT_SERVICE_UNREACHABLE"
    second = _time.monotonic() - started
    assert first < 1.5
    assert second < 0.2  # negative cache: no second wait within the same request burst
    adapter_mod._DNS_NEGATIVE_CACHE.clear()
