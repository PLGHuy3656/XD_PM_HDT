from typing import Protocol

from app.schemas.presence import DevicePresence


class DevicePresenceRepository(Protocol):
    """Abstract protocol for runtime device presence storage."""

    def get(self, device_id: str) -> DevicePresence | None:
        """Retrieves presence record for a device by its ID."""
        ...

    def save(self, presence: DevicePresence) -> None:
        """Saves or updates a device presence record."""
        ...

    def list_all(self) -> list[DevicePresence]:
        """Lists all tracked device presence records."""
        ...

    def clear(self) -> None:
        """Clears all presence records (useful for test isolation)."""
        ...


class InMemoryDevicePresenceRepository:
    """In-memory implementation of DevicePresenceRepository for CP4 prototype and tests."""

    def __init__(self):
        self._devices: dict[str, DevicePresence] = {}

    def get(self, device_id: str) -> DevicePresence | None:
        return self._devices.get(device_id)

    def save(self, presence: DevicePresence) -> None:
        self._devices[presence.device_id] = presence

    def list_all(self) -> list[DevicePresence]:
        return list(self._devices.values())

    def clear(self) -> None:
        self._devices.clear()


default_presence_repository = InMemoryDevicePresenceRepository()
