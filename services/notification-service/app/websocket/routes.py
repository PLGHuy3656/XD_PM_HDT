"""WebSocket endpoint for realtime alert and notification delivery (CP6.3)."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.dependencies import get_ws_manager
from app.websocket.manager import NotificationWebSocketManager

log = logging.getLogger("swiftletcare.notification.websocket.route")

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    user_id: Optional[str] = Query(
        None,
        alias="userId",
        description="User identity scope for local prototype. Replaced by Auth token in production.",
    ),
) -> None:
    """Realtime WebSocket stream for Alerts (broadcast) and Notifications (user-scoped).

    Local Prototype Identity Note:
    Passing `userId` via query param is a local prototype mechanism only.
    Final Gateway/Auth integration will derive identity from authenticated session/token.
    """
    manager: NotificationWebSocketManager = get_ws_manager()
    await manager.connect(websocket, user_id=user_id)
    log.info("WebSocket connected (user_id=%s, active_count=%d)", user_id, manager.active_count)

    try:
        while True:
            # Keep connection open; clients may optionally send ping/messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        log.info("WebSocket disconnected (user_id=%s, remaining=%d)", user_id, manager.active_count)
    except Exception as exc:
        manager.disconnect(websocket)
        log.debug("WebSocket terminated with error: %s", exc)


__all__ = ["router"]
