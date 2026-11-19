"""User device registration and push token management endpoints (CP6.3)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, Optional
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import DevicePlatform
from app.dependencies import get_notification_service, get_user_device_repo
from app.errors import DEVICE_NOT_FOUND, raise_notification_error
from app.ports.user_device_repository import UserDeviceRepository
from app.schemas.canonical import UserDevice
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


class RegisterDeviceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    user_id: str = Field(..., alias="userId", description="Owner user identifier")
    token: str = Field(..., alias="token", description="Unique push token (FCM/APNS)")
    platform: DevicePlatform = Field(..., description="Target platform (WEB, ANDROID, IOS)")
    device_name: Optional[str] = Field(
        None,
        alias="deviceName",
        description="Optional user-facing device nickname",
    )


@router.post("", response_model=UserDevice, status_code=status.HTTP_201_CREATED)
def register_device(
    req: RegisterDeviceRequest,
    service: NotificationService = Depends(get_notification_service),
    repo: UserDeviceRepository = Depends(get_user_device_repo),
) -> UserDevice:
    """Register or refresh a push notification token for a user device.

    Enforces global token uniqueness:
    - Same user + same token -> idempotent refresh.
    - Token moves from user A to user B -> ownership reassigned to user B.
    - Multiple devices per user supported.
    """
    now = datetime.now(timezone.utc)
    existing_by_token = repo.get_by_token(req.token)

    device_id = existing_by_token.device_id if existing_by_token else f"dev_{uuid.uuid4().hex[:12]}"

    device = UserDevice(
        device_id=device_id,
        user_id=req.user_id,
        fcm_token=req.token,
        platform=req.platform,
        device_name=req.device_name,
        is_enabled=True,
        created_at=existing_by_token.created_at if existing_by_token else now,
        updated_at=now,
    )
    return service.register_device(device)


@router.delete("/{deviceRegistrationId}", response_model=Dict[str, str])
def delete_device(
    deviceRegistrationId: str,
    service: NotificationService = Depends(get_notification_service),
    repo: UserDeviceRepository = Depends(get_user_device_repo),
) -> Dict[str, str]:
    """Disable a registered push device token.

    Note on local prototype semantics:
    Performs soft disable (`isEnabled=False`) in accordance with CP6.2 repository semantics.
    """
    existing = repo.get_by_id(deviceRegistrationId)
    if existing is None:
        raise_notification_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code=DEVICE_NOT_FOUND,
            message=f"Device registration '{deviceRegistrationId}' was not found.",
        )

    service.disable_device(deviceRegistrationId)
    return {
        "status": "disabled",
        "deviceId": deviceRegistrationId,
    }


__all__ = ["router"]
