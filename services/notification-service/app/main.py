"""FastAPI service entrypoint for Alert & Notification Service (CP6.3)."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from app.api import (
    alerts_router,
    devices_router,
    health_router,
    internal_events_router,
    notifications_router,
)
from app.dependencies import get_ws_manager
from app.errors import http_exception_handler, validation_exception_handler
from app.websocket.routes import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan attaching running event loop to WebSocket manager on startup."""
    loop = asyncio.get_running_loop()
    ws_manager = get_ws_manager()
    ws_manager.attach_loop(loop)

    from app.infrastructure.rabbitmq import RabbitMQSettings, get_rabbitmq_consumer
    rmq_settings = RabbitMQSettings.from_env()
    consumer = None
    if rmq_settings.enabled:
        consumer = get_rabbitmq_consumer()
        try:
            await consumer.start()
        except Exception as exc:
            import logging
            logging.getLogger("notification_service").error(
                "Failed to start RabbitMQ consumer on startup: %s", exc
            )

    yield

    if consumer and consumer.is_running:
        try:
            await consumer.stop()
        except Exception:
            pass

    await ws_manager.close_all()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title="SwiftletCare Alert & Notification Service",
        description=(
            "Microservice managing operational alert lifecycles, deduplication, "
            "and multi-channel notification delivery (IN_APP and FCM) for SwiftletCare."
        ),
        version="0.1.0",
        lifespan=lifespan,
        openapi_tags=[
            {"name": "health", "description": "Service health probe"},
            {"name": "alerts", "description": "Alert queries, acknowledgement, and resolution"},
            {"name": "notifications", "description": "User notification inbox and read state"},
            {"name": "devices", "description": "User device registration and push token management"},
            {"name": "websocket", "description": "Realtime WebSocket event streams"},
        ],
    )

    # Error Handlers
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)

    # API Routers
    app.include_router(health_router)
    app.include_router(alerts_router)
    app.include_router(notifications_router)
    app.include_router(devices_router)
    app.include_router(internal_events_router)
    app.include_router(ws_router)

    return app


app = create_app()


__all__ = ["app", "create_app"]
