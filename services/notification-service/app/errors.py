"""Consistent error contract for Alert & Notification Service V1 (CP6.3)."""
from __future__ import annotations

from typing import Any, Dict, Literal
from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

NotificationErrorCode = Literal[
    "ALERT_NOT_FOUND",
    "ALERT_INVALID_TRANSITION",
    "NOTIFICATION_NOT_FOUND",
    "NOTIFICATION_ACCESS_DENIED",
    "DEVICE_NOT_FOUND",
    "VALIDATION_ERROR",
]

ALERT_NOT_FOUND: NotificationErrorCode = "ALERT_NOT_FOUND"
ALERT_INVALID_TRANSITION: NotificationErrorCode = "ALERT_INVALID_TRANSITION"
NOTIFICATION_NOT_FOUND: NotificationErrorCode = "NOTIFICATION_NOT_FOUND"
NOTIFICATION_ACCESS_DENIED: NotificationErrorCode = "NOTIFICATION_ACCESS_DENIED"
DEVICE_NOT_FOUND: NotificationErrorCode = "DEVICE_NOT_FOUND"
VALIDATION_ERROR: NotificationErrorCode = "VALIDATION_ERROR"


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: NotificationErrorCode
    message: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detail: ErrorDetail


def raise_notification_error(
    status_code: int,
    code: NotificationErrorCode,
    message: str,
) -> None:
    """Raise an HTTPException conforming to the canonical `{detail: {code, message}}` structure."""
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Map FastAPI/Pydantic validation errors into the canonical format."""
    first_error = exc.errors()[0] if exc.errors() else {}
    msg = first_error.get("msg", "Request validation failed")
    loc = " -> ".join(str(l) for l in first_error.get("loc", []))
    full_message = f"Validation failed at '{loc}': {msg}" if loc else msg

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": {
                "code": VALIDATION_ERROR,
                "message": full_message,
            }
        },
    )


async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    """Ensure HTTP exceptions conform to `{detail: {code, message}}` structure."""
    if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    # Fallback if standard string detail was raised
    code: NotificationErrorCode = "VALIDATION_ERROR"
    if exc.status_code == 404:
        code = "ALERT_NOT_FOUND"
    elif exc.status_code == 409:
        code = "ALERT_INVALID_TRANSITION"
    elif exc.status_code == 403:
        code = "NOTIFICATION_ACCESS_DENIED"

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": {
                "code": code,
                "message": str(exc.detail),
            }
        },
    )


__all__ = [
    "NotificationErrorCode",
    "ALERT_NOT_FOUND",
    "ALERT_INVALID_TRANSITION",
    "NOTIFICATION_NOT_FOUND",
    "NOTIFICATION_ACCESS_DENIED",
    "DEVICE_NOT_FOUND",
    "VALIDATION_ERROR",
    "ErrorDetail",
    "ErrorResponse",
    "raise_notification_error",
    "validation_exception_handler",
    "http_exception_handler",
]
