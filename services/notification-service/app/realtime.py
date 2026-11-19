import asyncio
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class NotificationConnectionManager:
    def __init__(self):
        self.connections: dict[WebSocket, str] = {}
        self.lock = asyncio.Lock()

    async def register(self, websocket: WebSocket, user_id: str) -> None:
        async with self.lock:
            self.connections[websocket] = user_id

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self.lock:
            self.connections.pop(websocket, None)

    async def broadcast(self, user_id: str, data: dict) -> None:
        async with self.lock:
            connections = [
                websocket
                for websocket, connected_user_id in self.connections.items()
                if connected_user_id == user_id
            ]

        results = await asyncio.gather(
            *(websocket.send_json(data) for websocket in connections),
            return_exceptions=True,
        )
        for websocket, result in zip(connections, results):
            if isinstance(result, Exception):
                logger.warning("Removing disconnected notification websocket")
                await self.disconnect(websocket)


notification_connections = NotificationConnectionManager()
