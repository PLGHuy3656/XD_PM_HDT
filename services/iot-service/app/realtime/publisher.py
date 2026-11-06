import asyncio
import logging
from typing import Any, Protocol

from fastapi import WebSocket

from app.schemas.api import RealtimeEvent

logger = logging.getLogger("iot_service.realtime")


class RealtimePublisher(Protocol):
    """Abstract protocol for publishing realtime domain events."""

    def publish(self, event: RealtimeEvent) -> None:
        """Publishes a normalized realtime event to connected subscribers."""
        ...


class WebSocketConnectionManager:
    """In-process WebSocket connection manager implementing RealtimePublisher.

    Isolates client connection/send failures so broken WebSocket clients never
    disrupt MQTT ingestion or domain service execution.
    """

    def __init__(self):
        self._connections: list[WebSocket] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def active_connections(self) -> list[WebSocket]:
        return list(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        """Accepts a new WebSocket connection and registers it."""
        await websocket.accept()
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        if websocket not in self._connections:
            self._connections.append(websocket)
        logger.info(
            "[WS] Client connected (active_connections=%d)",
            len(self._connections),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Removes a WebSocket connection safely."""
        if websocket in self._connections:
            self._connections.remove(websocket)
            logger.info(
                "[WS] Client disconnected (active_connections=%d)",
                len(self._connections),
            )

    def clear(self) -> None:
        """Clears all active connections (useful for test isolation)."""
        self._connections.clear()

    async def broadcast_async(self, payload: dict[str, Any]) -> None:
        """Broadcasts a JSON-serializable dictionary to all connected clients.

        Automatically prunes dead or errored connections.
        """
        if not self._connections:
            return

        dead_connections: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(payload)
            except Exception as exc:
                logger.warning(
                    "[WS] Failed to send event to client, pruning connection: %s",
                    exc,
                )
                dead_connections.append(ws)

        for dead_ws in dead_connections:
            self.disconnect(dead_ws)

    def publish(self, event: RealtimeEvent) -> None:
        """Synchronous entrypoint implementing RealtimePublisher.

        Safely bridges synchronous domain services (e.g. MQTT callbacks) to async
        WebSocket connections. Never raises exceptions to caller.
        """
        try:
            payload = event.model_dump(mode="json")
            if not self._connections:
                return

            try:
                running_loop = asyncio.get_running_loop()
                running_loop.create_task(self.broadcast_async(payload))
            except RuntimeError:
                if self._loop is not None and self._loop.is_running():
                    fut = asyncio.run_coroutine_threadsafe(
                        self.broadcast_async(payload), self._loop
                    )
                    try:
                        fut.result(timeout=2.0)
                    except Exception as exc:
                        logger.warning(
                            "[WS] Broadcast future failed or timed out: %s", exc
                        )
                else:
                    asyncio.run(self.broadcast_async(payload))
        except Exception as exc:
            logger.warning(
                "[WS] Unexpected error during realtime event publish: %s", exc
            )


ws_manager = WebSocketConnectionManager()
