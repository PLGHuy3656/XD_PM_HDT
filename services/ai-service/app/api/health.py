"""Service-level health route `/health` (CP5.3 Task 2)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    service: Literal["ai-service"] = "ai-service"
    status: Literal["ok"] = "ok"


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="AI Service health check",
)
def get_health() -> HealthResponse:
    """Return service-level liveness/health status."""
    return HealthResponse(service="ai-service", status="ok")
