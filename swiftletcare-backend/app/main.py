
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.realtime import realtime_manager
from app.telemetry import start_mqtt
from app.control_router import router as control_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.event_loop = asyncio.get_running_loop()

    mqtt_client = start_mqtt(app.state.event_loop)
    app.state.mqtt_client = mqtt_client

    try:
        yield
    finally:
        mqtt_client.disconnect()
        mqtt_client.loop_stop()

app = FastAPI(
    title="SwiftletCare Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(control_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "swiftletcare-backend",
    }


@app.get("/mqtt/status")
def mqtt_status():
    client = getattr(app.state, "mqtt_client", None)

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


@app.websocket("/ws/telemetry")
async def telemetry_websocket(websocket: WebSocket):
    await realtime_manager.connect(websocket)

    try:
        while True:
            # Giữ kết nối và nhận các thông điệp từ client nếu có.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await realtime_manager.disconnect(websocket)
