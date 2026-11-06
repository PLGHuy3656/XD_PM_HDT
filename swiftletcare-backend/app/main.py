import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.mqtt.client import start_mqtt, stop_mqtt
from app.realtime.manager import realtime_manager
from app.routes.technician_routes import router as technician_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.event_loop = asyncio.get_running_loop()

    mqtt_client = start_mqtt(app.state.event_loop)
    app.state.mqtt_client = mqtt_client

    try:
        yield
    finally:
        stop_mqtt(mqtt_client)


app = FastAPI(
    title="SwiftletCare Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(technician_router)


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

    try:
        connected = client.is_connected()
    except Exception:
        connected = False

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
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass

    finally:
        await realtime_manager.disconnect(websocket)
