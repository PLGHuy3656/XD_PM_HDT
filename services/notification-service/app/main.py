import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.consumer import consume_events
from app.routes import router, websocket_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    consumer_task = None
    if settings.rabbitmq_url:
        consumer_task = asyncio.create_task(
            consume_events(
                settings.rabbitmq_url,
                settings.event_exchange,
                settings.notification_queue,
            )
        )
    else:
        logger.warning(
            "RabbitMQ is not configured; notification consumer is disabled"
        )

    try:
        yield
    finally:
        if consumer_task:
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title="SwiftletCare Notification Service",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)
app.include_router(websocket_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "notification-service"}
