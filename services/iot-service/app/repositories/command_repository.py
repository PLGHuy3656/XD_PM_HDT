from typing import Protocol

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

    def clear(self) -> None:
        """Clears all command records (useful for test isolation)."""
        ...


class InMemoryCommandRepository:
    """In-memory implementation of CommandRepository for CP4 prototyping and tests."""

    def __init__(self):
        self._commands: dict[str, DeviceCommand] = {}

    def save(self, command: DeviceCommand) -> None:
        self._commands[command.command_id] = command

    def get(self, command_id: str) -> DeviceCommand | None:
        return self._commands.get(command_id)

    def update(self, command: DeviceCommand) -> None:
        self._commands[command.command_id] = command

    def list_by_device(
        self, device_id: str, limit: int = 100
    ) -> list[DeviceCommand]:
        cmds = [
            cmd for cmd in self._commands.values() if cmd.device_id == device_id
        ]
        cmds.sort(key=lambda c: c.created_at, reverse=True)
        return cmds[:limit]

    def clear(self) -> None:
        self._commands.clear()


default_command_repository = InMemoryCommandRepository()
