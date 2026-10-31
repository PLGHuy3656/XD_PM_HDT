from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from app.realtime.manager import realtime_manager

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
    await realtime_manager.connect(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await realtime_manager.disconnect(websocket)
