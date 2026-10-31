
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.mqtt.client import start_mqtt
from app.routes.control_router import router as control_router
from app.routes.system_router import router as system_router


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
app.include_router(system_router)
