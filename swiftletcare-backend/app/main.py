
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.telemetry import start_mqtt


@asynccontextmanager
async def lifespan(app: FastAPI):
    mqtt_client = start_mqtt()
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