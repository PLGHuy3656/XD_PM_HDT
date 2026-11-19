"""Consistent API error contract for AI Service V1 (CP5.3 Task 14)."""
from __future__ import annotations

from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel

AIErrorCode = Literal[
    "CAMERA_NOT_FOUND",
    "DETECTION_NOT_AVAILABLE",
    "COUNT_NOT_AVAILABLE",
    "EVENT_NOT_FOUND",
    "SNAPSHOT_NOT_FOUND",
    "INVALID_SNAPSHOT_PATH",
]

CAMERA_NOT_FOUND: AIErrorCode = "CAMERA_NOT_FOUND"
DETECTION_NOT_AVAILABLE: AIErrorCode = "DETECTION_NOT_AVAILABLE"
COUNT_NOT_AVAILABLE: AIErrorCode = "COUNT_NOT_AVAILABLE"
EVENT_NOT_FOUND: AIErrorCode = "EVENT_NOT_FOUND"
SNAPSHOT_NOT_FOUND: AIErrorCode = "SNAPSHOT_NOT_FOUND"
INVALID_SNAPSHOT_PATH: AIErrorCode = "INVALID_SNAPSHOT_PATH"


class ErrorDetail(BaseModel):
    code: AIErrorCode
    message: str


class ErrorResponse(BaseModel):
    detail: ErrorDetail


def raise_ai_error(status_code: int, code: AIErrorCode, message: str) -> None:
    """Raise an HTTPException with the canonical `{detail: {code, message}}` payload."""
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


__all__ = [
    "AIErrorCode",
    "CAMERA_NOT_FOUND",
    "COUNT_NOT_AVAILABLE",
    "DETECTION_NOT_AVAILABLE",
    "EVENT_NOT_FOUND",
    "ErrorDetail",
    "ErrorResponse",
    "INVALID_SNAPSHOT_PATH",
    "SNAPSHOT_NOT_FOUND",
    "raise_ai_error",
]
