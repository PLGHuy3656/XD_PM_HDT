"""Metadata resolver port for cameras to enrich events with farmId and zoneId."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple


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
    """In-memory resolver with explicit mappings and optional fallback defaults (for tests only)."""

    def __init__(
        self,
        mappings: Optional[Dict[str, Tuple[str, str]]] = None,
        default_farm_id: Optional[str] = None,
        default_zone_id: Optional[str] = None,
    ) -> None:
        self._mappings = dict(mappings or {})
        self.default_farm_id = default_farm_id
        self.default_zone_id = default_zone_id

    def set_camera_metadata(self, camera_id: str, farm_id: str, zone_id: str) -> None:
        self._mappings[camera_id] = (farm_id, zone_id)

    def resolve(self, camera_id: str) -> Tuple[Optional[str], Optional[str]]:
        if camera_id in self._mappings:
            return self._mappings[camera_id]
        return (self.default_farm_id, self.default_zone_id)


# Default production instance has NO fallback defaults (will return (None, None) for unmapped cameras)
default_camera_metadata_resolver = InMemoryCameraMetadataResolver(
    default_farm_id=None,
    default_zone_id=None,
)

__all__ = [
    "CameraMetadataResolver",
    "InMemoryCameraMetadataResolver",
    "default_camera_metadata_resolver",
]
