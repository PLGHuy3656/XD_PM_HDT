"""Device Business Context / Metadata Resolver for IoT Telemetry & Domain Events.

Resolves deviceId (e.g. SWC-NODE-001) to canonical farmId and zoneId.
- When MANAGEMENT_SERVICE_URL and INTERNAL_SERVICE_KEY are configured (INT01+),
  queries authoritative Management Service GET /internal/v1/devices/{node_id}
  with a bounded TTL cache and strict fail-closed semantics (never fabricates farm IDs).
- When unconfigured (offline unit tests), uses the explicit static mapping only.
"""

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import NamedTuple

from app.config import settings

logger = logging.getLogger(__name__)


class DeviceLocation(NamedTuple):
    farm_id: str
    zone_id: str


class DeviceMetadataResolver:
    """Authoritative metadata resolver mapping device identity to business farm/zone context."""

    def __init__(
        self,
        static_mapping: dict[str, DeviceLocation] | None = None,
        management_service_url: str | None = None,
        internal_service_key: str | None = None,
    ):
        # Default canonical mappings for offline unit tests (only used when Management URL is unset)
        self._mapping: dict[str, DeviceLocation] = static_mapping or {
            "SWC-NODE-001": DeviceLocation(farm_id="FARM-01", zone_id="ZONE-01"),
            "ESP32-CTRL-01": DeviceLocation(farm_id="farm-binh-an", zone_id="zone-a"),
            "ESP32-CTRL-02": DeviceLocation(farm_id="farm-binh-an", zone_id="zone-b"),
            "ESP32-CTRL-04": DeviceLocation(farm_id="farm-phu-an", zone_id="zone-d"),
            "AUDIO-01": DeviceLocation(farm_id="farm-binh-an", zone_id="zone-c"),
            "swc-h01-f01-node01": DeviceLocation(farm_id="FARM-01", zone_id="ZONE-01"),
        }
        self._explicit_mgmt_url = management_service_url
        self._explicit_service_key = internal_service_key
        # Cache maps device_id -> (expires_at_monotonic, DeviceLocation | None)
        self._cache: dict[str, tuple[float, DeviceLocation | None]] = {}

    def register(self, device_id: str, farm_id: str, zone_id: str) -> None:
        loc = DeviceLocation(farm_id=farm_id, zone_id=zone_id)
        self._mapping[device_id] = loc
        self._cache[device_id] = (time.monotonic() + settings.metadata_cache_ttl_seconds, loc)

    def invalidate(self, device_id: str | None = None) -> None:
        if device_id is None:
            self._cache.clear()
        else:
            self._cache.pop(device_id, None)

    def _get_mgmt_config(self) -> tuple[str, str]:
        url = (
            self._explicit_mgmt_url
            if self._explicit_mgmt_url is not None
            else settings.management_service_url
        )
        key = (
            self._explicit_service_key
            if self._explicit_service_key is not None
            else settings.internal_service_key
        )
        return (url or "").strip().rstrip("/"), (key or "").strip()

    def _fetch_from_management(self, device_id: str, base_url: str, service_key: str) -> DeviceLocation | None:
        encoded = urllib.parse.quote(device_id, safe="")
        url = f"{base_url}/internal/v1/devices/{encoded}"
        req = urllib.request.Request(
            url,
            headers={
                "X-Internal-Service-Key": service_key,
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                if resp.status != 200:
                    return None
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                logger.info("[METADATA] Unregistered device '%s' (404 from Management)", device_id)
            else:
                logger.warning("[METADATA] Management lookup failed for '%s': HTTP %s (fail-closed)", device_id, exc.code)
            return None
        except Exception as exc:
            logger.warning("[METADATA] Management unreachable for '%s': %s (fail-closed)", device_id, type(exc).__name__)
            return None

        if not isinstance(data, dict):
            return None
        is_active = data.get("isActive", data.get("is_active", True))
        if not is_active:
            logger.info("[METADATA] Device '%s' is inactive in Management (fail-closed)", device_id)
            return None

        farm_id = data.get("farmId") or data.get("farm_id")
        if not isinstance(farm_id, str) or not farm_id.strip():
            return None
        zone_id = data.get("zoneId") or data.get("zone_id") or "UNASSIGNED"
        return DeviceLocation(farm_id=farm_id.strip(), zone_id=str(zone_id))

    def resolve(self, device_id: str) -> DeviceLocation | None:
        """Resolves deviceId to DeviceLocation(farm_id, zone_id).

        Returns None if device is unregistered, inactive, or Management is unavailable (fail-closed).
        """
        if not device_id or not device_id.strip():
            return None

        base_url, service_key = self._get_mgmt_config()
        if base_url:
            if not service_key:
                logger.warning("[METADATA] MANAGEMENT_SERVICE_URL set without INTERNAL_SERVICE_KEY (fail-closed)")
                return None

            now = time.monotonic()
            cached = self._cache.get(device_id)
            if cached is not None and cached[0] > now:
                return cached[1]

            loc = self._fetch_from_management(device_id, base_url, service_key)
            ttl = (
                settings.metadata_cache_ttl_seconds
                if loc is not None
                else settings.metadata_negative_cache_ttl_seconds
            )
            self._cache[device_id] = (now + ttl, loc)
            return loc

        # Offline / unit-test fallback: static mapping only
        return self._mapping.get(device_id)


default_metadata_resolver = DeviceMetadataResolver()
