"""Runtime event sink abstraction for decoupling CameraPipeline from transports (CP5.2 Task 5).

CameraPipeline emits canonical domain objects exclusively through `RuntimeEventSink`:
- `on_detection(result: DetectionResult)`
- `on_count(update: CountUpdate)`
- `on_event(event: AIEvent)`
- `on_status(status: CameraRuntimeStatus)`

This allows CP5.3 to attach in-memory state stores and WebSocket broadcasters,
and later RabbitMQ publishers, without changing CameraPipeline logic.
"""
from __future__ import annotations

import logging
from typing import Callable, Iterable, List, Optional, Protocol, runtime_checkable

from app.schemas.canonical import (
    AIEvent,
    CameraRuntimeStatus,
    CountUpdate,
    DetectionResult,
)

log = logging.getLogger("swiftletcare.ai.sink")


@runtime_checkable
class RuntimeEventSink(Protocol):
    """Transport-neutral consumer of canonical AI runtime outputs."""

    def on_detection(self, result: DetectionResult) -> None:
        """Called when a frame's DetectionResult is produced."""

    def on_count(self, update: CountUpdate) -> None:
        """Called when a CountUpdate is emitted (on crossing or periodic interval)."""

    def on_event(self, event: AIEvent) -> None:
        """Called when an immediate AIEvent (e.g. PREDATOR_DETECTED) triggers."""

    def on_status(self, status: CameraRuntimeStatus) -> None:
        """Called when CameraRuntimeStatus transitions or updates."""


class BaseRuntimeSink:
    """Base no-op implementation of RuntimeEventSink for selective subclassing."""

    def on_detection(self, result: DetectionResult) -> None:
        pass

    def on_count(self, update: CountUpdate) -> None:
        pass

    def on_event(self, event: AIEvent) -> None:
        pass

    def on_status(self, status: CameraRuntimeStatus) -> None:
        pass


class NullRuntimeSink(BaseRuntimeSink):
    """No-op sink used when no downstream observer is attached."""


class CallbackRuntimeSink(BaseRuntimeSink):
    """Adapter turning plain Python callables into a RuntimeEventSink."""

    def __init__(
        self,
        on_detection: Optional[Callable[[DetectionResult], None]] = None,
        on_count: Optional[Callable[[CountUpdate], None]] = None,
        on_event: Optional[Callable[[AIEvent], None]] = None,
        on_status: Optional[Callable[[CameraRuntimeStatus], None]] = None,
    ) -> None:
        self._on_detection = on_detection
        self._on_count = on_count
        self._on_event = on_event
        self._on_status = on_status

    def on_detection(self, result: DetectionResult) -> None:
        if self._on_detection is not None:
            self._on_detection(result)

    def on_count(self, update: CountUpdate) -> None:
        if self._on_count is not None:
            self._on_count(update)

    def on_event(self, event: AIEvent) -> None:
        if self._on_event is not None:
            self._on_event(event)

    def on_status(self, status: CameraRuntimeStatus) -> None:
        if self._on_status is not None:
            self._on_status(status)


class CompositeRuntimeSink(BaseRuntimeSink):
    """Fan-out sink dispatching canonical domain objects to multiple child sinks."""

    def __init__(
        self,
        sinks: Optional[Iterable[RuntimeEventSink]] = None,
        isolate_errors: bool = True,
    ) -> None:
        self._sinks: List[RuntimeEventSink] = list(sinks or [])
        self._isolate_errors = isolate_errors

    @property
    def sinks(self) -> List[RuntimeEventSink]:
        return list(self._sinks)

    def add_sink(self, sink: RuntimeEventSink) -> None:
        if sink not in self._sinks:
            self._sinks.append(sink)

    def remove_sink(self, sink: RuntimeEventSink) -> None:
        if sink in self._sinks:
            self._sinks.remove(sink)

    def _dispatch(self, method_name: str, payload: object) -> None:
        for sink in list(self._sinks):
            try:
                getattr(sink, method_name)(payload)
            except Exception as exc:
                if not self._isolate_errors:
                    raise
                log.exception("Sink %r raised error in %s: %s", sink, method_name, exc)

    def on_detection(self, result: DetectionResult) -> None:
        self._dispatch("on_detection", result)

    def on_count(self, update: CountUpdate) -> None:
        self._dispatch("on_count", update)

    def on_event(self, event: AIEvent) -> None:
        self._dispatch("on_event", event)

    def on_status(self, status: CameraRuntimeStatus) -> None:
        self._dispatch("on_status", status)


__all__ = [
    "BaseRuntimeSink",
    "CallbackRuntimeSink",
    "CompositeRuntimeSink",
    "NullRuntimeSink",
    "RuntimeEventSink",
]
