"""Device Business Context / Metadata Resolver for IoT Domain Events.

Resolves deviceId (e.g. SWC-NODE-001) to canonical farmId and zoneId.
Adheres to the fallback policy: never fabricate fake IDs (e.g. UNKNOWN_FARM),
returns None or uses configured mapping.
"""

from typing import NamedTuple


class DeviceLocation(NamedTuple):
    farm_id: str
    zone_id: str


class DeviceMetadataResolver:
    """In-memory metadata resolver mapping device identity to business farm/zone context."""

    def __init__(self, static_mapping: dict[str, DeviceLocation] | None = None):
        # Default canonical mappings matching project contracts
        self._mapping: dict[str, DeviceLocation] = static_mapping or {
            "SWC-NODE-001": DeviceLocation(farm_id="FARM-01", zone_id="ZONE-01"),
            "ESP32-CTRL-01": DeviceLocation(farm_id="farm-binh-an", zone_id="zone-a"),
            "ESP32-CTRL-02": DeviceLocation(farm_id="farm-binh-an", zone_id="zone-b"),
            "ESP32-CTRL-04": DeviceLocation(farm_id="farm-phu-an", zone_id="zone-d"),
            "AUDIO-01": DeviceLocation(farm_id="farm-binh-an", zone_id="zone-c"),
            "swc-h01-f01-node01": DeviceLocation(farm_id="FARM-01", zone_id="ZONE-01"),
        }

    def register(self, device_id: str, farm_id: str, zone_id: str) -> None:
        self._mapping[device_id] = DeviceLocation(farm_id=farm_id, zone_id=zone_id)

    def resolve(self, device_id: str) -> DeviceLocation | None:
        """Resolves deviceId to DeviceLocation(farm_id, zone_id).

        Returns None if device is unregistered.
        """
        return self._mapping.get(device_id)


default_metadata_resolver = DeviceMetadataResolver()
