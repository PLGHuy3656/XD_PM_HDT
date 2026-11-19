"""Internal test harness event ingestion endpoints (CP6.3).

IMPORTANT:
These endpoints are internal test entrypoints for local end-to-end verification.
They are excluded from the public OpenAPI documentation (include_in_schema=False).
In production (CP7), they will be replaced by RabbitMQ event consumers.
"""
from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, status

from app.dependencies import get_notification_service
from app.schemas.canonical import Alert
from app.schemas.events import (
    AIAlertInputEvent,
    IoTCommandAlertInputEvent,
    IoTPresenceAlertInputEvent,
    IoTTelemetryAlertInputEvent,
)
from app.services.notification_service import NotificationService

router = APIRouter(
    prefix="/internal/v1/events",
    tags=["internal"],
    include_in_schema=False,  # Excluded from public OpenAPI docs
)


@router.post("/ai", response_model=List[Alert], status_code=status.HTTP_200_OK)
def ingest_ai_event(
    event: AIAlertInputEvent,
    service: NotificationService = Depends(get_notification_service),
) -> List[Alert]:
    """Ingest an AI predator detection event."""
    return service.handle_ai_event(event)


@router.post("/iot/telemetry", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
def ingest_telemetry_event(
    event: IoTTelemetryAlertInputEvent,
    service: NotificationService = Depends(get_notification_service),
) -> Dict[str, Any]:
    """Ingest an IoT environmental telemetry event."""
    triggered, resolved = service.handle_telemetry_event(event)
    return {
        "triggered": [a.model_dump(by_alias=True) for a in triggered],
        "resolved": [a.model_dump(by_alias=True) for a in resolved],
    }


@router.post("/iot/presence", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
def ingest_presence_event(
    event: IoTPresenceAlertInputEvent,
    service: NotificationService = Depends(get_notification_service),
) -> Dict[str, Any]:
    """Ingest an IoT device presence (ONLINE/OFFLINE) event."""
    triggered, resolved = service.handle_presence_event(event)
    return {
        "triggered": [a.model_dump(by_alias=True) for a in triggered],
        "resolved": [a.model_dump(by_alias=True) for a in resolved],
    }


@router.post("/iot/command", response_model=List[Alert], status_code=status.HTTP_200_OK)
def ingest_command_event(
    event: IoTCommandAlertInputEvent,
    service: NotificationService = Depends(get_notification_service),
) -> List[Alert]:
    """Ingest an IoT actuator command status event."""
    return service.handle_command_event(event)


__all__ = ["router"]
