"""
IoT Service HTTP Adapter (CP8.1)

Implements the frozen CP8.0 service-to-service boundary contract:
    Management Service
        ↓ HTTP/service contract (GET /api/iot/devices/presence, GET /api/iot/devices/{device_id}/presence)
    IoT Service
        ↓
    IoT repositories

Management Service NEVER queries `iot_db`, IoT Redis keys, or legacy `swiftletcare.device_latest_state`.
"""

from datetime import datetime
import json
import logging
from typing import Any, Callable
import urllib.error
import urllib.parse
import urllib.request

from app.config import settings

logger = logging.getLogger(__name__)

HttpGetCallable = Callable[[str, float], tuple[int, Any]]


def _default_http_get(url: str, timeout: float) -> tuple[int, Any]:
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status_code = resp.getcode()
            raw = resp.read().decode("utf-8")
            body = json.loads(raw) if raw else None
            return status_code, body
    except urllib.error.HTTPError as exc:
        return exc.code, None


class IoTServiceAdapter:
    """HTTP client adapter for querying live device presence from IoT Service."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        http_get: HttpGetCallable | None = None,
    ):
        self._base_url = (base_url or settings.iot_service_base_url).rstrip("/")
        self._timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.iot_service_timeout_seconds
        )
        self._http_get: HttpGetCallable = http_get or _default_http_get

    @staticmethod
    def _parse_iso_datetime(value: str | None) -> datetime | None:
        if not value or not isinstance(value, str):
            return None
        try:
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None

    @classmethod
    def _normalize_presence_item(cls, item: dict[str, Any]) -> dict[str, Any]:
        raw_status = item.get("status")
        status = str(raw_status).upper() if raw_status else "UNKNOWN"
        if status not in ("ONLINE", "OFFLINE", "STALE", "UNKNOWN"):
            status = "UNKNOWN"
        last_seen_dt = cls._parse_iso_datetime(item.get("lastSeen"))
        return {
            "device_id": str(item.get("deviceId", "")),
            "status": status,
            "is_online": status == "ONLINE",
            "is_confirmed_offline": status == "OFFLINE",
            "is_stale": status == "STALE",
            "is_unknown": status == "UNKNOWN",
            "recorded_at": last_seen_dt,
            "last_seen": item.get("lastSeen"),
            "ip": item.get("ip"),
            "free_heap": item.get("freeHeap"),
            "uptime": item.get("uptime"),
            "device_state": {
                "ip": item.get("ip"),
                "freeHeap": item.get("freeHeap"),
                "uptime": item.get("uptime"),
                "mockMode": item.get("mockMode"),
            },
        }

    @staticmethod
    def _build_unknown_presence(device_id: str, reason: str) -> dict[str, Any]:
        return {
            "device_id": str(device_id),
            "status": "UNKNOWN",
            "is_online": False,
            "is_confirmed_offline": False,
            "is_stale": False,
            "is_unknown": True,
            "reason": reason,
            "recorded_at": None,
            "last_seen": None,
            "ip": None,
            "free_heap": None,
            "uptime": None,
            "device_state": {
                "ip": None,
                "freeHeap": None,
                "uptime": None,
                "mockMode": None,
            },
        }

    def resolve_device_presence(self, device_id: str) -> dict[str, Any]:
        """
        Queries IoT Service canonical endpoint:
            GET /api/iot/devices/{device_id}/presence
        Explicitly distinguishes confirmed OFFLINE (`status == "OFFLINE"`) from
        unavailable/unobserved runtime presence (`status == "UNKNOWN"`).
        """
        if not device_id or not self._base_url:
            return self._build_unknown_presence(device_id, "UNCONFIGURED")

        encoded_id = urllib.parse.quote(str(device_id), safe="")
        url = f"{self._base_url}/api/iot/devices/{encoded_id}/presence"
        try:
            status_code, body = self._http_get(url, self._timeout)
            if status_code == 200 and isinstance(body, dict):
                return self._normalize_presence_item(body)
            if status_code == 404:
                return self._build_unknown_presence(device_id, "PRESENCE_NOT_FOUND")
            return self._build_unknown_presence(device_id, f"HTTP_{status_code}")
        except Exception as exc:
            logger.warning(
                "Could not query IoT Service presence for device '%s' at %s: %s",
                device_id,
                url,
                exc,
            )
            return self._build_unknown_presence(device_id, "IOT_SERVICE_UNREACHABLE")

    def get_device_presence(self, device_id: str) -> dict[str, Any] | None:
        """
        Queries IoT Service canonical endpoint:
            GET /api/iot/devices/{device_id}/presence
        Returns normalized presence dict (`ONLINE`, `OFFLINE`, `STALE`, or `UNKNOWN`)
        when HTTP 200 is returned, or None if 404 / unreachable.
        """
        if not device_id or not self._base_url:
            return None

        encoded_id = urllib.parse.quote(str(device_id), safe="")
        url = f"{self._base_url}/api/iot/devices/{encoded_id}/presence"
        try:
            status_code, body = self._http_get(url, self._timeout)
            if status_code == 200 and isinstance(body, dict):
                return self._normalize_presence_item(body)
            return None
        except Exception as exc:
            logger.warning(
                "Could not query IoT Service presence for device '%s' at %s: %s",
                device_id,
                url,
                exc,
            )
            return None

    def list_devices_presence(self) -> dict[str, dict[str, Any]]:
        """
        Queries IoT Service canonical endpoint:
            GET /api/iot/devices/presence
        Returns dict mapping deviceId -> normalized presence dict.
        """
        if not self._base_url:
            return {}

        url = f"{self._base_url}/api/iot/devices/presence"
        try:
            status_code, body = self._http_get(url, self._timeout)
            if status_code != 200 or not isinstance(body, list):
                return {}
            results: dict[str, dict[str, Any]] = {}
            for item in body:
                if isinstance(item, dict) and item.get("deviceId"):
                    norm = self._normalize_presence_item(item)
                    results[norm["device_id"]] = norm
            return results
        except Exception as exc:
            logger.warning(
                "Could not list device presence from IoT Service at %s: %s",
                url,
                exc,
            )
            return {}

    def get_devices_runtime_state(
        self, device_identifiers: list[str]
    ) -> dict[str, dict[str, Any]]:
        """
        Retrieves normalized runtime presence for the requested device identifiers
        (matching either Management UUID or IoT node_id) via IoT Service HTTP API.
        Only ONLINE devices are included in the returned active runtime state map
        for backward compatibility with callers expecting active online entries,
        while preserving full status metadata.
        """
        if not device_identifiers:
            return {}

        all_presence = self.list_devices_presence()
        if not all_presence:
            return {}

        results: dict[str, dict[str, Any]] = {}
        for identifier in device_identifiers:
            key = str(identifier)
            info = all_presence.get(key)
            if info and info.get("is_online"):
                results[key] = info
        return results

    def get_devices_presence_breakdown(
        self, device_identifiers: list[str]
    ) -> dict[str, int]:
        """
        Returns explicit presence breakdown distinguishing confirmed OFFLINE from UNKNOWN/unavailable:
            {"online": int, "offline": int, "stale": int, "unknown": int}
        """
        counts = {"online": 0, "offline": 0, "stale": 0, "unknown": 0}
        if not device_identifiers:
            return counts

        all_presence = self.list_devices_presence()
        for identifier in device_identifiers:
            key = str(identifier)
            info = all_presence.get(key)
            if info is None:
                # Check individual endpoint in case device has history-backed UNKNOWN state
                single = self.get_device_presence(key)
                info = single
            if info is None:
                counts["unknown"] += 1
            elif info.get("status") == "ONLINE":
                counts["online"] += 1
            elif info.get("status") == "OFFLINE":
                counts["offline"] += 1
            elif info.get("status") == "STALE":
                counts["stale"] += 1
            else:
                counts["unknown"] += 1
        return counts

    def get_devices_presence_counts(
        self, device_identifiers: list[str]
    ) -> tuple[int, int]:
        """
        Given a list of device identifiers (node_ids or UUIDs), returns (online_count, offline_count)
        preserving legacy 2-tuple contract while `get_devices_presence_breakdown` provides the
        detailed (online, confirmed offline, stale, unknown) split.
        """
        if not device_identifiers:
            return 0, 0

        online_states = self.get_devices_runtime_state(device_identifiers)
        online_count = len(online_states)
        offline_count = max(0, len(device_identifiers) - online_count)
        return online_count, offline_count


iot_service_adapter = IoTServiceAdapter()
