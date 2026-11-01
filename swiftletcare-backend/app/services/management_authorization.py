import httpx
from fastapi import HTTPException, status
from urllib.parse import quote

from app.config.settings import settings


def _require_device_permission(
    device_id: str,
    authorization: str,
    permission: str,
) -> None:
    url = (
        f"{settings.management_service_url.rstrip('/')}"
        f"/internal/authorization/devices/{quote(device_id, safe='')}/{permission}"
    )

    try:
        response = httpx.post(
            url,
            headers={"Authorization": authorization},
            timeout=5.0,
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authorization service unavailable",
        ) from exc

    if response.status_code == status.HTTP_401_UNAUTHORIZED:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    if response.status_code == status.HTTP_403_FORBIDDEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{permission.upper()} permission required",
        )

    if response.status_code == status.HTTP_404_NOT_FOUND:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not verify device permission",
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invalid authorization service response",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invalid authorization service response",
        )

    allowed = payload.get("allowed") is True
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{permission.upper()} permission required",
        )


def require_device_operate_permission(
    device_id: str,
    authorization: str,
) -> None:
    _require_device_permission(device_id, authorization, "operate")


def require_device_monitor_permission(
    device_id: str,
    authorization: str,
) -> None:
    _require_device_permission(device_id, authorization, "monitor")


def get_monitorable_device_node_ids(authorization: str) -> set[str]:
    try:
        response = httpx.get(
            f"{settings.management_service_url.rstrip('/')}/api/devices",
            headers={"Authorization": authorization},
            timeout=5.0,
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authorization service unavailable",
        ) from exc

    if response.status_code == status.HTTP_401_UNAUTHORIZED:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    if response.status_code == status.HTTP_403_FORBIDDEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device access forbidden",
        )
    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not verify device access",
        )

    try:
        devices = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invalid authorization service response",
        ) from exc

    if not isinstance(devices, list) or any(
        not isinstance(device, dict)
        or not isinstance(device.get("node_id"), str)
        or not device["node_id"]
        for device in devices
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invalid authorization service response",
        )

    return {device["node_id"] for device in devices}