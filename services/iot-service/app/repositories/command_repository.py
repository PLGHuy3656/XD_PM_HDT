import threading
from typing import Any, Iterable, Protocol

from app.schemas.command import DeviceCommand


class CommandRepository(Protocol):
    """Abstract protocol for runtime command tracking."""

    def save(self, command: DeviceCommand) -> None:
        """Persists a new command record."""
        ...

    def get(self, command_id: str) -> DeviceCommand | None:
        """Retrieves a command record by its commandId."""
        ...

    def update(self, command: DeviceCommand) -> None:
        """Updates an existing command record."""
        ...

    def list_by_device(
        self, device_id: str, limit: int = 100
    ) -> list[DeviceCommand]:
        """Lists recent command records for a device, newest first."""
        ...

    def list_all(self) -> list[DeviceCommand]:
        """Lists all tracked command records."""
        ...

    def clear(self) -> None:
        """Clears all command records (useful for test isolation)."""
        ...


class InMemoryCommandRepository:
    """In-memory implementation of CommandRepository for CP4 prototyping and tests.

    INT01-R1: all mutations are serialized by a re-entrant lock and expose an atomic
    ``compare_and_update`` so the MQTT ACK thread and the asyncio TIMEOUT sweeper can
    never overwrite each other's terminal transition (e.g. TIMEOUT -> SUCCESS).

    LIMITATION (documented): records live in process memory only. Restarting the IoT
    Service drops every tracked command; a later ACK for a dropped command is rejected
    as "Unknown commandId" and never becomes SUCCESS.
    """

    def __init__(self):
        self._commands: dict[str, DeviceCommand] = {}
        self._lock = threading.RLock()

    def save(self, command: DeviceCommand) -> None:
        with self._lock:
            self._commands[command.command_id] = command

    def get(self, command_id: str) -> DeviceCommand | None:
        with self._lock:
            return self._commands.get(command_id)

    def update(self, command: DeviceCommand) -> None:
        with self._lock:
            self._commands[command.command_id] = command

    def compare_and_update(
        self,
        command_id: str,
        expected_statuses: Iterable[str],
        updates: dict[str, Any],
    ) -> DeviceCommand | None:
        """Atomically applies ``updates`` only if the current status is in ``expected_statuses``.

        Returns the updated record, or None when the record is missing or its status changed.
        """
        expected = tuple(expected_statuses)
        with self._lock:
            current = self._commands.get(command_id)
            if current is None or current.status not in expected:
                return None
            updated = current.model_copy(update=updates)
            self._commands[command_id] = updated
            return updated

    def list_by_device(
        self, device_id: str, limit: int = 100
    ) -> list[DeviceCommand]:
        with self._lock:
            cmds = [
                cmd for cmd in self._commands.values() if cmd.device_id == device_id
            ]
        cmds.sort(key=lambda c: c.created_at, reverse=True)
        return cmds[:limit]

    def list_all(self) -> list[DeviceCommand]:
        with self._lock:
            return list(self._commands.values())

    def clear(self) -> None:
        with self._lock:
            self._commands.clear()


def compare_and_update(
    repository: Any,
    command_id: str,
    expected_statuses: Iterable[str],
    updates: dict[str, Any],
) -> DeviceCommand | None:
    """Repository-agnostic compare-and-update (falls back to read-check-write for custom repos)."""
    if hasattr(repository, "compare_and_update"):
        return repository.compare_and_update(command_id, expected_statuses, updates)
    current = repository.get(command_id)
    if current is None or current.status not in tuple(expected_statuses):
        return None
    updated = current.model_copy(update=updates)
    repository.update(updated)
    return updated


default_command_repository = InMemoryCommandRepository()
