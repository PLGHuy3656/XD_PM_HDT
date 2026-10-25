from fastapi import FastAPI

from app.routes.technician_routes import router as technician_router


app = FastAPI(
    title="SwiftletCare Management Service",
    version="0.1.0",
)

app.include_router(technician_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "management-service",
    }
