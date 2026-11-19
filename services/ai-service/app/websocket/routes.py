"""WebSocket V1 route `/ws/ai` (CP5.3 Task 9)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.websocket.manager import AIWebSocketManager

router = APIRouter(tags=["AI Realtime WebSocket"])


@router.websocket("/ws/ai")
async def ai_realtime_websocket(
    websocket: WebSocket,
    cameraId: Optional[str] = Query(
        default=None,
        description="Optional cameraId filter. When omitted, receives events for all cameras.",
    ),
) -> None:
    ws_manager: AIWebSocketManager = websocket.app.state.ws_manager
    await ws_manager.connect(websocket, camera_id=cameraId)
    try:
        while True:
            # Keep connection alive and detect client disconnects
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        ws_manager.disconnect(websocket)
