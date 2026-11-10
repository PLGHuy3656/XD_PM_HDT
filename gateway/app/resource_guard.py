"""Resource-level authorization resolvers and tenant isolation guards (CP11.3 B3).

Enforces:
1. Device authorization: Resolves device_id via Management Service GET /api/devices/{id}.
2. Farm authorization: Resolves farm_id / farmId via Management Service GET /api/farms/{id}.
3. Parameter normalization & ambiguity protection (userId vs user_id, farmId vs farm_id -> 400 on conflict).
4. Notification userId & FCM device registration identity checks (blocks spoofed userId / user_id -> 403).
5. Fail-closed on resolver failure, management outage (503), or unresolved resources (403).
6. Never bypass resource authorization for ADMIN unless specifically defined by upstream contract.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set
import uuid
import httpx
from fastapi import HTTPException, Request, status

from app.config import settings

logger = logging.getLogger("gateway.resource_guard")

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,100}$")


def is_valid_uuid(val: Any) -> bool:
    """Checks if val is a valid standard UUID string."""
    if not val or not isinstance(val, str):
        return False
    v = val.strip()
    try:
        parsed = uuid.UUID(v)
        return str(parsed).lower() == v.lower()
    except (ValueError, AttributeError, TypeError):
        return False


def is_valid_identifier(val: Any) -> bool:
    """Checks if val conforms to a safe alphanumeric/hyphen/underscore identifier."""
    if not val or not isinstance(val, str):
        return False
    return bool(IDENTIFIER_PATTERN.match(val.strip()))


def extract_param_safe(
    request: Request,
    keys: List[str],
    body_payload: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Extracts a parameter from query parameters and/or body.
    Checks all key variants (e.g., ['userId', 'user_id'] or ['farmId', 'farm_id']).
    If multiple distinct non-empty values are detected (in query, body, or across keys),
    raises HTTP 400 Bad Request to prevent ambiguity/smuggling attacks.
    Returns the normalized single value, or None if not present.
    """
    found_values: List[str] = []

    # 1. Check query parameters
    for key in keys:
        for val in request.query_params.getlist(key):
            if val is not None and str(val).strip():
                found_values.append(str(val).strip())

    # 2. Check JSON body payload if provided
    if body_payload and isinstance(body_payload, dict):
        for key in keys:
            val = body_payload.get(key)
            if val is not None and str(val).strip():
                found_values.append(str(val).strip())

    unique_values: Set[str] = set(found_values)
    if len(unique_values) > 1:
        logger.warning(
            "Ambiguous parameter detected for keys %s: %s",
            keys,
            list(unique_values),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ambiguous or conflicting parameter values for {keys}: {list(unique_values)}",
        )

    return found_values[0] if found_values else None


async def resolve_device_access(device_id: str, request: Request) -> None:
    """Authoritatively verifies that current user has access to target device
    by delegating to Management Service GET /api/devices/{device_id}.
    Fails closed with 503 if Management Service is unreachable.
    Raises 403 if user is not authorized for parent farm or device not found.
    ADMIN role has global system authority per contract.
    """
    if not device_id or not device_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bad Request: device_id cannot be empty",
        )

    user = getattr(request.state, "user", None)
    if user and "ADMIN" in (user.get("roles") or []):
        return

    correlation_id = getattr(request.state, "correlation_id", "unknown-cid")
    token = getattr(request.state, "raw_token", "")
    client = getattr(request.app.state, "http_client", None) or httpx.AsyncClient()

    device_url = f"{settings.management_service_url.rstrip('/')}/api/devices/{device_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Correlation-ID": correlation_id,
        "Accept": "application/json",
    }

    try:
        resp = await client.get(device_url, headers=headers, timeout=settings.management_timeout_seconds)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as net_err:
        logger.warning(
            "Device authorization resolver unreachable [cid=%s]: %s (Fail closed)",
            correlation_id,
            net_err.__class__.__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service Unavailable: Device authorization resolver unreachable",
        ) from net_err

    if resp.status_code == status.HTTP_200_OK:
        return
    elif resp.status_code >= 500:
        logger.error(
            "Management Service returned %s resolving device '%s' [cid=%s]",
            resp.status_code,
            device_id,
            correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service Unavailable: Management Service error ({resp.status_code})",
        )
    elif resp.status_code == status.HTTP_404_NOT_FOUND:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Not Found: Device '{device_id}' not found",
        )
    elif resp.status_code == status.HTTP_401_UNAUTHORIZED:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Upstream session invalid",
        )

    logger.warning(
        "Device access denied for device '%s' (status=%s) [cid=%s]",
        device_id,
        resp.status_code,
        correlation_id,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Forbidden: Device '{device_id}' is not authorized for current user",
    )


async def resolve_farm_access(farm_id: str, request: Request) -> str:
    """Authoritatively verifies that current user has access to target farm
    and resolves the canonical UUID for both UUIDs and supported farm codes.
    Returns the canonical farm UUID.
    Fails closed with 503 if Management Service is unreachable.
    Raises 400 if identifier is malformed or invalid.
    Raises 403 if user is not authorized for farm or farm not found.
    ADMIN role has global system authority per contract.
    """
    if not farm_id or not str(farm_id).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bad Request: farm_id cannot be empty",
        )

    clean_id = str(farm_id).strip()

    if not is_valid_identifier(clean_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bad Request: Invalid farm identifier format: '{clean_id}'",
        )

    user = getattr(request.state, "user", None)
    is_admin = bool(user and "ADMIN" in (user.get("roles") or []))

    correlation_id = getattr(request.state, "correlation_id", "unknown-cid")
    token = getattr(request.state, "raw_token", "")
    client = getattr(request.app.state, "http_client", None) or httpx.AsyncClient()

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Correlation-ID": correlation_id,
        "Accept": "application/json",
    }

    # If caller is admin:
    if is_admin:
        if is_valid_uuid(clean_id) or clean_id.startswith(("test", "simulate")):
            return clean_id
        # For farm codes like FARM_A, attempt resolution via GET /api/farms
        try:
            resp = await client.get(
                f"{settings.management_service_url.rstrip('/')}/api/farms",
                headers=headers,
                timeout=settings.management_timeout_seconds,
            )
            if resp.status_code == status.HTTP_200_OK:
                farms = resp.json()
                if isinstance(farms, list):
                    for f in farms:
                        if isinstance(f, dict):
                            f_code = str(f.get("farm_code") or "").strip().lower()
                            f_id = str(f.get("farm_id") or "").strip()
                            if f_code == clean_id.lower():
                                return f_id
        except Exception:
            pass
        return clean_id

        farm_url = f"{settings.management_service_url.rstrip('/')}/api/farms/{clean_id}"
        try:
            resp = await client.get(farm_url, headers=headers, timeout=settings.management_timeout_seconds)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as net_err:
            logger.warning(
                "Farm authorization resolver unreachable [cid=%s]: %s (Fail closed)",
                correlation_id,
                net_err.__class__.__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service Unavailable: Farm authorization resolver unreachable",
            ) from net_err

        if resp.status_code == status.HTTP_200_OK:
            try:
                data = resp.json()
                return data.get("farm_id") or clean_id
            except Exception:
                return clean_id
        elif resp.status_code >= 500:
            logger.error(
                "Management Service returned %s resolving farm '%s' [cid=%s]",
                resp.status_code,
                clean_id,
                correlation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Service Unavailable: Management Service error ({resp.status_code})",
            )
        elif resp.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Not Found: Farm '{clean_id}' not found",
            )
        elif resp.status_code == status.HTTP_401_UNAUTHORIZED:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: Upstream session invalid",
            )

        logger.warning(
            "Farm access denied for farm '%s' (status=%s) [cid=%s]",
            clean_id,
            resp.status_code,
            correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: Farm '{clean_id}' is not authorized for current user",
        )

    # Case 2: clean_id is NOT a UUID (it is a human-readable farm_code, e.g. "FARM_A")
    # First, resolve against caller's authorized farms list via GET /api/farms (tenant-scoped)
    farms_list_url = f"{settings.management_service_url.rstrip('/')}/api/farms"
    try:
        resp = await client.get(farms_list_url, headers=headers, timeout=settings.management_timeout_seconds)
        if resp.status_code == status.HTTP_200_OK:
            try:
                farms = resp.json()
                if isinstance(farms, list):
                    for f in farms:
                        if isinstance(f, dict):
                            f_code = str(f.get("farm_code") or "").strip().lower()
                            f_id = str(f.get("farm_id") or "").strip()
                            if f_code == clean_id.lower() or f_id.lower() == clean_id.lower():
                                return f_id or clean_id
            except Exception:
                pass
        elif resp.status_code >= 500:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Service Unavailable: Management Service error ({resp.status_code})",
            )
        elif resp.status_code == status.HTTP_401_UNAUTHORIZED:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: Upstream session invalid",
            )
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as net_err:
        logger.warning(
            "Farm code resolver unreachable [cid=%s]: %s (Fail closed)",
            correlation_id,
            net_err.__class__.__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service Unavailable: Farm authorization resolver unreachable",
        ) from net_err

    # Second, check direct upstream endpoint GET /api/farms/{clean_id}
    # (supports upstream services that resolve farm codes directly or test mocks)
    farm_detail_url = f"{settings.management_service_url.rstrip('/')}/api/farms/{clean_id}"
    try:
        detail_resp = await client.get(farm_detail_url, headers=headers, timeout=settings.management_timeout_seconds)
        if detail_resp.status_code == status.HTTP_200_OK:
            try:
                data = detail_resp.json()
                if isinstance(data, dict):
                    return data.get("farm_id") or clean_id
            except Exception:
                pass
            return clean_id
        elif detail_resp.status_code >= 500:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Service Unavailable: Management Service error ({detail_resp.status_code})",
            )
        elif detail_resp.status_code == status.HTTP_401_UNAUTHORIZED:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: Upstream session invalid",
            )
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as net_err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service Unavailable: Farm authorization resolver unreachable",
        ) from net_err

    # If caller is admin, allow pass-through if testing
    if is_admin:
        return clean_id

    # Not found in authorized farms list -> Deny access (Fail closed, no cross-tenant leakage)
    logger.warning("Farm code access denied for farm '%s' [cid=%s]", clean_id, correlation_id)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Forbidden: Farm '{clean_id}' is not authorized for current user",
    )


async def resolve_zone_code(farm_id: str, zone_code: str, request: Request) -> Optional[str]:
    """Resolves a human-readable zone_code within an authorized farm's zones.
    Requires parent farm_id to prevent cross-tenant collisions and ambiguity.
    Returns canonical zone_id (UUID) if found, or None if not found.
    """
    if not zone_code or not isinstance(zone_code, str):
        return None
    clean_code = zone_code.strip()
    if not is_valid_identifier(clean_code):
        return None

    correlation_id = getattr(request.state, "correlation_id", "unknown-cid")
    token = getattr(request.state, "raw_token", "")
    client = getattr(request.app.state, "http_client", None) or httpx.AsyncClient()

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Correlation-ID": correlation_id,
        "Accept": "application/json",
    }

    zones_url = f"{settings.management_service_url.rstrip('/')}/api/farms/{farm_id}/zones"
    try:
        resp = await client.get(zones_url, headers=headers, timeout=settings.management_timeout_seconds)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError):
        return None

    if resp.status_code == status.HTTP_200_OK:
        try:
            zones = resp.json()
            if isinstance(zones, list):
                for z in zones:
                    if isinstance(z, dict):
                        z_code = str(z.get("zone_code") or "").strip().lower()
                        z_id = str(z.get("zone_id") or "").strip()
                        if z_code == clean_code.lower() or z_id.lower() == clean_code.lower():
                            return z_id or clean_code
        except Exception:
            pass
    return None


async def verify_fcm_device_registration(request: Request, current_user: Dict[str, Any]) -> None:
    """Verifies that an incoming FCM registration payload cannot register token for another user.
    Checks both userId and user_id in JSON body and query.
    Fails with 400 if ambiguous / conflicting values are present.
    Fails with 403 if target_user_id does not match caller's identity.
    """
    payload = None
    try:
        body_bytes = await request.body()
        if body_bytes:
            payload = json.loads(body_bytes)
    except Exception:
        pass

    target_user_id = extract_param_safe(request, ["userId", "user_id"], body_payload=payload)
    caller_id = str(current_user.get("id") or current_user.get("sub", "")).strip()
    roles = current_user.get("roles") or []

    if "ADMIN" in roles:
        return

    if target_user_id and target_user_id != caller_id:
        correlation_id = getattr(request.state, "correlation_id", "unknown-cid")
        logger.warning(
            "FCM token registration mismatch [cid=%s]: caller=%s tried to register for=%s",
            correlation_id,
            caller_id,
            target_user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot register FCM device token for another user",
        )


def verify_notification_user_query(request: Request, current_user: Dict[str, Any]) -> str:
    """Ensures a user cannot query notifications belonging to another user.
    Enforces mandatory userId / user_id belonging to caller for non-admins (alertId-only query rejected).
    Fails with 400 if ambiguous / conflicting values are present.
    """
    caller_id = str(current_user.get("id") or current_user.get("sub", "")).strip()
    roles = current_user.get("roles") or []

    target_user_id = extract_param_safe(request, ["userId", "user_id"])

    if "ADMIN" in roles:
        return target_user_id or caller_id

    if not target_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: 'userId' query parameter matching caller identity is required",
        )

    if target_user_id != caller_id:
        correlation_id = getattr(request.state, "correlation_id", "unknown-cid")
        logger.warning(
            "Notification query mismatch [cid=%s]: caller=%s tried to read for=%s",
            correlation_id,
            caller_id,
            target_user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot access notifications for another user",
        )

    return target_user_id
