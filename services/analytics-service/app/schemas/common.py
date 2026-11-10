"""
Common response schemas and error envelopes for Analytics Service.
"""
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Health check payload."""
    status: str = Field(..., json_schema_extra={"example": "ok"})
    service: str = Field("analytics-service", json_schema_extra={"example": "analytics-service"})
    version: str = Field("0.1.0", json_schema_extra={"example": "0.1.0"})


class ErrorDetail(BaseModel):
    """Standard error response."""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Wrapper error envelope."""
    error: ErrorDetail
