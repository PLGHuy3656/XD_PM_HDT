"""Alert management REST endpoints (CP6.3)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import AlertEventType, AlertSeverity, AlertSource, AlertStatus
from app.dependencies import get_notification_service
from app.errors import (
    ALERT_INVALID_TRANSITION,
    ALERT_NOT_FOUND,
    raise_notification_error,
)
from app.schemas.canonical import Alert
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


class AcknowledgeAlertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    actor_id: str = Field(..., alias="actorId", description="User or operator identifier acknowledging the alert")


class ResolveAlertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    actor_id: str = Field(..., alias="actorId", description="User or operator identifier resolving the alert")
    resolution_note: Optional[str] = Field(
        None,
        alias="resolutionNote",
        description="Optional operational notes regarding the resolution",
    )


class AlertMetadataResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    alert_id: str = Field(..., alias="alertId", description="Unique alert identifier")
    farm_id: str = Field(..., alias="farmId", description="Target farm identifier")
    status: AlertStatus = Field(..., description="Lifecycle status")
    severity: AlertSeverity = Field(..., description="Canonical severity tier")
    event_type: AlertEventType = Field(..., alias="eventType", description="Condition type")
    device_id: Optional[str] = Field(default=None, alias="deviceId")
    camera_id: Optional[str] = Field(default=None, alias="cameraId")


@router.get("", response_model=List[Alert])
def list_alerts(
    status: Optional[AlertStatus] = None,
    severity: Optional[AlertSeverity] = None,
    source: Optional[AlertSource] = None,
    event_type: Optional[AlertEventType] = Query(None, alias="eventType"),
    farm_id: Optional[str] = Query(None, alias="farmId"),
    zone_id: Optional[str] = Query(None, alias="zoneId"),
    start_time: Optional[datetime] = Query(None, alias="startTime"),
    end_time: Optional[datetime] = Query(None, alias="endTime"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: NotificationService = Depends(get_notification_service),
) -> List[Alert]:
    """List alerts matching filter criteria ordered by createdAt descending."""
    return service.list_alerts(
        farm_id=farm_id,
        zone_id=zone_id,
        status=status,
        severity=severity,
        event_type=event_type,
        source=source,
        limit=limit,
        offset=offset,
        start_time=start_time,
        end_time=end_time,
    )


@router.get("/{alertId}", response_model=Alert)
def get_alert_detail(
    alertId: str,
    service: NotificationService = Depends(get_notification_service),
) -> Alert:
    """Retrieve full detail for a specific alert."""
    alert = service.get_alert(alertId)
    if alert is None:
        raise_notification_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ALERT_NOT_FOUND,
            message=f"Alert '{alertId}' was not found.",
        )
    return alert


@router.get("/{alertId}/metadata", response_model=AlertMetadataResponse)
def get_alert_metadata(
    alertId: str,
    service: NotificationService = Depends(get_notification_service),
) -> AlertMetadataResponse:
    """Internal lightweight metadata lookup for authorization guards (NB-3)."""
    alert = service.get_alert(alertId)
    if alert is None:
        raise_notification_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ALERT_NOT_FOUND,
            message=f"Alert '{alertId}' was not found.",
        )
    return AlertMetadataResponse(
        alertId=alert.alert_id,
        farmId=alert.farm_id,
        status=alert.status,
        severity=alert.severity,
        eventType=alert.event_type,
        deviceId=alert.device_id,
        cameraId=alert.camera_id,
    )


@router.post("/{alertId}/acknowledge", response_model=Alert)
def acknowledge_alert(
    alertId: str,
    req: AcknowledgeAlertRequest,
    service: NotificationService = Depends(get_notification_service),
) -> Alert:
    """Acknowledge an active OPEN alert."""
    try:
        return service.acknowledge_alert(
            alert_id=alertId,
            acknowledged_by=req.actor_id,
        )
    except KeyError:
        raise_notification_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ALERT_NOT_FOUND,
            message=f"Alert '{alertId}' was not found.",
        )
    except ValueError as exc:
        raise_notification_error(
            status_code=status.HTTP_409_CONFLICT,
            code=ALERT_INVALID_TRANSITION,
            message=str(exc),
        )


@router.post("/{alertId}/resolve", response_model=Alert)
def resolve_alert(
    alertId: str,
    req: ResolveAlertRequest,
    service: NotificationService = Depends(get_notification_service),
) -> Alert:
    """Resolve an OPEN or ACKNOWLEDGED alert."""
    try:
        return service.resolve_alert(
            alert_id=alertId,
            resolved_by=req.actor_id,
            resolution_note=req.resolution_note,
        )
    except KeyError:
        raise_notification_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ALERT_NOT_FOUND,
            message=f"Alert '{alertId}' was not found.",
        )
    except ValueError as exc:
        raise_notification_error(
            status_code=status.HTTP_409_CONFLICT,
            code=ALERT_INVALID_TRANSITION,
            message=str(exc),
        )


__all__ = ["router"]
