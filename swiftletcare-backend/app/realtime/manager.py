
import asyncio
import logging

from fastapi import WebSocket

logger = logging.getLogger("realtime")


class RealtimeManager:
    def __init__(self):
        self.active_connections: set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()

        async with self.lock:
            self.active_connections.add(websocket)

        logger.info(
            "WebSocket client connected. Total clients: %s",
            len(self.active_connections),
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self.lock:
            self.active_connections.discard(websocket)

        logger.info(
            "WebSocket client disconnected. Total clients: %s",
            len(self.active_connections),
        )

    async def broadcast(self, data: dict) -> None:
        async with self.lock:
            connections = list(self.active_connections)

        if not connections:
            return

        results = await asyncio.gather(
            *[
                websocket.send_json(data)
                for websocket in connections
            ],
            return_exceptions=True,
        )

        failed_connections = [
            websocket
            for websocket, result in zip(connections, results)
            if isinstance(result, Exception)
        ]

        for websocket in failed_connections:
            await self.disconnect(websocket)


realtime_manager = RealtimeManager()
