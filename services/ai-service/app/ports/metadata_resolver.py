"""Metadata resolver port and adapters for enriching camera events/status with farmId and zoneId."""
from __future__ import annotations

import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple
from urllib.parse import quote

import httpx

logger = logging.getLogger("ai_service.ports.metadata_resolver")


class CameraMetadataResolver(ABC):
    """Port for resolving farmId and zoneId from cameraId."""

    @abstractmethod
    def resolve(self, camera_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Returns (farm_id, zone_id) for the given camera_id, or (None, None) if unresolved."""
        raise NotImplementedError

    def resolve_farm_id(self, camera_id: str, default: Optional[str] = None) -> Optional[str]:
        farm_id, _ = self.resolve(camera_id)
        return farm_id or default

    def resolve_zone_id(self, camera_id: str, default: Optional[str] = None) -> Optional[str]:
        _, zone_id = self.resolve(camera_id)
        return zone_id or default


class InMemoryCameraMetadataResolver(CameraMetadataResolver):
    """In-memory resolver with explicit mappings and optional fallback defaults (for tests/runtime)."""

    def __init__(
        self,
        mappings: Optional[Dict[str, Tuple[Optional[str], Optional[str]]]] = None,
        default_farm_id: Optional[str] = None,
        default_zone_id: Optional[str] = None,
    ) -> None:
        self._mappings: Dict[str, Tuple[Optional[str], Optional[str]]] = dict(mappings or {})
        self.default_farm_id = default_farm_id
        self.default_zone_id = default_zone_id

    def set_camera_metadata(
        self,
        camera_id: str,
        farm_id: Optional[str],
        zone_id: Optional[str],
    ) -> None:
        self._mappings[camera_id] = (farm_id, zone_id)

    def resolve(self, camera_id: str) -> Tuple[Optional[str], Optional[str]]:
        if camera_id in self._mappings:
            return self._mappings[camera_id]
        return (self.default_farm_id, self.default_zone_id)


class ManagementCameraMetadataResolver(CameraMetadataResolver):
    """Read-only adapter querying Management Service for (farmId, zoneId) with TTL caching."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 3.0,
        cache_ttl_seconds: float = 60.0,
        internal_service_key: str = "",
        enabled: bool | Callable[[], bool] = True,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self._base_url = (base_url or "").rstrip("/")
        self._timeout = float(timeout_seconds)
        self._cache_ttl = max(0.0, float(cache_ttl_seconds))
        self._internal_service_key = (internal_service_key or "").strip()
        self._enabled = enabled
        self._transport = transport
        self._lock = threading.Lock()
        self._cache: Dict[str, Tuple[float, Tuple[Optional[str], Optional[str]]]] = {}

    def is_enabled(self) -> bool:
        if callable(self._enabled):
            return bool(self._enabled())
        return bool(self._enabled)

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    def resolve(self, camera_id: str) -> Tuple[Optional[str], Optional[str]]:
        if not self.is_enabled() or not self._base_url:
            return (None, None)

        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(camera_id)
            if cached is not None:
                expires_at, value = cached
                if now < expires_at:
                    return value
                self._cache.pop(camera_id, None)

        url = f"{self._base_url}/api/cameras/{quote(camera_id, safe='')}"
        headers = {"Accept": "application/json"}
        if self._internal_service_key:
            headers["X-Internal-Service-Key"] = self._internal_service_key

        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                resp = client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            logger.warning(
                "Management metadata lookup failed for camera '%s': %s",
                camera_id,
                exc.__class__.__name__,
            )
            return (None, None)

        if resp.status_code != 200:
            logger.warning(
                "Management metadata lookup returned HTTP %s for camera '%s'",
                resp.status_code,
                camera_id,
            )
            return (None, None)

        try:
            data = resp.json()
        except ValueError:
            logger.warning("Malformed JSON from Management metadata lookup for camera '%s'", camera_id)
            return (None, None)

        if not isinstance(data, dict):
            logger.warning("Unexpected payload type from Management metadata lookup for camera '%s'", camera_id)
            return (None, None)

        raw_farm = data.get("farm_id") or data.get("farmId")
        raw_zone = data.get("zone_id") or data.get("zoneId")
        farm_id = str(raw_farm).strip() if raw_farm else None
        zone_id = str(raw_zone).strip() if raw_zone else None
        result = (farm_id or None, zone_id or None)

        if self._cache_ttl > 0 and result[0] is not None:
            with self._lock:
                self._cache[camera_id] = (time.monotonic() + self._cache_ttl, result)

        return result


class StaticConfigCameraMetadataResolver(CameraMetadataResolver):
    """Static fallback resolver reading optional metadata from env JSON and/or cameras.yaml."""

    def __init__(
        self,
        cameras_yaml_path: Optional[Path | str] = None,
        env_json_provider: Optional[Callable[[], str]] = None,
    ) -> None:
        self._cameras_yaml_path = Path(cameras_yaml_path) if cameras_yaml_path else None
        self._env_json_provider = env_json_provider

    def _from_env_json(self, camera_id: str) -> Tuple[Optional[str], Optional[str]]:
        if self._env_json_provider is None:
            return (None, None)
        raw = (self._env_json_provider() or "").strip()
        if not raw:
            return (None, None)
        try:
            parsed = json.loads(raw)
        except ValueError:
            logger.warning("Invalid AI_CAMERA_METADATA_JSON payload; ignoring static env metadata")
            return (None, None)
        if not isinstance(parsed, dict):
            return (None, None)
        entry = parsed.get(camera_id)
        if not isinstance(entry, dict):
            return (None, None)
        farm_id = str(entry.get("farm_id") or entry.get("farmId") or "").strip() or None
        zone_id = str(entry.get("zone_id") or entry.get("zoneId") or "").strip() or None
        return (farm_id, zone_id)

    def _from_yaml(self, camera_id: str) -> Tuple[Optional[str], Optional[str]]:
        if self._cameras_yaml_path is None or not self._cameras_yaml_path.exists():
            return (None, None)
        try:
            import yaml

            data = yaml.safe_load(self._cameras_yaml_path.read_text(encoding="utf-8")) or {}
            for cam in data.get("cameras", []):
                if str(cam.get("camera_id", "")).strip() == camera_id:
                    farm_id = str(cam.get("farm_id") or cam.get("farmId") or "").strip() or None
                    zone_id = str(cam.get("zone_id") or cam.get("zoneId") or "").strip() or None
                    return (farm_id, zone_id)
        except Exception as exc:
            logger.warning("Failed reading static camera metadata from %s: %s", self._cameras_yaml_path, exc)
        return (None, None)

    def resolve(self, camera_id: str) -> Tuple[Optional[str], Optional[str]]:
        farm_id, zone_id = self._from_env_json(camera_id)
        if farm_id is not None or zone_id is not None:
            return (farm_id, zone_id)
        return self._from_yaml(camera_id)


class CompositeCameraMetadataResolver(CameraMetadataResolver):
    """Composite resolver: InMemory -> Management (TTL cached) -> Static config (YAML/env).

    Never fabricates fake IDs when unresolved; logs a warning and returns (None, None).
    """

    def __init__(
        self,
        memory_resolver: Optional[InMemoryCameraMetadataResolver] = None,
        management_resolver: Optional[ManagementCameraMetadataResolver] = None,
        static_resolver: Optional[CameraMetadataResolver] = None,
    ) -> None:
        self._memory = memory_resolver or InMemoryCameraMetadataResolver(
            default_farm_id=None,
            default_zone_id=None,
        )
        self._management = management_resolver
        self._static = static_resolver

    @property
    def _mappings(self) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
        """Expose inner in-memory mappings for test cleanup compatibility."""
        return self._memory._mappings

    def set_camera_metadata(
        self,
        camera_id: str,
        farm_id: Optional[str],
        zone_id: Optional[str],
    ) -> None:
        self._memory.set_camera_metadata(camera_id, farm_id, zone_id)

    def clear_cache(self) -> None:
        if self._management is not None:
            self._management.clear_cache()

    def resolve(self, camera_id: str) -> Tuple[Optional[str], Optional[str]]:
        farm_id, zone_id = self._memory.resolve(camera_id)
        if farm_id is not None or zone_id is not None:
            return (farm_id, zone_id)

        if self._management is not None:
            farm_id, zone_id = self._management.resolve(camera_id)
            if farm_id is not None or zone_id is not None:
                return (farm_id, zone_id)

        if self._static is not None:
            farm_id, zone_id = self._static.resolve(camera_id)
            if farm_id is not None or zone_id is not None:
                return (farm_id, zone_id)

        logger.warning(
            "Unable to resolve farmId/zoneId for camera '%s'; returning (None, None)",
            camera_id,
        )
        return (None, None)


def _build_default_resolver() -> CompositeCameraMetadataResolver:
    from app.config import AI_PIPELINE_DIR, settings

    mgmt_resolver = ManagementCameraMetadataResolver(
        base_url=settings.ai_management_service_url,
        timeout_seconds=settings.ai_registry_timeout_seconds,
        cache_ttl_seconds=settings.ai_metadata_cache_ttl_seconds,
        internal_service_key=settings.ai_internal_service_key,
        enabled=lambda: settings.ai_metadata_management_enabled,
    )
    static_resolver = StaticConfigCameraMetadataResolver(
        cameras_yaml_path=AI_PIPELINE_DIR / "configs" / "cameras.yaml",
        env_json_provider=lambda: settings.ai_camera_metadata_json,
    )
    return CompositeCameraMetadataResolver(
        memory_resolver=InMemoryCameraMetadataResolver(default_farm_id=None, default_zone_id=None),
        management_resolver=mgmt_resolver,
        static_resolver=static_resolver,
    )


default_camera_metadata_resolver = _build_default_resolver()

__all__ = [
    "CameraMetadataResolver",
    "CompositeCameraMetadataResolver",
    "InMemoryCameraMetadataResolver",
    "ManagementCameraMetadataResolver",
    "StaticConfigCameraMetadataResolver",
    "default_camera_metadata_resolver",
]
