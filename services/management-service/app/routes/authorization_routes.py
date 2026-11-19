import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.config import settings
from app.core.dependencies import (
    check_technician_permission,
    get_current_user,
    verify_farm_resource_access,
)
from app.repositories.device_repository import device_repository
from app.repositories.user_repository import user_repository

router = APIRouter(
    prefix="/internal/authorization",
    tags=["Internal Authorization"],
)


@router.get("/analytics/device-contexts")
def list_analytics_device_contexts(
    service_token: str | None = Header(
        default=None,
        alias="X-Analytics-Service-Token",
    ),
):
    expected_token = settings.analytics_service_token
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analytics service authentication is not configured",
        )
    if not service_token or not secrets.compare_digest(
        service_token,
        expected_token,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid analytics service credentials",
        )

    return device_repository.list_analytics_device_contexts()


@router.get("/analytics/device-contexts/{node_id}")
def get_analytics_device_context(
    node_id: str,
    service_token: str | None = Header(
        default=None,
        alias="X-Analytics-Service-Token",
    ),
):
    expected_token = settings.analytics_service_token
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analytics service authentication is not configured",
        )
    if not service_token or not secrets.compare_digest(
        service_token,
        expected_token,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid analytics service credentials",
        )

    contexts = device_repository.list_analytics_device_contexts(node_id)
    if not contexts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active camera/node not found",
        )
    return contexts[0]


@router.post("/devices/{device_id}/operate")
def authorize_device_operation(
    device_id: str,
    current_user: dict = Depends(get_current_user),
):
    farm_id = user_repository.get_farm_id_for_device(device_id)
    if farm_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    roles = current_user.get("roles") or []

    if "ADMIN" in roles:
        return {"allowed": True}

    if "TECHNICIAN" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OPERATE permission required",
        )

    allowed = check_technician_permission(
        str(current_user["id"]),
        farm_id,
        "OPERATE",
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OPERATE permission required",
        )

    return {"allowed": True}


@router.post("/devices/{device_id}/monitor")
def authorize_device_monitoring(
    device_id: str,
    current_user: dict = Depends(get_current_user),
):
    farm_id = user_repository.get_farm_id_for_device(device_id)
    if farm_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    verify_farm_resource_access(current_user, farm_id)
    return {"allowed": True}