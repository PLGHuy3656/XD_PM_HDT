"""WebSocket V1 connection manager and thread-safe RuntimeEventSink bridge (CP5.3 Task 9, 10, 11).

Canonical WebSocket event envelope:
{
  "type": "detection.updated" | "count.updated" | "ai.event" | "camera.status",
  "cameraId": "CAM-01",
  "data": { ...canonical V1 domain object... }
}

Thread / Async Safety:
`CameraPipeline` may execute synchronously in a background worker thread while
FastAPI/WebSocket runs on an `asyncio` event loop. `WebSocketRuntimeSink` bridges
synchronous sink callbacks (`on_detection`, `on_count`, `on_event`, `on_status`)
to the event loop via `asyncio.run_coroutine_threadsafe` (when called from a
worker thread) or `loop.create_task` (when called from the event loop thread).
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
import time
from typing import Any, Dict, List, Literal, Optional

from fastapi import WebSocket

from app.runtime.camera_pipeline import CameraPipeline
from app.runtime.sink import BaseRuntimeSink
from app.schemas.canonical import (
    AIEvent,
    CameraRuntimeStatus,
    CountUpdate,
    DetectionResult,
)

log = logging.getLogger("swiftletcare.ai.websocket")

WebSocketEventType = Literal[
    "detection.updated",
    "count.updated",
    "ai.event",
    "camera.status",
]


def build_ws_envelope(
    event_type: WebSocketEventType,
    camera_id: str,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the canonical WebSocket V1 event envelope."""
    return {
        "type": event_type,
        "cameraId": camera_id,
        "data": data,
    }


class WebSocketRuntimeSink(BaseRuntimeSink):
    """RuntimeEventSink observer forwarding canonical domain events to AIWebSocketManager."""

    def __init__(
        self,
        ws_manager: "AIWebSocketManager",
        detection_max_hz: float = 0.0,
    ) -> None:
        self._ws_manager = ws_manager
        self.detection_max_hz = max(0.0, float(detection_max_hz))
        self._last_detection_emit_ts: Dict[str, float] = {}
        self._lock = threading.Lock()

    def on_detection(self, result: DetectionResult) -> None:
        if self.detection_max_hz > 0.0:
            now = time.monotonic()
            min_interval = 1.0 / self.detection_max_hz
            with self._lock:
                last_ts = self._last_detection_emit_ts.get(result.cameraId)
                if last_ts is not None and (now - last_ts) < min_interval:
                    return
                self._last_detection_emit_ts[result.cameraId] = now

        envelope = build_ws_envelope(
            "detection.updated",
            result.cameraId,
            result.to_dict(),
        )
        self._ws_manager.publish_from_sync(envelope)

    def on_count(self, update: CountUpdate) -> None:
        envelope = build_ws_envelope(
            "count.updated",
            update.cameraId,
            update.to_dict(),
        )
        self._ws_manager.publish_from_sync(envelope)

    def on_event(self, event: AIEvent) -> None:
        data = event.to_dict()
        if data.get("snapshot"):
            data["snapshot"] = CameraPipeline.normalize_snapshot_ref(data["snapshot"])
        envelope = build_ws_envelope(
            "ai.event",
            event.cameraId,
            data,
        )
        self._ws_manager.publish_from_sync(envelope)

    def on_status(self, status: CameraRuntimeStatus) -> None:
        envelope = build_ws_envelope(
            "camera.status",
            status.cameraId,
            status.to_dict(),
        )
        self._ws_manager.publish_from_sync(envelope)


class AIWebSocketManager:
    """Manages active `/ws/ai` WebSocket clients and thread-safe broadcasts."""

    def __init__(self, detection_max_hz: float = 0.0) -> None:
        self._lock = threading.RLock()
        self._clients: Dict[WebSocket, Optional[str]] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._pending_futures: List[concurrent.futures.Future[Any]] = []
        self._sink = WebSocketRuntimeSink(self, detection_max_hz=detection_max_hz)

    @property
    def detection_max_hz(self) -> float:
        return self._sink.detection_max_hz

    @detection_max_hz.setter
    def detection_max_hz(self, hz: float) -> None:
        self._sink.detection_max_hz = max(0.0, float(hz))

    @property
    def sink(self) -> WebSocketRuntimeSink:
        return self._sink

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._clients)

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind the running asyncio event loop for cross-thread scheduling."""
        with self._lock:
            self._loop = loop

    async def connect(
        self,
        websocket: WebSocket,
        camera_id: Optional[str] = None,
    ) -> None:
        await websocket.accept()
        running_loop = asyncio.get_running_loop()
        normalized_cam = camera_id.strip() if camera_id and camera_id.strip() else None
        with self._lock:
            self._loop = running_loop
            self._clients[websocket] = normalized_cam

    def disconnect(self, websocket: WebSocket) -> None:
        with self._lock:
            self._clients.pop(websocket, None)

    async def broadcast(self, envelope: Dict[str, Any]) -> None:
        """Broadcast a canonical envelope to all matching connected WebSocket clients."""
        with self._lock:
            snapshot = list(self._clients.items())

        if not snapshot:
            return

        target_cam = envelope.get("cameraId")
        dead_clients: List[WebSocket] = []

        for ws, cam_filter in snapshot:
            if cam_filter is not None and cam_filter != target_cam:
                continue
            try:
                await ws.send_json(envelope)
            except Exception as exc:
                log.debug("Removing disconnected/failing WebSocket client: %s", exc)
                dead_clients.append(ws)

        if dead_clients:
            with self._lock:
                for ws in dead_clients:
                    self._clients.pop(ws, None)

    def publish_from_sync(self, envelope: Dict[str, Any]) -> None:
        """Thread-safe bridge from synchronous RuntimeEventSink callbacks to async WebSocket."""
        with self._lock:
            if not self._clients:
                return
            target_loop = self._loop

        if target_loop is None or target_loop.is_closed():
            return

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop is target_loop:
            running_loop.create_task(self.broadcast(envelope))
            return

        if target_loop.is_running():
            try:
                fut = asyncio.run_coroutine_threadsafe(
                    self.broadcast(envelope),
                    target_loop,
                )
                with self._lock:
                    self._pending_futures = [
                        f for f in self._pending_futures if not f.done()
                    ]
                    self._pending_futures.append(fut)
            except RuntimeError:
                # Event loop stopped concurrently; ignore gracefully
                pass

    def flush_sync(self, timeout: float = 2.0) -> None:
        """Wait for any pending cross-thread broadcasts to finish (useful in tests/shutdown)."""
        with self._lock:
            futures = list(self._pending_futures)
            self._pending_futures.clear()

        for fut in futures:
            try:
                fut.result(timeout=timeout)
            except Exception:
                pass

    async def close_all(self) -> None:
        """Disconnect and close all active WebSocket clients cleanly on shutdown."""
        with self._lock:
            clients = list(self._clients.keys())
            self._clients.clear()

        for ws in clients:
            try:
                await ws.close()
            except Exception:
                pass


__all__ = [
    "AIWebSocketManager",
    "WebSocketEventType",
    "WebSocketRuntimeSink",
    "build_ws_envelope",
]
