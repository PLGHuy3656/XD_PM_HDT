"""Thread-safe in-memory runtime state store for canonical AI V1 objects (CP5.2 Task 6).

Stores:
- Latest `DetectionResult` per cameraId
- Latest `CountUpdate` per cameraId
- Recent `AIEvent` records (bounded ring buffer, indexed by eventId)
- Latest `CameraRuntimeStatus` per cameraId

Also implements `RuntimeEventSink` so it can be attached directly to `CameraPipeline`
or `AIRuntimeManager`.
"""
from __future__ import annotations

import threading
from collections import deque
from typing import Deque, Dict, List, Optional

from app.runtime.sink import BaseRuntimeSink
from app.schemas.canonical import (
    AIEvent,
    CameraRuntimeStatus,
    CountUpdate,
    DetectionResult,
)


class InMemoryAIRuntimeStateStore(BaseRuntimeSink):
    """Thread-safe in-memory state store for AI runtime state."""

    def __init__(self, max_events: int = 500, max_count_history: int = 100) -> None:
        if max_events <= 0:
            raise ValueError("max_events must be > 0")
        if max_count_history <= 0:
            raise ValueError("max_count_history must be > 0")
        self._max_events = max_events
        self._max_count_history = max_count_history
        self._lock = threading.RLock()
        self._latest_detections: Dict[str, DetectionResult] = {}
        self._latest_counts: Dict[str, CountUpdate] = {}
        self._latest_statuses: Dict[str, CameraRuntimeStatus] = {}
        self._recent_events: Deque[AIEvent] = deque()
        self._events_by_id: Dict[str, AIEvent] = {}
        self._count_history: Dict[str, Deque[CountUpdate]] = {}

    # ------------------------------------------------------------------
    # RuntimeEventSink implementation
    # ------------------------------------------------------------------
    def on_detection(self, result: DetectionResult) -> None:
        self.record_detection(result)

    def on_count(self, update: CountUpdate) -> None:
        self.record_count(update)

    def on_event(self, event: AIEvent) -> None:
        self.record_event(event)

    def on_status(self, status: CameraRuntimeStatus) -> None:
        self.record_status(status)

    # ------------------------------------------------------------------
    # Explicit write methods
    # ------------------------------------------------------------------
    def record_detection(self, result: DetectionResult) -> None:
        with self._lock:
            self._latest_detections[result.cameraId] = result

    def record_count(self, update: CountUpdate) -> None:
        with self._lock:
            self._latest_counts[update.cameraId] = update
            if update.cameraId not in self._count_history:
                self._count_history[update.cameraId] = deque(maxlen=self._max_count_history)
            self._count_history[update.cameraId].append(update)

    def record_event(self, event: AIEvent) -> None:
        with self._lock:
            if len(self._recent_events) >= self._max_events:
                evicted = self._recent_events.popleft()
                self._events_by_id.pop(evicted.eventId, None)
            self._recent_events.append(event)
            self._events_by_id[event.eventId] = event

    def record_status(self, status: CameraRuntimeStatus) -> None:
        with self._lock:
            self._latest_statuses[status.cameraId] = status

    # ------------------------------------------------------------------
    # Read / query methods
    # ------------------------------------------------------------------
    def get_latest_detection(self, camera_id: str) -> Optional[DetectionResult]:
        with self._lock:
            return self._latest_detections.get(camera_id)

    def get_latest_count(self, camera_id: str) -> Optional[CountUpdate]:
        with self._lock:
            return self._latest_counts.get(camera_id)

    def get_count_history(self, camera_id: str, limit: int = 20) -> List[CountUpdate]:
        """Return recent CountUpdate records for a camera ordered newest-first."""
        if limit <= 0:
            raise ValueError("limit must be > 0")
        with self._lock:
            history = self._count_history.get(camera_id)
            if not history:
                return []
            items = list(reversed(history))
            return items[:limit]

    def get_camera_status(self, camera_id: str) -> Optional[CameraRuntimeStatus]:
        with self._lock:
            return self._latest_statuses.get(camera_id)

    def list_camera_statuses(self) -> List[CameraRuntimeStatus]:
        with self._lock:
            return [self._latest_statuses[k] for k in sorted(self._latest_statuses.keys())]

    def list_events(
        self,
        camera_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AIEvent]:
        """Return recent AIEvent records ordered newest-first."""
        if limit <= 0:
            raise ValueError("limit must be > 0")
        with self._lock:
            items = list(reversed(self._recent_events))
            if camera_id is not None:
                items = [e for e in items if e.cameraId == camera_id]
            return items[:limit]

    def get_event(self, event_id: str) -> Optional[AIEvent]:
        with self._lock:
            return self._events_by_id.get(event_id)

    def clear(self) -> None:
        with self._lock:
            self._latest_detections.clear()
            self._latest_counts.clear()
            self._latest_statuses.clear()
            self._recent_events.clear()
            self._events_by_id.clear()
            self._count_history.clear()


__all__ = ["InMemoryAIRuntimeStateStore"]
