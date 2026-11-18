import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.alerting import run_analytics_monitor
from app.config import settings
from app.routes import ai_router, router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    monitor_task = None
    if settings.database_url and settings.analytics_service_token:
        monitor_task = asyncio.create_task(
            run_analytics_monitor(
                settings.rabbitmq_url,
                settings.event_exchange,
            ),
            name="analytics-monitor",
        )
    else:
        logger.warning(
            "Analytics monitoring is disabled; configure DATABASE_URL and "
            "ANALYTICS_SERVICE_TOKEN to enable it"
        )

    try:
        yield
    finally:
        if monitor_task is not None:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title="SwiftletCare Analytics Service",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)
app.include_router(ai_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "analytics-service"}
