from fastapi import FastAPI

from app.routes.auth_routes import router as auth_router
from app.routes.device_routes import router as device_router
from app.routes.farm_routes import router as farm_router
from app.routes.technician_routes import router as technician_router
from app.routes.zone_routes import router as zone_router

app = FastAPI(
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
app.include_router(technician_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "management-service",
        "version": "0.3.5",
    }
