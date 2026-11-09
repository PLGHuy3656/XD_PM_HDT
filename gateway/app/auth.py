"""Authentication and Role-Based Access Control (RBAC) module for API Gateway (CP11.3).

Performs:
1. Strict JWT validation (HS256, expiration, required sub and roles claims).
2. Authoritative active user introspection via Management Service GET /api/auth/me.
3. Fail-closed behavior on introspection failure or management outage.
4. Role permission enforcement (ADMIN, FARM_OWNER, TECHNICIAN).
5. Zero leakage of tokens or secret material in logs.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional
import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

logger = logging.getLogger("gateway.auth")

# HTTPBearer extraction without automatic FastAPI default 403 behavior
bearer_scheme = HTTPBearer(auto_error=False)


def decode_and_verify_token(token: str) -> Dict[str, Any]:
    """Decodes and cryptographically verifies JWT access token signature, algorithm, and claims.

    Enforces HS256 algorithm and required claims ('sub', 'roles').
    NEVER logs token content or secret key.
    """
    if not settings.jwt_secret:
        logger.error("Authentication failed: JWT_SECRET is not configured on Gateway")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error: Authentication configuration missing",
        )

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {exc.__class__.__name__}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate essential claims
    sub = payload.get("sub")
    if not sub or not isinstance(sub, str) or not sub.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload: 'sub' claim missing or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    roles = payload.get("roles")
    if roles is None or not isinstance(roles, list):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload: 'roles' claim missing or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def check_user_active_via_management(
    token: str,
    user_id: str,
    client: httpx.AsyncClient,
    correlation_id: str,
) -> Dict[str, Any]:
    """Authoritatively verifies that the user is active by calling Management Service GET /api/auth/me.

    Does not query management_db directly.
    Fails closed (HTTP 503) if Management Service is unreachable.
    Fails closed (HTTP 401) if account is inactive, disabled, or not found.
    """
    me_url = f"{settings.management_service_url.rstrip('/')}/api/auth/me"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Correlation-ID": correlation_id,
        "Accept": "application/json",
    }

    try:
        resp = await client.get(
            me_url,
            headers=headers,
            timeout=settings.management_timeout_seconds,
        )
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as net_err:
        logger.warning(
            "Management auth introspection unreachable [cid=%s]: %s (Fail closed)",
            correlation_id,
            net_err.__class__.__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service Unavailable: Authentication introspection backend unreachable",
        ) from net_err
    except Exception as exc:
        logger.error(
            "Unexpected error during auth introspection [cid=%s]: %s",
            correlation_id,
            exc.__class__.__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service Unavailable: Authentication service error",
        ) from exc

    if resp.status_code == status.HTTP_401_UNAUTHORIZED:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if resp.status_code != status.HTTP_200_OK:
        logger.warning(
            "Management auth introspection returned non-200 [%s] [cid=%s]",
            resp.status_code,
            correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service Unavailable: Authentication backend reported failure",
        )

    try:
        user_info = resp.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service Unavailable: Invalid introspection response",
        )

    # 1. Authoritative active status check
    if user_info.get("status") != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is not active",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Strict ID verification: User ID in /me must match JWT sub
    me_user_id = str(user_info.get("id", ""))
    if not me_user_id or me_user_id != str(user_id):
        logger.warning(
            "JWT sub mismatch [cid=%s]: token sub=%s vs /me id=%s",
            correlation_id,
            user_id,
            me_user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Token subject does not match account identity",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Authoritative role assignment from Management Service
    user_info["roles"] = user_info.get("roles") or []
    return user_info


async def get_current_gateway_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Dict[str, Any]:
    """Dependency that authenticates incoming request using Bearer JWT.

    Verifies signature and authoritative active status, attaches user to request.state.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: Missing or empty Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials.strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: Token cannot be empty",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 1. Verify token signature, algorithm, and claims locally
    payload = decode_and_verify_token(token)
    user_id = payload["sub"]
    correlation_id = getattr(request.state, "correlation_id", "unknown-cid")

    # 2. Check active user status authoritatively if active check is enabled
    client = getattr(request.app.state, "http_client", None)
    if client is None:
        client = httpx.AsyncClient()

    if settings.jwt_require_active_check:
        user_info = await check_user_active_via_management(
            token=token,
            user_id=user_id,
            client=client,
            correlation_id=correlation_id,
        )
    else:
        # Fallback only when active check explicitly disabled in test fixtures
        user_info = {
            "id": user_id,
            "roles": payload.get("roles", []),
            "email": payload.get("email", ""),
            "status": "ACTIVE",
        }

    # Attach verified user to request state for downstream use and header injection
    request.state.user = user_info
    request.state.raw_token = token
    return user_info


def require_roles(*allowed_roles: str) -> Callable:
    """Dependency factory enforcing role-based access control.

    Raises HTTP 403 if authenticated user does not have at least one allowed role.
    """
    async def _role_checker(
        current_user: Dict[str, Any] = Depends(get_current_gateway_user),
    ) -> Dict[str, Any]:
        user_roles = current_user.get("roles") or []
        if not any(r in allowed_roles for r in user_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Insufficient role permissions. Required: {', '.join(allowed_roles)}",
            )
        return current_user

    return _role_checker


# Convenient role checkers
require_admin = require_roles("ADMIN")
require_any_authenticated = require_roles("ADMIN", "FARM_OWNER", "TECHNICIAN")
