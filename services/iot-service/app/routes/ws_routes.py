from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.realtime.publisher import WebSocketConnectionManager
from app.routes.dependencies import get_ws_manager

router = APIRouter(tags=["Realtime"])


@router.websocket("/ws/iot")
async def iot_websocket_endpoint(
    websocket: WebSocket,
    manager: WebSocketConnectionManager = Depends(get_ws_manager),
):
    """WebSocket endpoint streaming normalized IoT realtime events:

    - telemetry.updated
    - presence.updated
    - command.updated
    """
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and detect client disconnects
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
