"""Explicit route allowlist reverse proxy endpoints for SwiftletCare API Gateway (CP11.3 Phase B).

Enforces DEFAULT-DENY Architecture:
1. Public endpoints: GET /health and POST /api/auth/login ONLY.
2. Mandatory Bearer JWT validation & active account check for all protected endpoints.
3. Strict RBAC role enforcement (ADMIN, FARM_OWNER, TECHNICIAN).
4. Resource-level authorization:
   - Device scoping via Management GET /api/devices/{id}
   - Farm scoping via Management GET /api/farms/{id}
   - Cross-tenant device listing isolation (mandatory farm_id parameter)
   - FCM registration & notification userId identity verification (checks both userId & user_id)
   - Parameter ambiguity protection (rejects conflicting userId/user_id, farmId/farm_id with 400)
   - Fail-closed lock on unresolvable resources (alerts acknowledge/resolve, AI events, camera detail, notifications mark-as-read)
5. Explicit routes ONLY: All catch-all /{path:path} patterns are REMOVED. Any unlisted route or HTTP method fails closed with 404/405.
6. Admin exceptions apply strictly where allowed by contract; never bypass allowlist for unknown routes.
"""
from __future__ import annotations

import logging
import urllib.parse
from typing import Any, Dict, Optional
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse

from app.auth import (
    get_current_gateway_user,
    require_admin,
    require_any_authenticated,
    require_roles,
    revoke_token,
)
from app.config import settings
from app.proxy import internal_service_headers_for, proxy_handler, validate_path_security
from app.resource_guard import (
    extract_param_safe,
    is_valid_uuid,
    resolve_alert_access,
    resolve_camera_access,
    resolve_device_access,
    resolve_farm_access,
    resolve_zone_code,
    verify_fcm_device_registration,
    verify_notification_user_query,
)

logger = logging.getLogger("gateway.routes")
router = APIRouter()


def _check_path_security(request: Request, path: str = "") -> None:
    """Security filter: Blocks dangerous encodings, ambiguous delimiters (%3f, %23),
    traversal sequences, and direct client access to /internal endpoints.
    """
    validate_path_security(request, path)


# =============================================================================
# 1. Management Service Routes
# =============================================================================

# --- A. Authentication Endpoints ---

@router.post(
    "/api/auth/login",
    tags=["Management - Auth (Public)"],
    summary="Public user authentication to acquire JWT token",
)
async def proxy_auth_login(request: Request) -> Response:
    """Public login route. No JWT required."""
    _check_path_security(request, "login")
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path="/api/auth/login",
        timeout=settings.management_timeout_seconds,
    )


@router.get(
    "/api/auth/me",
    tags=["Management - Auth (Protected)"],
    summary="Get profile of currently authenticated user",
)
async def proxy_auth_me(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_gateway_user),
) -> Response:
    """Introspection endpoint for authenticated user profile."""
    _check_path_security(request, "me")
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path="/api/auth/me",
        timeout=settings.management_timeout_seconds,
    )


@router.post(
    "/api/auth/logout",
    tags=["Management - Auth (Protected)"],
    summary="Server-side logout and JWT token revocation (FR-UAM-02)",
)
async def proxy_auth_logout(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_gateway_user),
) -> JSONResponse:
    """Revokes the current JWT bearer token in Redis and invalidates session."""
    auth_header = request.headers.get("authorization", "")
    token = auth_header.split(" ", 1)[1].strip() if " " in auth_header else auth_header.strip()
    if token:
        revoke_token(token)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "ok", "message": "Successfully logged out"},
    )


# --- Users Management Endpoints (Strict Admin RBAC - FR-UAM-05) ---

@router.get(
    "/api/users",
    tags=["Management - Users (Admin Only)"],
    summary="List all users (Admin only)",
)
async def proxy_list_users(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Response:
    _check_path_security(request, "users")
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path="/api/users",
        timeout=settings.management_timeout_seconds,
    )


@router.post(
    "/api/users",
    tags=["Management - Users (Admin Only)"],
    summary="Create a new user (Admin only)",
)
async def proxy_create_user(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Response:
    _check_path_security(request, "users")
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path="/api/users",
        timeout=settings.management_timeout_seconds,
    )


@router.get(
    "/api/users/{user_id}",
    tags=["Management - Users (Admin Only)"],
    summary="Get user detail (Admin only)",
)
async def proxy_get_user(
    request: Request,
    user_id: str,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Response:
    _check_path_security(request, f"users/{user_id}")
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/users/{user_id}",
        timeout=settings.management_timeout_seconds,
    )


@router.put(
    "/api/users/{user_id}",
    tags=["Management - Users (Admin Only)"],
    summary="Update user details (Admin only)",
)
async def proxy_update_user(
    request: Request,
    user_id: str,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Response:
    _check_path_security(request, f"users/{user_id}")
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/users/{user_id}",
        timeout=settings.management_timeout_seconds,
    )


@router.patch(
    "/api/users/{user_id}/status",
    tags=["Management - Users (Admin Only)"],
    summary="Update user status (Admin only)",
)
async def proxy_update_user_status(
    request: Request,
    user_id: str,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Response:
    _check_path_security(request, f"users/{user_id}/status")
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/users/{user_id}/status",
        timeout=settings.management_timeout_seconds,
    )


@router.delete(
    "/api/users/{user_id}",
    tags=["Management - Users (Admin Only)"],
    summary="Delete user (Admin only)",
)
async def proxy_delete_user(
    request: Request,
    user_id: str,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Response:
    _check_path_security(request, f"users/{user_id}")
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/users/{user_id}",
        timeout=settings.management_timeout_seconds,
    )


# --- B. Technician Endpoints (Strict RBAC) ---

@router.post(
    "/api/technicians/{technician_id}/farms/{farm_id}/assign",
    tags=["Management - Technicians (Admin Only)"],
    summary="Assign a farm to a technician (Admin only)",
)
async def proxy_technician_assign(
    request: Request,
    technician_id: str,
    farm_id: str,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Response:
    """Assign farm to technician. Strictly requires ADMIN role."""
    path = f"{technician_id}/farms/{farm_id}/assign"
    _check_path_security(request, path)
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/technicians/{path}",
        timeout=settings.management_timeout_seconds,
    )


@router.delete(
    "/api/technicians/{technician_id}/farms/{farm_id}/assign",
    tags=["Management - Technicians (Admin Only)"],
    summary="Unassign a farm from a technician (Admin only)",
)
async def proxy_technician_unassign(
    request: Request,
    technician_id: str,
    farm_id: str,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Response:
    """Unassign farm from technician. Strictly requires ADMIN role."""
    path = f"{technician_id}/farms/{farm_id}/assign"
    _check_path_security(request, path)
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/technicians/{path}",
        timeout=settings.management_timeout_seconds,
    )


@router.get(
    "/api/technicians",
    tags=["Management - Technicians"],
    summary="List all technicians (Admin or Technician only)",
)
async def proxy_technicians_list(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "TECHNICIAN")),
) -> Response:
    """Lists technicians. Forbidden for FARM_OWNER."""
    _check_path_security(request, "")
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path="/api/technicians",
        timeout=settings.management_timeout_seconds,
    )


@router.get(
    "/api/technicians/{technician_id}",
    tags=["Management - Technicians"],
    summary="Get technician profile",
)
async def proxy_technician_profile(
    request: Request,
    technician_id: str,
    current_user: Dict[str, Any] = Depends(get_current_gateway_user),
) -> Response:
    """Access technician profile. Requires ADMIN or technician self."""
    _check_path_security(request, technician_id)

    roles = current_user.get("roles") or []
    caller_id = str(current_user.get("id") or current_user.get("sub", ""))
    if "ADMIN" not in roles and caller_id != technician_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot access another technician's profile",
        )

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/technicians/{technician_id}",
        timeout=settings.management_timeout_seconds,
    )


@router.get(
    "/api/technicians/{technician_id}/dashboard",
    tags=["Management - Technicians"],
    summary="Get technician dashboard",
)
async def proxy_technician_dashboard(
    request: Request,
    technician_id: str,
    current_user: Dict[str, Any] = Depends(get_current_gateway_user),
) -> Response:
    """Access technician dashboard. Requires ADMIN or technician self."""
    _check_path_security(request, f"{technician_id}/dashboard")

    roles = current_user.get("roles") or []
    caller_id = str(current_user.get("id") or current_user.get("sub", ""))
    if "ADMIN" not in roles and caller_id != technician_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot access another technician's dashboard",
        )

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/technicians/{technician_id}/dashboard",
        timeout=settings.management_timeout_seconds,
    )


@router.get(
    "/api/technicians/{technician_id}/farms/{farm_id}",
    tags=["Management - Technicians"],
    summary="Get technician assignment for farm",
)
async def proxy_technician_farm_assignment(
    request: Request,
    technician_id: str,
    farm_id: str,
    current_user: Dict[str, Any] = Depends(get_current_gateway_user),
) -> Response:
    """Access technician farm assignment. Requires ADMIN or technician self."""
    subpath = f"{technician_id}/farms/{farm_id}"
    _check_path_security(request, subpath)

    roles = current_user.get("roles") or []
    caller_id = str(current_user.get("id") or current_user.get("sub", ""))
    if "ADMIN" not in roles and caller_id != technician_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot access another technician's assignment",
        )

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/technicians/{subpath}",
        timeout=settings.management_timeout_seconds,
    )


@router.get(
    "/api/technicians/{technician_id}/farms",
    tags=["Management - Technicians"],
    summary="Get farms assigned to technician",
)
async def proxy_technician_farms(
    request: Request,
    technician_id: str,
    current_user: Dict[str, Any] = Depends(get_current_gateway_user),
) -> Response:
    """Access technician assigned farms. Requires ADMIN or technician self."""
    subpath = f"{technician_id}/farms"
    _check_path_security(request, subpath)

    roles = current_user.get("roles") or []
    caller_id = str(current_user.get("id") or current_user.get("sub", ""))
    if "ADMIN" not in roles and caller_id != technician_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot access another technician's farms",
        )

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/technicians/{subpath}",
        timeout=settings.management_timeout_seconds,
    )


@router.get(
    "/api/technicians/{technician_id}/farms/{farm_id}/devices",
    tags=["Management - Technicians"],
    summary="Get devices in an assigned farm for technician",
)
async def proxy_technician_farm_devices(
    request: Request,
    technician_id: str,
    farm_id: str,
    current_user: Dict[str, Any] = Depends(get_current_gateway_user),
) -> Response:
    """Access devices in an assigned farm. Requires ADMIN or technician self."""
    subpath = f"{technician_id}/farms/{farm_id}/devices"
    _check_path_security(request, subpath)

    roles = current_user.get("roles") or []
    caller_id = str(current_user.get("id") or current_user.get("sub", ""))
    if "ADMIN" not in roles and caller_id != technician_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot access another technician's farm devices",
        )

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/technicians/{subpath}",
        timeout=settings.management_timeout_seconds,
    )


@router.get(
    "/api/technicians/{technician_id}/farms/{farm_id}/devices/{device_id}",
    tags=["Management - Technicians"],
    summary="Get device detail in an assigned farm for technician",
)
async def proxy_technician_farm_device_detail(
    request: Request,
    technician_id: str,
    farm_id: str,
    device_id: str,
    current_user: Dict[str, Any] = Depends(get_current_gateway_user),
) -> Response:
    """Access device detail in an assigned farm. Requires ADMIN or technician self."""
    subpath = f"{technician_id}/farms/{farm_id}/devices/{device_id}"
    _check_path_security(request, subpath)

    roles = current_user.get("roles") or []
    caller_id = str(current_user.get("id") or current_user.get("sub", ""))
    if "ADMIN" not in roles and caller_id != technician_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot access another technician's device detail",
        )

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/technicians/{subpath}",
        timeout=settings.management_timeout_seconds,
    )


# --- C. Farm & Device Endpoints (Management Service) ---

@router.get(
    "/api/farms",
    tags=["Management - Farms"],
    summary="List accessible farms (scoped by management_db tenancy filter)",
)
async def proxy_farms_list(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "TECHNICIAN", "FARM_OWNER")),
) -> Response:
    """List farms accessible to current user."""
    _check_path_security(request, "")
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path="/api/farms",
        timeout=settings.management_timeout_seconds,
    )


@router.get(
    "/api/farms/{farm_id}",
    tags=["Management - Farms"],
    summary="Get farm details with resource authorization",
)
async def proxy_farm_detail(
    request: Request,
    farm_id: str,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "TECHNICIAN", "FARM_OWNER")),
) -> Response:
    """Get single farm details. Supports canonical UUID or authorized farm_code."""
    _check_path_security(request, farm_id)
    canonical_farm_id = await resolve_farm_access(farm_id, request)

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/farms/{canonical_farm_id}",
        timeout=settings.management_timeout_seconds,
    )


@router.get(
    "/api/farms/{farm_id}/zones",
    tags=["Management - Farms"],
    summary="List zones of a farm",
)
async def proxy_farm_zones(
    request: Request,
    farm_id: str,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "TECHNICIAN", "FARM_OWNER")),
) -> Response:
    """List zones of farm. Supports canonical UUID or authorized farm_code."""
    _check_path_security(request, f"{farm_id}/zones")
    canonical_farm_id = await resolve_farm_access(farm_id, request)

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/farms/{canonical_farm_id}/zones",
        timeout=settings.management_timeout_seconds,
    )


@router.get(
    "/api/devices",
    tags=["Management - Devices"],
    summary="List devices with mandatory farm isolation for non-admins",
)
async def proxy_devices_list(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "TECHNICIAN", "FARM_OWNER")),
) -> Response:
    """List devices. Non-admins must provide farm_id / farmId. Normalizes farm and zone identifiers."""
    _check_path_security(request, "")
    roles = current_user.get("roles") or []
    farm_id = extract_param_safe(request, ["farm_id", "farmId"])

    canonical_farm_id = None
    if farm_id:
        canonical_farm_id = await resolve_farm_access(farm_id, request)
    elif "ADMIN" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: 'farm_id' parameter required for non-admin users to prevent cross-tenant exposure",
        )

    # Validate / resolve zone_id if present
    zone_id = request.query_params.get("zone_id")
    canonical_zone_id = None
    if zone_id:
        if is_valid_uuid(zone_id):
            canonical_zone_id = zone_id.strip()
        else:
            # If not a UUID, it must be resolved via parent farm
            if canonical_farm_id:
                canonical_zone_id = await resolve_zone_code(canonical_farm_id, zone_id, request)
                if not canonical_zone_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Bad Request: Zone identifier '{zone_id}' not found in farm",
                    )
            else:
                # Rule 4: Never resolve a zone code globally when it is only unique within a farm!
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Bad Request: zone_id must be a valid UUID. Zone codes cannot be resolved globally without parent farm context.",
                )

    # Canonicalize query: ensure upstream Management receives canonical farm_id and zone_id
    query_dict = dict(request.query_params)
    query_dict.pop("farmId", None)
    if canonical_farm_id:
        query_dict["farm_id"] = canonical_farm_id
    if canonical_zone_id:
        query_dict["zone_id"] = canonical_zone_id
    canonical_qs = urllib.parse.urlencode(query_dict)

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path="/api/devices",
        timeout=settings.management_timeout_seconds,
        canonical_query=canonical_qs,
    )


@router.get(
    "/api/devices/{device_id}",
    tags=["Management - Devices"],
    summary="Get device details with authorization",
)
async def proxy_device_detail(
    request: Request,
    device_id: str,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "TECHNICIAN", "FARM_OWNER")),
) -> Response:
    """Get device details."""
    _check_path_security(request, device_id)
    await resolve_device_access(device_id, request)

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/devices/{device_id}",
        timeout=settings.management_timeout_seconds,
    )


@router.get(
    "/api/zones/{zone_id}",
    tags=["Management - Zones"],
    summary="Get zone details (UUID only)",
)
async def proxy_zone_detail(
    request: Request,
    zone_id: str,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "TECHNICIAN", "FARM_OWNER")),
) -> Response:
    """Get zone details. Requires valid UUID; bare zone codes cannot be resolved globally without parent farm context."""
    _check_path_security(request, zone_id)
    if not is_valid_uuid(zone_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bad Request: zone_id must be a valid UUID. Zone codes cannot be resolved globally without parent farm context.",
        )

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/zones/{zone_id}",
        timeout=settings.management_timeout_seconds,
    )


@router.post(
    "/api/farms",
    tags=["Management - Farms"],
    summary="Create a new farm (Admin or Farm Owner)",
)
async def proxy_farm_create(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "FARM_OWNER")),
) -> Response:
    _check_path_security(request, "")
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path="/api/farms",
        timeout=settings.management_timeout_seconds,
    )


@router.put(
    "/api/farms/{farm_id}",
    tags=["Management - Farms"],
    summary="Update farm metadata (Admin or owning Farm Owner)",
)
async def proxy_farm_update(
    request: Request,
    farm_id: str,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "FARM_OWNER")),
) -> Response:
    _check_path_security(request, farm_id)
    canonical_farm_id = await resolve_farm_access(farm_id, request)
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/farms/{canonical_farm_id}",
        timeout=settings.management_timeout_seconds,
    )


@router.delete(
    "/api/farms/{farm_id}",
    tags=["Management - Farms"],
    summary="Delete a farm (Admin only)",
)
async def proxy_farm_delete(
    request: Request,
    farm_id: str,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Response:
    _check_path_security(request, farm_id)
    canonical_farm_id = await resolve_farm_access(farm_id, request)
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/farms/{canonical_farm_id}",
        timeout=settings.management_timeout_seconds,
    )


@router.post(
    "/api/farms/{farm_id}/approve",
    tags=["Management - Farms"],
    summary="Approve a pending or rejected farm (Admin only)",
)
async def proxy_farm_approve(
    request: Request,
    farm_id: str,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Response:
    _check_path_security(request, farm_id)
    canonical_farm_id = await resolve_farm_access(farm_id, request)
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/farms/{canonical_farm_id}/approve",
        timeout=settings.management_timeout_seconds,
    )


@router.post(
    "/api/farms/{farm_id}/reject",
    tags=["Management - Farms"],
    summary="Reject a pending farm (Admin only)",
)
async def proxy_farm_reject(
    request: Request,
    farm_id: str,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Response:
    _check_path_security(request, farm_id)
    canonical_farm_id = await resolve_farm_access(farm_id, request)
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/farms/{canonical_farm_id}/reject",
        timeout=settings.management_timeout_seconds,
    )


@router.post(
    "/api/farms/{farm_id}/zones",
    tags=["Management - Zones"],
    summary="Create a zone inside an authorized farm (Admin or owning Farm Owner)",
)
async def proxy_zone_create(
    request: Request,
    farm_id: str,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "FARM_OWNER")),
) -> Response:
    _check_path_security(request, f"{farm_id}/zones")
    canonical_farm_id = await resolve_farm_access(farm_id, request)
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/farms/{canonical_farm_id}/zones",
        timeout=settings.management_timeout_seconds,
    )


@router.put(
    "/api/zones/{zone_id}",
    tags=["Management - Zones"],
    summary="Update a zone (Admin or owning Farm Owner)",
)
async def proxy_zone_update(
    request: Request,
    zone_id: str,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "FARM_OWNER")),
) -> Response:
    _check_path_security(request, zone_id)
    if not is_valid_uuid(zone_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bad Request: zone_id must be a valid UUID.",
        )
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/zones/{zone_id}",
        timeout=settings.management_timeout_seconds,
    )


@router.delete(
    "/api/zones/{zone_id}",
    tags=["Management - Zones"],
    summary="Delete a zone (Admin or owning Farm Owner)",
)
async def proxy_zone_delete(
    request: Request,
    zone_id: str,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "FARM_OWNER")),
) -> Response:
    _check_path_security(request, zone_id)
    if not is_valid_uuid(zone_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bad Request: zone_id must be a valid UUID.",
        )
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/zones/{zone_id}",
        timeout=settings.management_timeout_seconds,
    )


@router.post(
    "/api/devices",
    tags=["Management - Devices"],
    summary="Register a new device in an approved farm (Admin, owning Farm Owner, or assigned Technician)",
)
async def proxy_device_create(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "FARM_OWNER", "TECHNICIAN")),
) -> Response:
    _check_path_security(request, "")
    try:
        body_json = await request.json()
    except Exception:
        body_json = None
    if isinstance(body_json, dict) and body_json.get("farm_id"):
        await resolve_farm_access(str(body_json["farm_id"]), request)
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path="/api/devices",
        timeout=settings.management_timeout_seconds,
    )


@router.put(
    "/api/devices/{device_id}",
    tags=["Management - Devices"],
    summary="Update device metadata (Admin or owning Farm Owner)",
)
async def proxy_device_update(
    request: Request,
    device_id: str,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "FARM_OWNER")),
) -> Response:
    _check_path_security(request, device_id)
    await resolve_device_access(device_id, request)
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/devices/{device_id}",
        timeout=settings.management_timeout_seconds,
    )


@router.patch(
    "/api/devices/{device_id}/zone",
    tags=["Management - Devices"],
    summary="Update device zone assignment (Admin, owning Farm Owner, or assigned Technician)",
)
async def proxy_device_zone_update(
    request: Request,
    device_id: str,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "FARM_OWNER", "TECHNICIAN")),
) -> Response:
    _check_path_security(request, device_id)
    await resolve_device_access(device_id, request)
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/devices/{device_id}/zone",
        timeout=settings.management_timeout_seconds,
    )


@router.delete(
    "/api/devices/{device_id}",
    tags=["Management - Devices"],
    summary="Delete a device from registry (Admin or owning Farm Owner)",
)
async def proxy_device_delete(
    request: Request,
    device_id: str,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "FARM_OWNER")),
) -> Response:
    _check_path_security(request, device_id)
    await resolve_device_access(device_id, request)
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.management_service_url,
        upstream_path=f"/api/devices/{device_id}",
        timeout=settings.management_timeout_seconds,
    )


# =============================================================================
# 1b. System Status (INT01-R1) — ADMIN only, active upstream probes
# =============================================================================

_SYSTEM_SERVICES = (
    # id, display name, settings url attr, deployed attr (None = always deployed), probe path
    ("management", "Management Service", "management_service_url", None, "/health"),
    ("iot", "IoT Service", "iot_service_url", "iot_service_deployed", "/health/runtime"),
    ("ai", "AI Vision Service", "ai_service_url", "ai_service_deployed", "/health"),
    ("notification", "Notification Service", "notification_service_url", "notification_service_deployed", "/health"),
    ("analytics", "Analytics Service", "analytics_service_url", "analytics_service_deployed", "/health"),
)


async def _probe_upstream(client: httpx.AsyncClient, service_id: str, base_url: str, path: str) -> Dict[str, Any]:
    """Classifies one upstream as HEALTHY / DEGRADED / UNAVAILABLE.

    HTTP 200 alone only proves the process answers; for IoT the MQTT broker link is also checked.
    """
    import time

    url = f"{base_url.rstrip('/')}{path}"
    started = time.perf_counter()
    try:
        resp = await client.get(url, timeout=settings.system_status_probe_timeout_seconds)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
        return {"status": "UNAVAILABLE", "detail": f"unreachable ({type(exc).__name__})", "latencyMs": None}
    latency = int((time.perf_counter() - started) * 1000)
    if resp.status_code == 404 and path != "/health":
        # Older upstream without the runtime endpoint: process is up but dependencies are unverified
        try:
            legacy = await client.get(f"{base_url.rstrip('/')}/health", timeout=settings.system_status_probe_timeout_seconds)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError):
            return {"status": "UNAVAILABLE", "detail": "unreachable", "latencyMs": None}
        if legacy.status_code == 200:
            return {"status": "DEGRADED", "detail": "runtime dependency status not reported", "latencyMs": latency}
        return {"status": "UNAVAILABLE", "detail": f"HTTP {legacy.status_code}", "latencyMs": latency}
    if resp.status_code != 200:
        return {"status": "UNAVAILABLE", "detail": f"HTTP {resp.status_code}", "latencyMs": latency}
    if service_id == "iot":
        try:
            body = resp.json()
        except ValueError:
            body = {}
        mqtt_state = body.get("mqtt") if isinstance(body, dict) else None
        if mqtt_state == "connected":
            return {"status": "HEALTHY", "detail": "MQTT connected", "latencyMs": latency}
        return {"status": "DEGRADED", "detail": f"MQTT {mqtt_state or 'unknown'}", "latencyMs": latency}
    return {"status": "HEALTHY", "detail": "health check OK", "latencyMs": latency}


@router.get(
    "/api/system/status",
    tags=["System"],
    summary="Live upstream service status (Admin only)",
)
async def system_status(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> JSONResponse:
    """Statuses: HEALTHY | DEGRADED | UNAVAILABLE | NOT_DEPLOYED. Exposes no URLs or secrets."""
    import asyncio
    from datetime import datetime, timezone

    client = getattr(request.app.state, "http_client", None)
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient()
    try:
        results: list[Dict[str, Any]] = [
            {"id": "gateway", "name": "API Gateway", "deployed": True, "status": "HEALTHY",
             "detail": "serving this request", "latencyMs": 0},
        ]
        probes = []
        for sid, name, url_attr, deployed_attr, path in _SYSTEM_SERVICES:
            deployed = True if deployed_attr is None else bool(getattr(settings, deployed_attr))
            entry: Dict[str, Any] = {"id": sid, "name": name, "deployed": deployed}
            results.append(entry)
            if not deployed:
                entry.update({"status": "NOT_DEPLOYED", "detail": "not part of this deployment", "latencyMs": None})
            else:
                probes.append((entry, _probe_upstream(client, sid, getattr(settings, url_attr), path)))
        outcomes = await asyncio.gather(*(coro for _, coro in probes))
        for (entry, _), outcome in zip(probes, outcomes):
            entry.update(outcome)
    finally:
        if owns_client:
            await client.aclose()

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "environment": settings.environment,
            "checkedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "services": results,
        },
    )


# =============================================================================
# 2. IoT Service Routes (/api/iot/*)
# =============================================================================

@router.post(
    "/api/iot/devices/{device_id}/commands/relay",
    tags=["IoT - Commands"],
    summary="Send relay actuator command",
)
async def proxy_iot_relay_post(
    request: Request,
    device_id: str,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "TECHNICIAN", "FARM_OWNER")),
) -> Response:
    """Relay commands strictly require device ownership/assignment."""
    path = f"devices/{device_id}/commands/relay"
    _check_path_security(request, path)
    await resolve_device_access(device_id, request)

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.iot_service_url,
        upstream_path=f"/api/iot/{path}",
        timeout=settings.iot_timeout_seconds,
    )


@router.post(
    "/api/iot/devices/{device_id}/commands/config",
    tags=["IoT - Commands"],
    summary="Send device config command",
)
async def proxy_iot_config_post(
    request: Request,
    device_id: str,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "TECHNICIAN", "FARM_OWNER")),
) -> Response:
    """Configuration command requires device authorization."""
    path = f"devices/{device_id}/commands/config"
    _check_path_security(request, path)
    await resolve_device_access(device_id, request)

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.iot_service_url,
        upstream_path=f"/api/iot/{path}",
        timeout=settings.iot_timeout_seconds,
    )


@router.put(
    "/api/iot/devices/{device_id}/config",
    tags=["IoT - Configuration"],
    summary="Configure IoT device parameters (Blocked: Upstream IoT service uses POST /commands/config)",
)
async def proxy_iot_config_put(
    request: Request,
    device_id: str,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "TECHNICIAN", "FARM_OWNER")),
) -> Response:
    """Device configuration update requires device authorization.

    BLOCKED / NOT IMPLEMENTED UPSTREAM:
    Upstream IoT Service implements asynchronous command dispatch via POST /api/iot/devices/{device_id}/commands/config
    and does NOT expose a synchronous PUT /config endpoint.
    """
    path = f"devices/{device_id}/config"
    _check_path_security(request, path)
    await resolve_device_access(device_id, request)

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="NOT_IMPLEMENTED: Upstream IoT Service does not support synchronous PUT /config. Use POST /api/iot/devices/{device_id}/commands/config for environmental configuration.",
    )


@router.get(
    "/api/iot/devices/{device_id}/commands",
    tags=["IoT - Commands"],
    summary="List command history for a specific device",
)
async def proxy_iot_device_commands(
    request: Request,
    device_id: str,
    limit: Optional[int] = Query(None, ge=1, le=500),
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "TECHNICIAN", "FARM_OWNER")),
) -> Response:
    """Command history strictly requires device ownership/assignment."""
    path = f"devices/{device_id}/commands"
    _check_path_security(request, path)
    await resolve_device_access(device_id, request)

    canonical_qs = f"limit={limit}" if limit is not None else ""
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.iot_service_url,
        upstream_path=f"/api/iot/{path}",
        timeout=settings.iot_timeout_seconds,
        canonical_query=canonical_qs,
    )


@router.get(
    "/api/iot/commands/{command_id}",
    tags=["IoT - Commands"],
    summary="Query command lifecycle status with device ownership verification",
)
async def proxy_iot_command_status(
    request: Request,
    command_id: str,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "FARM_OWNER", "TECHNICIAN")),
) -> Response:
    """Command lifecycle state.
    - ADMIN: global access.
    - FARM_OWNER / TECHNICIAN: resolves command -> deviceId from IoT Service,
      then authoritatively verifies device ownership/assignment via Management
      (fail-closed 403 on cross-farm, 503 if Management/IoT unavailable).
    """
    path = f"commands/{command_id}"
    _check_path_security(request, path)
    roles = current_user.get("roles") or []
    if "ADMIN" in roles:
        return await proxy_handler.forward(
            request=request,
            upstream_base_url=settings.iot_service_url,
            upstream_path=f"/api/iot/{path}",
            timeout=settings.iot_timeout_seconds,
        )

    client = getattr(request.app.state, "http_client", None)
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient()
    cmd_url = f"{settings.iot_service_url.rstrip('/')}/api/iot/{path}"
    try:
        resp = await client.get(
            cmd_url,
            headers=internal_service_headers_for(settings.iot_service_url),
            timeout=settings.iot_timeout_seconds,
        )
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service Unavailable: IoT Service unreachable while verifying command ownership",
        ) from exc
    finally:
        if owns_client:
            await client.aclose()

    if resp.status_code == status.HTTP_404_NOT_FOUND:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Command '{command_id}' not found",
        )
    if resp.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service Unavailable: Could not resolve command ownership",
        )

    try:
        payload = resp.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invalid response from IoT Service",
        ) from exc

    cmd_device_id = payload.get("deviceId") if isinstance(payload, dict) else None
    if not isinstance(cmd_device_id, str) or not cmd_device_id.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Command ownership could not be resolved",
        )

    # Authoritative cross-farm / technician assignment verification via Management Service
    await resolve_device_access(cmd_device_id.strip(), request)
    return JSONResponse(status_code=status.HTTP_200_OK, content=payload)


@router.get(
    "/api/iot/devices/{device_id}/telemetry",
    tags=["IoT - Telemetry"],
    summary="Get device telemetry",
)
async def proxy_iot_device_telemetry(
    request: Request,
    device_id: str,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """Get device telemetry requires device authorization."""
    path = f"devices/{device_id}/telemetry"
    _check_path_security(request, path)
    await resolve_device_access(device_id, request)

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.iot_service_url,
        upstream_path=f"/api/iot/{path}",
        timeout=settings.iot_timeout_seconds,
    )


@router.get(
    "/api/iot/devices/{device_id}/telemetry/latest",
    tags=["IoT - Telemetry"],
    summary="Get latest device telemetry",
)
async def proxy_iot_device_telemetry_latest(
    request: Request,
    device_id: str,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """Get latest device telemetry requires device authorization."""
    path = f"devices/{device_id}/telemetry/latest"
    _check_path_security(request, path)
    await resolve_device_access(device_id, request)

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.iot_service_url,
        upstream_path=f"/api/iot/{path}",
        timeout=settings.iot_timeout_seconds,
    )


@router.get(
    "/api/iot/devices/{device_id}/presence",
    tags=["IoT - Presence"],
    summary="Get single device presence",
)
async def proxy_iot_device_presence(
    request: Request,
    device_id: str,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """Get single device presence status requires device authorization."""
    path = f"devices/{device_id}/presence"
    _check_path_security(request, path)
    await resolve_device_access(device_id, request)

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.iot_service_url,
        upstream_path=f"/api/iot/{path}",
        timeout=settings.iot_timeout_seconds,
    )


@router.get(
    "/api/iot/devices/{device_id}/presence/history",
    tags=["IoT - Presence"],
    summary="Get device presence transition history",
)
async def proxy_iot_device_presence_history(
    request: Request,
    device_id: str,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """Get durable device presence transition history. Requires device authorization."""
    path = f"devices/{device_id}/presence/history"
    _check_path_security(request, path)
    await resolve_device_access(device_id, request)

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.iot_service_url,
        upstream_path=f"/api/iot/{path}",
        timeout=settings.iot_timeout_seconds,
    )


@router.get(
    "/api/iot/devices/{device_id}/history",
    tags=["IoT - History (Legacy Alias)"],
    summary="Get device history (Legacy alias mapped to /presence/history)",
)
async def proxy_iot_device_history(
    request: Request,
    device_id: str,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """Get device history. Upstream contract maps to /presence/history (telemetry history is at /telemetry)."""
    _check_path_security(request, f"devices/{device_id}/history")
    await resolve_device_access(device_id, request)

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.iot_service_url,
        upstream_path=f"/api/iot/devices/{device_id}/presence/history",
        timeout=settings.iot_timeout_seconds,
    )


@router.get(
    "/api/iot/farms/{farm_id}/telemetry",
    tags=["IoT - Farm Telemetry"],
    summary="Get farm telemetry",
)
async def proxy_iot_farm_telemetry(
    request: Request,
    farm_id: str,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """Get farm telemetry requires farm authorization."""
    _check_path_security(request, f"farms/{farm_id}/telemetry")
    canonical_farm_id = await resolve_farm_access(farm_id, request)

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.iot_service_url,
        upstream_path=f"/api/iot/farms/{canonical_farm_id}/telemetry",
        timeout=settings.iot_timeout_seconds,
    )


@router.get(
    "/api/iot/farms/{farm_id}/telemetry/latest",
    tags=["IoT - Farm Telemetry"],
    summary="Get latest farm telemetry",
)
async def proxy_iot_farm_telemetry_latest(
    request: Request,
    farm_id: str,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """Get latest farm telemetry requires farm authorization."""
    _check_path_security(request, f"farms/{farm_id}/telemetry/latest")
    canonical_farm_id = await resolve_farm_access(farm_id, request)

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.iot_service_url,
        upstream_path=f"/api/iot/farms/{canonical_farm_id}/telemetry/latest",
        timeout=settings.iot_timeout_seconds,
    )


@router.get(
    "/api/iot/devices/presence",
    tags=["IoT - Global Presence"],
    summary="Get global device presence list (Admin only)",
)
async def proxy_iot_devices_presence_global(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Response:
    """Unscoped device presence listing is restricted to ADMIN."""
    _check_path_security(request, "devices/presence")
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.iot_service_url,
        upstream_path="/api/iot/devices/presence",
        timeout=settings.iot_timeout_seconds,
    )


# =============================================================================
# 3. AI Service Routes (/api/v1/ai/*)
# =============================================================================

@router.get(
    "/api/v1/ai/cameras",
    tags=["AI Service - Cameras (Locked for non-admin)"],
    summary="List AI cameras (Locked for non-admin pending TV2 farm-scoped filtering)",
)
async def proxy_ai_cameras(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """List AI cameras. Locked for non-admins pending TV2 farm-scoped camera filtering."""
    _check_path_security(request, "cameras")
    farm_id = extract_param_safe(request, ["farm_id", "farmId"])

    roles = current_user.get("roles") or []
    if "ADMIN" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: AI camera listing is temporarily locked for non-admins pending TV2 farm-scoped camera filtering",
        )

    canonical_qs = f"farm_id={farm_id}" if farm_id else ""

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.ai_service_url,
        upstream_path="/api/v1/ai/cameras",
        timeout=settings.ai_timeout_seconds,
        canonical_query=canonical_qs,
    )


@router.get(
    "/api/v1/ai/cameras/{camera_id}",
    tags=["AI Service - Camera Detail"],
    summary="Get single AI camera details with authorization",
)
async def proxy_ai_camera_detail(
    request: Request,
    camera_id: str,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """Camera detail endpoint with authoritative camera ownership resolution.
    Upstream contract exposes technical status at /api/v1/ai/cameras/{cameraId}/status.
    """
    _check_path_security(request, f"cameras/{camera_id}")
    canonical_camera_id = await resolve_camera_access(
        camera_id,
        request,
        locked_detail="Forbidden: AI camera detail is locked pending camera-to-farm resolver",
    )

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.ai_service_url,
        upstream_path=f"/api/v1/ai/cameras/{canonical_camera_id}/status",
        timeout=settings.ai_timeout_seconds,
    )


@router.get(
    "/api/v1/ai/cameras/{camera_id}/status",
    tags=["AI Service - Camera Detail"],
    summary="Get single AI camera status with authorization",
)
async def proxy_ai_camera_status(
    request: Request,
    camera_id: str,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """Direct status endpoint for AI camera with authoritative camera ownership resolution."""
    _check_path_security(request, f"cameras/{camera_id}/status")
    canonical_camera_id = await resolve_camera_access(
        camera_id,
        request,
        locked_detail="Forbidden: AI camera detail is locked pending camera-to-farm resolver",
    )

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.ai_service_url,
        upstream_path=f"/api/v1/ai/cameras/{canonical_camera_id}/status",
        timeout=settings.ai_timeout_seconds,
    )


@router.get(
    "/api/v1/ai/cameras/{camera_id}/counts/latest",
    tags=["AI Service - Cameras"],
    summary="Get latest canonical bird count for camera with authorization",
)
async def proxy_ai_camera_count_latest(
    request: Request,
    camera_id: str,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """Latest bird count for camera with authoritative camera ownership resolution."""
    _check_path_security(request, f"cameras/{camera_id}/counts/latest")
    canonical_camera_id = await resolve_camera_access(
        camera_id,
        request,
        locked_detail="Forbidden: AI camera counts are restricted to ADMIN pending camera-to-farm resolver",
    )

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.ai_service_url,
        upstream_path=f"/api/v1/ai/cameras/{canonical_camera_id}/counts/latest",
        timeout=settings.ai_timeout_seconds,
    )


@router.get(
    "/api/v1/ai/cameras/{camera_id}/counts",
    tags=["AI Service - Cameras"],
    summary="List historical bird count updates for camera with authorization",
)
async def proxy_ai_camera_counts(
    request: Request,
    camera_id: str,
    limit: Optional[int] = Query(None, ge=1, le=500),
    startTime: Optional[str] = Query(None),
    endTime: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """Historical count updates for camera with authoritative camera ownership resolution."""
    _check_path_security(request, f"cameras/{camera_id}/counts")
    canonical_camera_id = await resolve_camera_access(
        camera_id,
        request,
        locked_detail="Forbidden: AI camera counts are restricted to ADMIN pending camera-to-farm resolver",
    )

    # Strictly allowlist parameters and apply standard URL encoding to prevent parameter injection / malformed timestamps
    query_dict: dict[str, str] = {}
    if limit is not None:
        query_dict["limit"] = str(limit)
    if startTime:
        query_dict["startTime"] = startTime
    if endTime:
        query_dict["endTime"] = endTime
    canonical_qs = urllib.parse.urlencode(query_dict)

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.ai_service_url,
        upstream_path=f"/api/v1/ai/cameras/{canonical_camera_id}/counts",
        timeout=settings.ai_timeout_seconds,
        canonical_query=canonical_qs,
    )


@router.get(
    "/api/v1/ai/cameras/{camera_id}/detections/latest",
    tags=["AI Service - Cameras"],
    summary="Get latest canonical detection result for camera with authorization",
)
async def proxy_ai_camera_detection_latest(
    request: Request,
    camera_id: str,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """Latest detection result for camera with authoritative camera ownership resolution."""
    _check_path_security(request, f"cameras/{camera_id}/detections/latest")
    canonical_camera_id = await resolve_camera_access(
        camera_id,
        request,
        locked_detail="Forbidden: AI camera detections are restricted to ADMIN pending camera-to-farm resolver",
    )

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.ai_service_url,
        upstream_path=f"/api/v1/ai/cameras/{canonical_camera_id}/detections/latest",
        timeout=settings.ai_timeout_seconds,
    )


# -----------------------------------------------------------------------------
# INT02: interactive AI camera sessions (DEMO_VIDEO / LOCAL_CAMERA) and frame ingest
# -----------------------------------------------------------------------------
MAX_AI_FRAME_BYTES = 1_500_000


async def _resolve_camera_context(camera_id: str, request: Request) -> Dict[str, Optional[str]]:
    """Authorise the caller for the camera, then read farm/zone AUTHORITATIVELY from Management.

    The client never supplies farmId/zoneId or a media source.
    """
    canonical_camera_id = await resolve_camera_access(camera_id, request)
    client = getattr(request.app.state, "http_client", None)
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient()
    try:
        resp = await client.get(
            f"{settings.management_service_url.rstrip('/')}/api/cameras/{canonical_camera_id}",
            headers={
                "Authorization": f"Bearer {getattr(request.state, 'raw_token', '')}",
                "X-Correlation-ID": getattr(request.state, "correlation_id", "unknown-cid"),
                "Accept": "application/json",
            },
            timeout=settings.management_timeout_seconds,
        )
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service Unavailable: Management unreachable") from exc
    finally:
        if owns_client:
            await client.aclose()
    if resp.status_code != status.HTTP_200_OK:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Camera metadata could not be resolved")
    data = resp.json() if resp.content else {}
    farm_id = str(data.get("farm_id") or data.get("farmId") or "").strip() or None
    zone_id = str(data.get("zone_id") or data.get("zoneId") or "").strip() or None
    if not farm_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Camera is not bound to a farm")
    return {"cameraId": canonical_camera_id, "farmId": farm_id, "zoneId": zone_id}


async def _ai_internal_post(request: Request, path: str, json_body: Optional[Dict[str, Any]] = None) -> Response:
    from app.proxy import internal_service_headers_for

    client = getattr(request.app.state, "http_client", None)
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient()
    try:
        resp = await client.post(
            f"{settings.ai_service_url.rstrip('/')}{path}",
            json=json_body,
            headers={
                **internal_service_headers_for(settings.ai_service_url),
                "X-Correlation-ID": getattr(request.state, "correlation_id", "unknown-cid"),
            },
            timeout=settings.ai_timeout_seconds,
        )
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service Unavailable: AI Service unreachable") from exc
    finally:
        if owns_client:
            await client.aclose()
    try:
        content = resp.json()
    except ValueError:
        content = {"detail": resp.text[:200]}
    return JSONResponse(status_code=resp.status_code, content=content)


@router.post(
    "/api/v1/ai/cameras/{camera_id}/session",
    tags=["AI Service - Camera Sessions (INT02)"],
    summary="Start a DEMO_VIDEO or LOCAL_CAMERA AI session for an authorised camera",
)
async def proxy_ai_camera_session_start(
    request: Request,
    camera_id: str,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "FARM_OWNER", "TECHNICIAN")),
) -> Response:
    _check_path_security(request, f"cameras/{camera_id}/session")
    try:
        body = await request.json()
    except Exception:
        body = None
    mode = body.get("mode") if isinstance(body, dict) else None
    if mode not in ("DEMO_VIDEO", "LOCAL_CAMERA") or (isinstance(body, dict) and set(body.keys()) - {"mode"}):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Body must be exactly {\"mode\": \"DEMO_VIDEO\" | \"LOCAL_CAMERA\"}",
        )
    ctx = await _resolve_camera_context(camera_id, request)
    return await _ai_internal_post(
        request,
        f"/api/v1/ai/cameras/{ctx['cameraId']}/sessions",
        {"mode": mode, "farmId": ctx["farmId"], "zoneId": ctx["zoneId"]},
    )


@router.post(
    "/api/v1/ai/cameras/{camera_id}/session/stop",
    tags=["AI Service - Camera Sessions (INT02)"],
    summary="Stop the AI session of an authorised camera",
)
async def proxy_ai_camera_session_stop(
    request: Request,
    camera_id: str,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "FARM_OWNER", "TECHNICIAN")),
) -> Response:
    _check_path_security(request, f"cameras/{camera_id}/session/stop")
    canonical_camera_id = await resolve_camera_access(camera_id, request)
    return await _ai_internal_post(request, f"/api/v1/ai/cameras/{canonical_camera_id}/stop")


@router.post(
    "/api/v1/ai/cameras/{camera_id}/frames",
    tags=["AI Service - Camera Sessions (INT02)"],
    summary="Push one webcam frame (JPEG/PNG) into the camera's LOCAL_CAMERA session",
)
async def proxy_ai_camera_frame(
    request: Request,
    camera_id: str,
    current_user: Dict[str, Any] = Depends(require_roles("ADMIN", "FARM_OWNER", "TECHNICIAN")),
) -> Response:
    _check_path_security(request, f"cameras/{camera_id}/frames")
    ctype = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if ctype not in ("image/jpeg", "image/png"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Frames must be image/jpeg or image/png")
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_AI_FRAME_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Frame too large")
    canonical_camera_id = await resolve_camera_access(camera_id, request)
    body = await request.body()
    if len(body) > MAX_AI_FRAME_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Frame too large")
    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.ai_service_url,
        upstream_path=f"/api/v1/ai/cameras/{canonical_camera_id}/frames",
        timeout=settings.ai_timeout_seconds,
    )


@router.get(
    "/api/v1/ai/events",
    tags=["AI Service - Events (Locked)"],
    summary="Get AI detection events (Locked for non-admin)",
)
async def proxy_ai_events(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """AI events endpoint is locked for non-admins pending event-to-farm resolver."""
    _check_path_security(request, "events")
    roles = current_user.get("roles") or []
    farm_id = extract_param_safe(request, ["farm_id", "farmId"])

    if farm_id and "ADMIN" not in roles:
        # Check authorization if supplied, but fail closed regardless for cross-tenant or unverified events
        await resolve_farm_access(farm_id, request)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: AI detection events endpoint is locked pending event-to-farm resolver",
        )
    elif "ADMIN" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: AI detection events endpoint is locked pending event-to-farm resolver",
        )

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.ai_service_url,
        upstream_path="/api/v1/ai/events",
        timeout=settings.ai_timeout_seconds,
    )


@router.get(
    "/api/v1/ai/events/{event_id}",
    tags=["AI Service - Events (Locked)"],
    summary="Get single AI detection event by ID (Locked for non-admin)",
)
async def proxy_ai_event_detail(
    request: Request,
    event_id: str,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """AI event detail by ID. Locked for non-admins pending event-to-farm resolver."""
    _check_path_security(request, f"events/{event_id}")
    roles = current_user.get("roles") or []
    if "ADMIN" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: AI detection event detail is locked pending event-to-farm resolver",
        )

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.ai_service_url,
        upstream_path=f"/api/v1/ai/events/{event_id}",
        timeout=settings.ai_timeout_seconds,
    )


@router.get(
    "/api/v1/ai/snapshots/{snapshot_path:path}",
    tags=["AI Service - Snapshots (Locked)"],
    summary="Get AI snapshot image (Locked for non-admin)",
)
async def proxy_ai_snapshots_locked(
    request: Request,
    snapshot_path: str,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """Camera snapshot endpoints are locked for non-admins pending camera-to-farm resolver."""
    _check_path_security(request, f"snapshots/{snapshot_path}")
    roles = current_user.get("roles") or []
    if "ADMIN" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Camera snapshot access is temporarily locked pending camera-to-farm resolver",
        )

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.ai_service_url,
        upstream_path=f"/api/v1/ai/snapshots/{snapshot_path}",
        timeout=settings.ai_timeout_seconds,
    )


# =============================================================================
# 4. Notification Service Routes (/api/v1/alerts/*, /api/v1/notifications/*, /api/v1/devices/*)
# =============================================================================

@router.get(
    "/api/v1/alerts",
    tags=["Notification - Alerts"],
    summary="List alerts with mandatory farm scoping for non-admins",
)
async def proxy_alerts_root(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """List alerts. Non-admins must provide farmId / farm_id."""
    _check_path_security(request, "")
    roles = current_user.get("roles") or []
    farm_id = extract_param_safe(request, ["farmId", "farm_id"])

    canonical_farm_id = None
    if farm_id:
        canonical_farm_id = await resolve_farm_access(farm_id, request)
    elif "ADMIN" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: 'farmId' parameter required for non-admin users to prevent cross-tenant exposure",
        )

    # Canonicalize query: ensure upstream Notification receives canonical farmId
    query_dict = dict(request.query_params)
    query_dict.pop("farm_id", None)
    if canonical_farm_id:
        query_dict["farmId"] = canonical_farm_id
    canonical_qs = urllib.parse.urlencode(query_dict)

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.notification_service_url,
        upstream_path="/api/v1/alerts",
        timeout=settings.notification_timeout_seconds,
        canonical_query=canonical_qs,
    )


@router.get(
    "/api/v1/alerts/{alert_id}",
    tags=["Notification - Alerts"],
    summary="Get alert by ID with authorization",
)
async def proxy_alert_detail(
    request: Request,
    alert_id: str,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """Single alert detail with authoritative alert ownership resolution."""
    _check_path_security(request, alert_id)
    await resolve_alert_access(
        alert_id,
        request,
        locked_detail="Forbidden: Direct alert access by ID is locked pending alert-to-farm resolver",
    )

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.notification_service_url,
        upstream_path=f"/api/v1/alerts/{alert_id}",
        timeout=settings.notification_timeout_seconds,
    )


@router.post(
    "/api/v1/alerts/{alert_id}/acknowledge",
    tags=["Notification - Alerts"],
    summary="Acknowledge alert by ID with authorization",
)
async def proxy_alert_ack_locked(
    request: Request,
    alert_id: str,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """Alert acknowledgement by ID with authoritative alert ownership resolution."""
    _check_path_security(request, f"{alert_id}/acknowledge")
    await resolve_alert_access(
        alert_id,
        request,
        locked_detail="Forbidden: Direct alert acknowledgement by ID is temporarily locked pending alert-to-farm resolver",
    )

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.notification_service_url,
        upstream_path=f"/api/v1/alerts/{alert_id}/acknowledge",
        timeout=settings.notification_timeout_seconds,
    )


@router.post(
    "/api/v1/alerts/{alert_id}/resolve",
    tags=["Notification - Alerts"],
    summary="Resolve alert by ID with authorization",
)
async def proxy_alert_resolve_locked(
    request: Request,
    alert_id: str,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """Alert resolution by ID with authoritative alert ownership resolution."""
    _check_path_security(request, f"{alert_id}/resolve")
    await resolve_alert_access(
        alert_id,
        request,
        locked_detail="Forbidden: Direct alert resolution by ID is temporarily locked pending alert-to-farm resolver",
    )

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.notification_service_url,
        upstream_path=f"/api/v1/alerts/{alert_id}/resolve",
        timeout=settings.notification_timeout_seconds,
    )


@router.get(
    "/api/v1/notifications",
    tags=["Notification - Items"],
    summary="List notifications with strict caller identity scoping",
)
async def proxy_notifications_root(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """List notifications. Requires caller's own userId (alertId-only queries forbidden for non-admins)."""
    _check_path_security(request, "")
    user_id = verify_notification_user_query(request, current_user)

    # Canonicalize query: ensure upstream Notification receives userId
    query_dict = dict(request.query_params)
    query_dict.pop("user_id", None)
    query_dict["userId"] = user_id
    canonical_qs = urllib.parse.urlencode(query_dict)

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.notification_service_url,
        upstream_path="/api/v1/notifications",
        timeout=settings.notification_timeout_seconds,
        canonical_query=canonical_qs,
    )


@router.post(
    "/api/v1/notifications/read-all",
    tags=["Notification - Items (Locked)"],
    summary="Mark all notifications as read (Locked)",
)
async def proxy_notifications_read_all_locked(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """Read-all notification mutation is locked pending user-scoped notification resolver."""
    _check_path_security(request, "read-all")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Forbidden: Notification read-all is temporarily locked pending user-scoped notification resolver",
    )


@router.post(
    "/api/v1/notifications/{notification_id}/read",
    tags=["Notification - Items (Locked)"],
    summary="Mark single notification as read (Locked)",
)
async def proxy_notifications_item_read_locked(
    request: Request,
    notification_id: str,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """Single notification read mutation is locked pending user-scoped notification resolver."""
    _check_path_security(request, f"{notification_id}/read")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Forbidden: Notification item read is temporarily locked pending user-scoped notification resolver",
    )


@router.post(
    "/api/v1/devices",
    tags=["Notification - User Devices"],
    summary="Register user FCM device with identity validation",
)
async def proxy_notif_devices_post(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """Ensures caller cannot register FCM device tokens for another user (checks userId and user_id)."""
    _check_path_security(request, "")
    await verify_fcm_device_registration(request, current_user)

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.notification_service_url,
        upstream_path="/api/v1/devices",
        timeout=settings.notification_timeout_seconds,
    )


@router.get(
    "/api/v1/devices",
    tags=["Notification - User Devices (Blocked)"],
    summary="List user registered notification devices (Blocked: Upstream does not implement GET)",
)
async def proxy_notif_devices_get(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """List registered devices for caller.

    BLOCKED / NOT IMPLEMENTED UPSTREAM:
    Upstream Notification Service (app/api/devices.py) only implements POST (registration)
    and DELETE (unregistration). Listing user devices is not implemented in upstream API.
    """
    _check_path_security(request, "")
    target_user_id = extract_param_safe(request, ["userId", "user_id"])
    caller_id = str(current_user.get("id") or current_user.get("sub", "")).strip()
    roles = current_user.get("roles") or []

    if target_user_id and target_user_id != caller_id and "ADMIN" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot list notification devices for another user",
        )

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="NOT_IMPLEMENTED: Device registration listing is not supported by upstream Notification Service.",
    )


@router.delete(
    "/api/v1/devices/{device_id}",
    tags=["Notification - User Devices (Locked)"],
    summary="Delete device registration by ID (Locked for non-admin)",
)
async def proxy_notif_devices_delete(
    request: Request,
    device_id: str,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """Direct deletion of device registration by opaque ID is fail-closed for non-admins."""
    _check_path_security(request, device_id)
    roles = current_user.get("roles") or []
    if "ADMIN" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Direct notification device mutation by ID is temporarily locked",
        )

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.notification_service_url,
        upstream_path=f"/api/v1/devices/{device_id}",
        timeout=settings.notification_timeout_seconds,
    )


# =============================================================================
# 5. Analytics Service Routes (CP9 Target - /api/v1/analytics/*)
# =============================================================================

@router.get(
    "/api/v1/analytics/farms/{farm_id}/summary",
    tags=["Analytics Service"],
    summary="Get farm analytics summary (Farm-scoped)",
)
async def proxy_analytics_farm_summary(
    request: Request,
    farm_id: str,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """Farm-scoped analytics summary requires farm authorization."""
    _check_path_security(request, f"farms/{farm_id}/summary")
    canonical_farm_id = await resolve_farm_access(farm_id, request)

    # Analytics Service deployment check (fail-closed)
    if not settings.analytics_service_deployed:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SERVICE_NOT_DEPLOYED: Analytics Service is not yet deployed",
        )

    # Strictly allowlist parameters and apply standard URL encoding
    query_dict: dict[str, str] = {}
    period = request.query_params.get("period")
    if period:
        query_dict["period"] = period
    canonical_qs = urllib.parse.urlencode(query_dict)

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.analytics_service_url,
        upstream_path=f"/api/v1/analytics/farms/{canonical_farm_id}/summary",
        timeout=settings.analytics_timeout_seconds,
        canonical_query=canonical_qs,
    )


@router.get(
    "/api/v1/analytics/farms/{farm_id}/trends",
    tags=["Analytics Service"],
    summary="Get farm analytics trends (Farm-scoped)",
)
async def proxy_analytics_farm_trends(
    request: Request,
    farm_id: str,
    current_user: Dict[str, Any] = Depends(require_any_authenticated),
) -> Response:
    """Farm-scoped analytics trends requires farm authorization."""
    _check_path_security(request, f"farms/{farm_id}/trends")
    canonical_farm_id = await resolve_farm_access(farm_id, request)

    # Analytics Service deployment check (fail-closed)
    if not settings.analytics_service_deployed:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SERVICE_NOT_DEPLOYED: Analytics Service is not yet deployed",
        )

    # Strictly allowlist parameters and apply standard URL encoding
    query_dict = {}
    period = request.query_params.get("period")
    if period:
        query_dict["period"] = period
    zone_id = request.query_params.get("zone_id")
    if zone_id:
        query_dict["zone_id"] = zone_id
    metric = request.query_params.get("metric")
    if metric:
        query_dict["metric"] = metric
    canonical_qs = urllib.parse.urlencode(query_dict)

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.analytics_service_url,
        upstream_path=f"/api/v1/analytics/farms/{canonical_farm_id}/trends",
        timeout=settings.analytics_timeout_seconds,
        canonical_query=canonical_qs,
    )


@router.get(
    "/api/v1/analytics/trends",
    tags=["Analytics Service"],
    summary="Get global analytics trends (Admin only)",
)
async def proxy_analytics_trends_global(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Response:
    """Global analytics trends without farm scoping is restricted to ADMIN."""
    _check_path_security(request, "trends")

    # Analytics Service deployment check (fail-closed)
    if not settings.analytics_service_deployed:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SERVICE_NOT_DEPLOYED: Analytics Service is not yet deployed",
        )

    # Strictly allowlist parameters and apply standard URL encoding
    query_dict = {}
    period = request.query_params.get("period")
    if period:
        query_dict["period"] = period
    metric = request.query_params.get("metric")
    if metric:
        query_dict["metric"] = metric
    canonical_qs = urllib.parse.urlencode(query_dict)

    return await proxy_handler.forward(
        request=request,
        upstream_base_url=settings.analytics_service_url,
        upstream_path="/api/v1/analytics/trends",
        timeout=settings.analytics_timeout_seconds,
        canonical_query=canonical_qs,
    )
