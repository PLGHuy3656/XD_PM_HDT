from typing import Protocol

from app.schemas.telemetry import AcceptedTelemetry


class TelemetryRepository(Protocol):
    """Abstract protocol for telemetry storage."""

    def save(self, telemetry: AcceptedTelemetry) -> None:
        """Persists an accepted telemetry record."""
        ...

    def get_latest(self, device_id: str) -> AcceptedTelemetry | None:
        """Retrieves the most recent telemetry record for a given device."""
        ...

    def list_by_device(
        self, device_id: str, limit: int = 100
    ) -> list[AcceptedTelemetry]:
        """Lists recent telemetry records for a given device."""
        ...

    def get_latest_by_farm(self, farm_id: str) -> AcceptedTelemetry | None:
        """Retrieves the most recent telemetry record for a given farm."""
        ...

    def list_by_farm(
        self, farm_id: str, limit: int = 100
    ) -> list[AcceptedTelemetry]:
        """Lists recent telemetry records for a given farm."""
        ...


class InMemoryTelemetryRepository:
    """In-memory implementation of TelemetryRepository for CP4 prototyping and tests."""

    def __init__(self):
        self._records: dict[str, list[AcceptedTelemetry]] = {}
        self._device_farms: dict[str, str] = {}

    def register_device_farm(self, device_id: str, farm_id: str) -> None:
        """Associates a device with a farm for farm-level telemetry queries."""
        self._device_farms[device_id] = farm_id

    def save(self, telemetry: AcceptedTelemetry) -> None:
        device_id = telemetry.device_id
        # Strictly map only explicitly registered devices; never fall back to a hardcoded farm UUID.
        if telemetry.farm_id is None:
            mapped_farm = self._device_farms.get(device_id)
            if mapped_farm is not None:
                object.__setattr__(telemetry, "farm_id", mapped_farm)
        if device_id not in self._records:
            self._records[device_id] = []
        self._records[device_id].append(telemetry)

    def get_latest(self, device_id: str) -> AcceptedTelemetry | None:
        records = self._records.get(device_id)
        if not records:
            return None
        return records[-1]

    def list_by_device(
        self, device_id: str, limit: int = 100
    ) -> list[AcceptedTelemetry]:
        records = self._records.get(device_id, [])
        return list(reversed(records))[:limit]

    def get_latest_by_farm(self, farm_id: str) -> AcceptedTelemetry | None:
        farm_records = self.list_by_farm(farm_id, limit=1)
        return farm_records[0] if farm_records else None

    def list_by_farm(
        self, farm_id: str, limit: int = 100
    ) -> list[AcceptedTelemetry]:
        matching: list[AcceptedTelemetry] = []
        for recs in self._records.values():
            for rec in recs:
                effective_farm = rec.farm_id or self._device_farms.get(rec.device_id)
                if effective_farm == farm_id:
                    matching.append(rec)
        matching.sort(key=lambda r: r.received_at, reverse=True)
        return matching[:limit]

    def clear(self) -> None:
        """Clears all in-memory records (useful for test resets)."""
        self._records.clear()
        self._device_farms.clear()


default_telemetry_repository = InMemoryTelemetryRepository()
