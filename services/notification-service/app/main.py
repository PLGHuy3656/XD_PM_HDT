import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.consumer import consume_events, deliver_pending_notifications
from app.routes import router, websocket_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    background_tasks = []
    if settings.rabbitmq_url and settings.database_url:
        background_tasks.append(asyncio.create_task(
            consume_events(
                settings.rabbitmq_url,
                settings.event_exchange,
                settings.notification_queue,
            )
        ))
    else:
        if not settings.rabbitmq_url:
            logger.warning(
                "RabbitMQ is not configured; notification consumer is disabled"
            )
        if not settings.database_url:
            logger.warning(
                "DATABASE_URL is not configured; notification consumer is disabled"
            )
    if settings.database_url:
        background_tasks.append(asyncio.create_task(deliver_pending_notifications()))
    else:
        logger.warning(
            "DATABASE_URL is not configured; notification delivery worker is disabled"
        )

    try:
        yield
    finally:
        for task in background_tasks:
            task.cancel()
        for task in background_tasks:
            try:
                await task
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
