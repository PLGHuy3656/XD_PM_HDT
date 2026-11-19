"""
Deprecated Legacy IoT Adapter Shim (Retired in CP8.1)

Direct SQL access from Management Service to `swiftletcare.device_latest_state`
has been removed per the frozen CP8.0 Data Ownership & Persistence Contract V1.
All runtime presence queries now delegate to `IoTServiceAdapter` over HTTP:
    GET /api/iot/devices/presence
    GET /api/iot/devices/{device_id}/presence
"""

from typing import Any

from app.adapters.iot_service_adapter import IoTServiceAdapter, iot_service_adapter


class LegacyIoTAdapter:
    """Deprecated compatibility wrapper delegating strictly to IoTServiceAdapter (HTTP)."""

    def __init__(self, adapter: IoTServiceAdapter | None = None):
        self._adapter = adapter or iot_service_adapter

    def get_devices_runtime_state(
        self, device_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        return self._adapter.get_devices_runtime_state(device_ids)

    def get_devices_presence_counts(
        self, device_ids: list[str]
    ) -> tuple[int, int]:
        return self._adapter.get_devices_presence_counts(device_ids)


legacy_iot_adapter = LegacyIoTAdapter()
