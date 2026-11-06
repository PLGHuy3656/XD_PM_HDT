from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.config import settings
from app.mqtt.client import mqtt_manager
from app.routes import iot_router, ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages service lifespan: initializes background MQTT client on startup,

    gracefully stops MQTT loop on shutdown.
    """
    if settings.mqtt_auto_start:
        mqtt_manager.start()
    yield
    if settings.mqtt_auto_start:
        mqtt_manager.stop()


app = FastAPI(
    title="SwiftletCare IoT Service",
    description="Microservice responsible for MQTT lifecycle, telemetry processing, device presence, and control configuration.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(iot_router)
app.include_router(ws_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.service_name,
    }
