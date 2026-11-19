from urllib.parse import quote
from uuid import UUID

import httpx
from fastapi import HTTPException, status

from app.config import settings


def get_monitorable_devices(
    authorization: str,
    farm_id: str | None = None,
    zone_id: str | None = None,
) -> list[dict]:
    params = {}
    if farm_id is not None:
        params["farm_id"] = farm_id
    if zone_id is not None:
        params["zone_id"] = zone_id

    try:
        response = httpx.get(
            f"{settings.management_service_url.rstrip('/')}/api/devices",
            headers={"Authorization": authorization},
            params=params,
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

    return devices


def get_authorized_farms(authorization: str) -> list[dict]:
    try:
        response = httpx.get(
            f"{settings.management_service_url.rstrip('/')}/api/farms",
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
            detail="Farm access forbidden",
        )
    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not verify farm access",
        )

    try:
        farms = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invalid authorization service response",
        ) from exc

    if not isinstance(farms, list) or any(
        not isinstance(farm, dict)
        or not isinstance(farm.get("farm_id"), str)
        or not farm["farm_id"]
        for farm in farms
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invalid authorization service response",
        )

    return farms


def get_authorized_zones(
    authorization: str,
    farm_id: str,
) -> list[dict]:
    try:
        response = httpx.get(
            (
                f"{settings.management_service_url.rstrip('/')}"
                f"/api/farms/{farm_id}/zones"
            ),
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
            detail="Farm access forbidden",
        )
    if response.status_code == status.HTTP_404_NOT_FOUND:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farm not found",
        )
    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not verify zone access",
        )

    try:
        zones = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invalid authorization service response",
        ) from exc

    if not isinstance(zones, list) or any(
        not isinstance(zone, dict)
        or not isinstance(zone.get("zone_id"), str)
        or not zone["zone_id"]
        for zone in zones
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invalid authorization service response",
        )

    return zones


def _is_valid_analytics_device_context(context: object) -> bool:
    if not isinstance(context, dict):
        return False

    required_strings = (
        "device_id",
        "node_id",
        "farm_id",
        "farm_code",
        "farm_name",
    )
    if any(
        not isinstance(context.get(field), str) or not context[field]
        for field in required_strings
    ):
        return False

    zone_id = context.get("zone_id")
    if zone_id is not None and (
        not isinstance(zone_id, str) or not zone_id
    ):
        return False
    if any(
        context.get(field) is not None
        and not isinstance(context.get(field), str)
        for field in ("zone_code", "zone_name")
    ):
        return False

    recipients = context.get("recipient_user_ids")
    if not isinstance(recipients, list) or any(
        not isinstance(user_id, str) or not user_id
        for user_id in recipients
    ):
        return False

    try:
        UUID(context["device_id"])
        UUID(context["farm_id"])
        if zone_id is not None:
            UUID(zone_id)
        for user_id in recipients:
            UUID(user_id)
    except ValueError:
        return False
    return True


def get_analytics_device_contexts() -> list[dict]:
    service_token = settings.analytics_service_token
    if not service_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analytics service authentication is not configured",
        )

    try:
        response = httpx.get(
            (
                f"{settings.management_service_url.rstrip('/')}"
                "/internal/authorization/analytics/device-contexts"
            ),
            headers={"X-Analytics-Service-Token": service_token},
            timeout=5.0,
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Management Service unavailable",
        ) from exc

    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not load Analytics device contexts",
        )

    try:
        contexts = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invalid Analytics device context response",
        ) from exc

    if not isinstance(contexts, list) or any(
        not _is_valid_analytics_device_context(context)
        for context in contexts
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invalid Analytics device context response",
        )

    return contexts


def get_analytics_device_context(node_id: str) -> dict:
    service_token = settings.analytics_service_token
    if not service_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analytics service authentication is not configured",
        )

    try:
        response = httpx.get(
            (
                f"{settings.management_service_url.rstrip('/')}"
                "/internal/authorization/analytics/device-contexts/"
                f"{quote(node_id, safe='')}"
            ),
            headers={"X-Analytics-Service-Token": service_token},
            timeout=5.0,
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Management Service unavailable",
        ) from exc

    if response.status_code == status.HTTP_404_NOT_FOUND:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown or inactive camera/node",
        )
    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not resolve camera/node context",
        )

    try:
        context = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invalid camera/node context response",
        ) from exc

    if (
        not _is_valid_analytics_device_context(context)
        or context["node_id"] != node_id
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invalid camera/node context response",
        )

    return context


def get_current_user_id(authorization: str) -> str:
    try:
        response = httpx.get(
            f"{settings.management_service_url.rstrip('/')}/api/auth/me",
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
    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not verify current user",
        )

    try:
        user = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invalid authorization service response",
        ) from exc

    if not isinstance(user, dict) or not isinstance(user.get("id"), str):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invalid authorization service response",
        )

    return user["id"]
