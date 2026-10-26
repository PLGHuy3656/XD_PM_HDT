"""Routes package for Management Service."""
from app.routes.auth_routes import router as auth_router
from app.routes.device_routes import router as device_router
from app.routes.farm_routes import router as farm_router
from app.routes.technician_routes import router as technician_router
from app.routes.zone_routes import router as zone_router

__all__ = [
    "auth_router",
    "device_router",
    "farm_router",
    "technician_router",
    "zone_router",
]
