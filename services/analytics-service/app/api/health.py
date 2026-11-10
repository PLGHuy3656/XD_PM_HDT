"""
Health check route.
"""
from fastapi import APIRouter
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health endpoint returning service status."""
    return HealthResponse(status="ok", service="analytics-service", version="0.1.0")
