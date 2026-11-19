"""Authoritative camera registry port (CP13 hardening R2).

Management Service is the single source of truth for camera registration,
device type and parent farm/zone. AI Service never trusts caller-supplied
farmId/zoneId for persisted CountUpdates: it resolves the camera through the
Management camera registry (GET /api/cameras/{cameraId}) using the caller's
bearer token, so Management also enforces the caller's farm authorization.

Failure policy is fail-closed:
- Management unreachable / 5xx / malformed response -> CameraRegistryUnavailable (503)
- Caller token rejected (401)                         -> CameraRegistryUnauthorized (401)
- Camera unknown, not a CAMERA, or not authorized     -> CameraNotAuthorized (403)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

import httpx


@dataclass(frozen=True)
class RegisteredCamera:
    camera_uuid: str
    node_id: str
    farm_id: str
    zone_id: Optional[str]


class CameraRegistryError(Exception):
    """Base error for registry resolution failures."""


class CameraRegistryUnavailable(CameraRegistryError):
    pass


class CameraRegistryUnauthorized(CameraRegistryError):
    pass


class CameraNotAuthorized(CameraRegistryError):
    pass


class CameraRegistry(ABC):
    @abstractmethod
    def resolve_camera(self, camera_id: str, bearer_token: str) -> RegisteredCamera:
        raise NotImplementedError


class ManagementCameraRegistry(CameraRegistry):
    """Resolves cameras through Management Service GET /api/cameras/{id}."""

    def __init__(self, base_url: str, timeout_seconds: float = 3.0, transport: Optional[httpx.BaseTransport] = None) -> None:
        self._base_url = (base_url or "").rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport

    def resolve_camera(self, camera_id: str, bearer_token: str) -> RegisteredCamera:
        if not self._base_url:
            raise CameraRegistryUnavailable("Management camera registry URL is not configured")
        url = f"{self._base_url}/api/cameras/{quote(camera_id, safe='')}"
        headers = {"Authorization": f"Bearer {bearer_token}", "Accept": "application/json"}
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                resp = client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            raise CameraRegistryUnavailable(exc.__class__.__name__) from exc

        if resp.status_code == 200:
            try:
                data = resp.json()
            except ValueError as exc:
                raise CameraRegistryUnavailable("Malformed registry response") from exc
            if not isinstance(data, dict):
                raise CameraRegistryUnavailable("Malformed registry response")
            dev_type = str(data.get("device_type") or "").upper()
            node_id = str(data.get("node_id") or "").strip()
            farm_id = str(data.get("farm_id") or "").strip()
            camera_uuid = str(data.get("device_id") or "").strip()
            if dev_type != "CAMERA" or data.get("is_active") is False:
                raise CameraNotAuthorized("Camera is not registered or not active")
            if not node_id or not farm_id:
                raise CameraRegistryUnavailable("Registry response missing node_id/farm_id")
            zone_id = data.get("zone_id")
            return RegisteredCamera(
                camera_uuid=camera_uuid,
                node_id=node_id,
                farm_id=farm_id,
                zone_id=str(zone_id).strip() if zone_id else None,
            )
        if resp.status_code == 401:
            raise CameraRegistryUnauthorized("Caller token rejected by Management")
        if resp.status_code in (400, 403, 404):
            raise CameraNotAuthorized("Camera is not registered or not authorized for caller")
        raise CameraRegistryUnavailable(f"Management returned {resp.status_code}")


__all__ = [
    "CameraNotAuthorized",
    "CameraRegistry",
    "CameraRegistryError",
    "CameraRegistryUnauthorized",
    "CameraRegistryUnavailable",
    "ManagementCameraRegistry",
    "RegisteredCamera",
]
