"""Health check endpoint for Notification Service (CP6.3 / CP6.4)."""
from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter

from app.infrastructure.firebase.config import FCMSettings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Dict[str, Any])
def get_health() -> Dict[str, Any]:
    """Return operational service health status with non-sensitive FCM config."""
    try:
        settings = FCMSettings.from_env()
        fcm_info = {
            "provider": settings.provider.value,
            "enabled": settings.enabled,
        }
    except Exception:
        fcm_info = {
            "provider": "unknown",
            "enabled": False,
        }

    return {
        "service": "notification-service",
        "status": "ok",
        "fcm": fcm_info,
    }
