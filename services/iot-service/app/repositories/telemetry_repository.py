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


class InMemoryTelemetryRepository:
    """In-memory implementation of TelemetryRepository for CP4 prototyping and tests."""

    def __init__(self):
        self._records: dict[str, list[AcceptedTelemetry]] = {}

    def save(self, telemetry: AcceptedTelemetry) -> None:
        device_id = telemetry.device_id
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

    def clear(self) -> None:
        """Clears all in-memory records (useful for test resets)."""
        self._records.clear()


default_telemetry_repository = InMemoryTelemetryRepository()
