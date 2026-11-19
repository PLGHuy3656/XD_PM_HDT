"""WebSocket connection manager and thread/async-safe dispatcher (CP6.3)."""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
from typing import Any, Dict, List, Literal, Optional

from fastapi import WebSocket

log = logging.getLogger("swiftletcare.notification.websocket")

WebSocketEventType = Literal[
    "alert.created",
    "alert.updated",
    "notification.created",
    "notification.updated",
]


def build_ws_envelope(
    event_type: WebSocketEventType,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Build canonical WebSocket event envelope."""
    return {
        "type": event_type,
        "data": data,
    }


class NotificationWebSocketManager:
    """Manages active `/ws/notifications` clients and provides user-scoped routing."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._clients: Dict[WebSocket, Optional[str]] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._pending_futures: List[concurrent.futures.Future[Any]] = []

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._clients)

    def user_active_count(self, user_id: str) -> int:
        with self._lock:
            return sum(1 for uid in self._clients.values() if uid == user_id)

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind running asyncio event loop for thread-safe cross-thread scheduling."""
        with self._lock:
            self._loop = loop

    async def connect(
        self,
        websocket: WebSocket,
        user_id: Optional[str] = None,
    ) -> None:
        await websocket.accept()
        running_loop = asyncio.get_running_loop()
        normalized_uid = user_id.strip() if user_id and user_id.strip() else None
        with self._lock:
            self._loop = running_loop
            self._clients[websocket] = normalized_uid

    def disconnect(self, websocket: WebSocket) -> None:
        with self._lock:
            self._clients.pop(websocket, None)

    async def broadcast(self, envelope: Dict[str, Any]) -> None:
        """Broadcast an event envelope to all connected clients (e.g. alert.created, alert.updated)."""
        with self._lock:
            snapshot = list(self._clients.keys())

        if not snapshot:
            return

        dead_clients: List[WebSocket] = []
        for ws in snapshot:
            try:
                await ws.send_json(envelope)
            except Exception as exc:
                log.debug("Removing failed/disconnected WebSocket client: %s", exc)
                dead_clients.append(ws)

        if dead_clients:
            with self._lock:
                for ws in dead_clients:
                    self._clients.pop(ws, None)

    async def send_to_user(self, user_id: str, envelope: Dict[str, Any]) -> None:
        """Send an event envelope strictly to clients authenticated/associated with user_id."""
        with self._lock:
            snapshot = [
                ws for ws, uid in self._clients.items() if uid == user_id
            ]

        if not snapshot:
            return

        dead_clients: List[WebSocket] = []
        for ws in snapshot:
            try:
                await ws.send_json(envelope)
            except Exception as exc:
                log.debug("Removing failed user client %s: %s", user_id, exc)
                dead_clients.append(ws)

        if dead_clients:
            with self._lock:
                for ws in dead_clients:
                    self._clients.pop(ws, None)

    def broadcast_from_sync(self, envelope: Dict[str, Any]) -> None:
        """Sync -> Async bridge: broadcast to all clients from synchronous domain callbacks."""
        self._schedule_coroutine(self.broadcast(envelope))

    def send_to_user_from_sync(self, user_id: str, envelope: Dict[str, Any]) -> None:
        """Sync -> Async bridge: deliver to user from synchronous domain callbacks."""
        self._schedule_coroutine(self.send_to_user(user_id, envelope))

    def _schedule_coroutine(self, coro: Any) -> None:
        with self._lock:
            if not self._clients:
                # Close the coroutine to prevent unawaited coroutine warning
                if asyncio.iscoroutine(coro):
                    coro.close()
                return
            target_loop = self._loop

        if target_loop is None or target_loop.is_closed():
            if asyncio.iscoroutine(coro):
                coro.close()
            return

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop is target_loop:
            running_loop.create_task(coro)
            return

        if target_loop.is_running():
            try:
                fut = asyncio.run_coroutine_threadsafe(coro, target_loop)
                with self._lock:
                    self._pending_futures = [
                        f for f in self._pending_futures if not f.done()
                    ]
                    self._pending_futures.append(fut)
            except RuntimeError:
                if asyncio.iscoroutine(coro):
                    coro.close()
        else:
            if asyncio.iscoroutine(coro):
                coro.close()

    def flush_sync(self, timeout: float = 2.0) -> None:
        """Wait for any pending cross-thread scheduled futures to finish."""
        with self._lock:
            futures = list(self._pending_futures)
            self._pending_futures.clear()

        for fut in futures:
            try:
                fut.result(timeout=timeout)
            except Exception:
                pass

    async def close_all(self) -> None:
        """Disconnect and close all active WebSocket clients cleanly."""
        with self._lock:
            clients = list(self._clients.keys())
            self._clients.clear()

        for ws in clients:
            try:
                await ws.close()
            except Exception:
                pass


__all__ = [
    "NotificationWebSocketManager",
    "WebSocketEventType",
    "build_ws_envelope",
]
