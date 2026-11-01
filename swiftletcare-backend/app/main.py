
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config.settings import settings
from app.mqtt.client import start_mqtt
from app.services.rabbitmq_publisher import RabbitMQEventPublisher
from app.routes.control_router import router as control_router
from app.routes.management_gateway_router import router as management_gateway_router
from app.routes.system_router import router as system_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.event_loop = asyncio.get_running_loop()

    event_publisher = None
    if settings.rabbitmq_url:
        event_publisher = RabbitMQEventPublisher(
            settings.rabbitmq_url,
            settings.event_exchange,
        )
    else:
        logger.warning(
            "RabbitMQ is not configured; device ACK notifications are disabled"
        )

    mqtt_client = start_mqtt(app.state.event_loop, event_publisher)
    app.state.mqtt_client = mqtt_client

    try:
        yield
    finally:
        mqtt_client.disconnect()
        mqtt_client.loop_stop()
        if event_publisher:
            await event_publisher.close()

app = FastAPI(
    title="SwiftletCare Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(control_router)
app.include_router(management_gateway_router)
app.include_router(system_router)
