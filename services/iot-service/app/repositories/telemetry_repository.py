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


DEFAULT_DEVICE_FARM_MAP: dict[str, str] = {
    "SWC-DEMO-NODE-001": "a18d8eee-cb1a-4b00-b375-d505eb8128d7",
    "SWC-NODE-001": "a18d8eee-cb1a-4b00-b375-d505eb8128d7",
    "SWC-DEMO-NODE-002": "f8fc4fa7-0d27-4e0b-89c0-e676e0e73469",
    "SWC-NODE-002": "f8fc4fa7-0d27-4e0b-89c0-e676e0e73469",
}


class InMemoryTelemetryRepository:
    """In-memory implementation of TelemetryRepository for CP4 prototyping and tests."""

    def __init__(self):
        self._records: dict[str, list[AcceptedTelemetry]] = {}
        self._device_farms: dict[str, str] = dict(DEFAULT_DEVICE_FARM_MAP)

    def register_device_farm(self, device_id: str, farm_id: str) -> None:
        """Associates a device with a farm for farm-level telemetry queries."""
        self._device_farms[device_id] = farm_id

    def save(self, telemetry: AcceptedTelemetry) -> None:
        device_id = telemetry.device_id
        if telemetry.farm_id is None:
            farm_id = self._device_farms.get(device_id)
            if farm_id is None:
                farm_id = "a18d8eee-cb1a-4b00-b375-d505eb8128d7"
                self._device_farms[device_id] = farm_id
            object.__setattr__(telemetry, "farm_id", farm_id)
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
        for dev_id, recs in self._records.items():
            for rec in recs:
                if rec.farm_id == farm_id or self._device_farms.get(rec.device_id) == farm_id:
                    matching.append(rec)
        matching.sort(key=lambda r: r.received_at, reverse=True)
        return matching[:limit]

    def clear(self) -> None:
        """Clears all in-memory records (useful for test resets)."""
        self._records.clear()
        self._device_farms = dict(DEFAULT_DEVICE_FARM_MAP)


default_telemetry_repository = InMemoryTelemetryRepository()
