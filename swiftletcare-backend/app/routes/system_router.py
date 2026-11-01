import asyncio
import json

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)

from app.realtime.manager import realtime_manager
from app.services.management_authorization import (
    get_monitorable_device_node_ids,
)

router = APIRouter()


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "swiftletcare-backend",
    }


@router.get("/mqtt/status")
def mqtt_status(request: Request):
    client = getattr(request.app.state, "mqtt_client", None)

    if client is None:
        return {
            "connected": False,
            "message": "MQTT client not initialized",
        }

    connected = client.is_connected()

    return {
        "connected": connected,
        "message": (
            "Connected to MQTT broker"
            if connected
            else "Not connected to MQTT broker"
        ),
    }


@router.websocket("/ws/telemetry")
async def telemetry_websocket(websocket: WebSocket):
    await websocket.accept()

    try:
        auth_message = await asyncio.wait_for(
            websocket.receive_json(),
            timeout=5.0,
        )
        authorization = (
            auth_message.get("authorization")
            if isinstance(auth_message, dict)
            and auth_message.get("type") == "auth"
            else None
        )
        if not isinstance(authorization, str) or not authorization.startswith(
            "Bearer ",
        ):
            await websocket.close(code=4401, reason="Authentication required")
            return

        try:
            allowed_node_ids = await asyncio.to_thread(
                get_monitorable_device_node_ids,
                authorization,
            )
        except HTTPException as exc:
            close_code = {
                401: 4401,
                403: 4403,
            }.get(exc.status_code, 4503)
            await websocket.close(
                code=close_code,
                reason=str(exc.detail),
            )
            return

        await realtime_manager.register(websocket, allowed_node_ids)
        await websocket.send_json({"type": "authorized"})

        while True:
            await websocket.receive_text()
    except asyncio.TimeoutError:
        await websocket.close(code=4401, reason="Authentication required")
    except json.JSONDecodeError:
        await websocket.close(code=1003, reason="Invalid authentication message")
    except WebSocketDisconnect:
        pass
    finally:
        await realtime_manager.disconnect(websocket)
