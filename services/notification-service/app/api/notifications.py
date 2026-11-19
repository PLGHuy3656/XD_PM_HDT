"""Notification REST endpoints for user inbox and read state (CP6.3)."""
from __future__ import annotations

from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.dependencies import get_notification_repo, get_notification_service
from app.errors import (
    NOTIFICATION_ACCESS_DENIED,
    NOTIFICATION_NOT_FOUND,
    raise_notification_error,
)
from app.ports.notification_repository import NotificationRepository
from app.schemas.canonical import Notification
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


class ReadNotificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    user_id: Optional[str] = Field(
        None,
        alias="userId",
        description="Local prototype user identity. In production, derived from auth token.",
    )


class MarkAllReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    user_id: str = Field(
        ...,
        alias="userId",
        description="Target user identity whose unread notifications will be marked as read",
    )


@router.get("", response_model=List[Notification])
def list_notifications(
    user_id: Optional[str] = Query(
        None,
        alias="userId",
        description="User ID (required unless alertId is provided)",
    ),
    alert_id: Optional[str] = Query(None, alias="alertId"),
    is_read: Optional[bool] = Query(None, alias="isRead"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: NotificationService = Depends(get_notification_service),
) -> List[Notification]:
    """List notifications for a user or alert, sorted by createdAt descending."""
    if not user_id and not alert_id:
        raise_notification_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message="Either userId or alertId is required to list notifications.",
        )
    if alert_id and not user_id:
        items = service.list_notifications_by_alert(
            alert_id=alert_id,
            limit=limit,
            offset=offset,
        )
        if is_read is True:
            items = [n for n in items if n.read_at is not None]
        elif is_read is False:
            items = [n for n in items if n.read_at is None]
        return items

    assert user_id is not None
    items = service.list_notifications(
        user_id=user_id,
        is_read=is_read,
        limit=limit,
        offset=offset,
    )
    if alert_id:
        items = [n for n in items if n.alert_id == alert_id]
    return items


@router.post("/{notificationId}/read", response_model=Notification)
def mark_notification_read(
    notificationId: str,
    req: Optional[ReadNotificationRequest] = None,
    user_id_query: Optional[str] = Query(None, alias="userId"),
    service: NotificationService = Depends(get_notification_service),
    repo: NotificationRepository = Depends(get_notification_repo),
) -> Notification:
    """Mark a notification as read.

    Local Prototype Note:
    Client supplies `userId` via JSON body or query param. Production Gateway/Auth
    will enforce authenticated identity.
    """
    effective_user_id = (req.user_id if req and req.user_id else None) or user_id_query
    if not effective_user_id:
        # If no user ID provided in local prototype, reject
        raise_notification_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message="User identity (userId) is required to mark notification as read.",
        )

    existing = repo.get_by_id(notificationId)
    if existing is None:
        raise_notification_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code=NOTIFICATION_NOT_FOUND,
            message=f"Notification '{notificationId}' was not found.",
        )

    if existing.user_id != effective_user_id:
        raise_notification_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code=NOTIFICATION_ACCESS_DENIED,
            message=f"Access denied: Notification '{notificationId}' belongs to a different user.",
        )

    updated = service.mark_notification_as_read(
        notification_id=notificationId,
        user_id=effective_user_id,
    )
    assert updated is not None
    return updated


@router.post("/read-all", response_model=Dict[str, int])
def mark_all_read(
    req: MarkAllReadRequest,
    service: NotificationService = Depends(get_notification_service),
) -> Dict[str, int]:
    """Mark all unread notifications for a user as read without mutating delivery status."""
    count = service.mark_all_notifications_as_read(user_id=req.user_id)
    return {"updatedCount": count}


__all__ = ["router"]
