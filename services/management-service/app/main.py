import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import events
from app.migrations import apply_additive_migrations

from app.routes.auth_routes import router as auth_router
from app.routes.device_routes import camera_router, router as device_router
from app.routes.farm_routes import router as farm_router
from app.routes.inspection_routes import router as inspection_router
from app.routes.internal_routes import router as internal_router
from app.routes.technician_routes import router as technician_router
from app.routes.user_routes import router as user_router
from app.routes.zone_routes import router as zone_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        apply_additive_migrations()
    except Exception:
        # Never block startup on the additive migration; endpoints that need the new tables fail closed.
        logger.exception("Additive migration failed")
    events.start_dispatcher()
    yield
    events.stop_dispatcher()


app = FastAPI(
    lifespan=lifespan,
    title="SwiftletCare Management Service",
    description="Microservice responsible for Farm, Zone, Device Registry, Technician management, and Authentication/RBAC.",
    version="0.3.5",
)

# Authentication Router
app.include_router(auth_router)

# Management Domain Routers
app.include_router(farm_router)
app.include_router(zone_router)
app.include_router(device_router)
app.include_router(camera_router)
app.include_router(technician_router)
app.include_router(user_router)
app.include_router(inspection_router)

# Internal Service-to-Service Router (CP11.4-B1-R2-MGMT)
app.include_router(internal_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "management-service",
        "version": "0.3.5",
    }
