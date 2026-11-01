import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.routes.auth_routes import router as auth_router
from app.routes.device_routes import router as device_router
from app.routes.farm_routes import router as farm_router
from app.routes.technician_routes import router as technician_router
from app.routes.zone_routes import router as zone_router
from app.routes.authorization_routes import router as authorization_router
from app.services.event_publisher import EventOutboxPublisher

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    publisher = None
    publisher_task = None

    if settings.rabbitmq_url:
        publisher = EventOutboxPublisher(
            settings.rabbitmq_url,
            settings.event_exchange,
        )
        publisher_task = asyncio.create_task(publisher.run())
    else:
        logger.warning(
            "RabbitMQ is not configured; management events remain in the outbox"
        )

    try:
        yield
    finally:
        if publisher_task:
            publisher_task.cancel()
            try:
                await publisher_task
            except asyncio.CancelledError:
                pass
        if publisher:
            await publisher.close()

app = FastAPI(
    title="SwiftletCare Management Service",
    description="Microservice responsible for Farm, Zone, Device Registry, Technician management, and Authentication/RBAC.",
    version="0.3.5",
    lifespan=lifespan,
)

# Authentication Router
app.include_router(auth_router)

# Authorization Router
app.include_router(authorization_router)

# Management Domain Routers
app.include_router(farm_router)
app.include_router(zone_router)
app.include_router(device_router)
app.include_router(technician_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "management-service",
        "version": "0.3.5",
    }
