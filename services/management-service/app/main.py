from fastapi import FastAPI

from app.routes.device_routes import router as device_router
from app.routes.farm_routes import router as farm_router
from app.routes.technician_routes import router as technician_router
from app.routes.zone_routes import router as zone_router

# TODO(MANAGEMENT-IDENTITY):
# Legacy backend does not provide a unified User/Auth/RBAC persistence model.
# The final Management Service identity model will be designed when Management
# database ownership is introduced. Do not use frontend mock credentials as
# backend persistence.

app = FastAPI(
    title="SwiftletCare Management Service",
    description="Microservice responsible for Farm, Zone, Device Registry, and Technician management.",
    version="0.2.0",
)

# Domain Routers
app.include_router(farm_router)
app.include_router(zone_router)
app.include_router(device_router)
app.include_router(technician_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "management-service",
        "version": "0.2.0",
    }
