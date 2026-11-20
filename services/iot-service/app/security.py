"""INT01-R1: service-to-service authentication for IoT Service HTTP/WebSocket APIs.

The IoT Service holds no user identity or RBAC (owned by Management + API Gateway).
Its HTTP API is therefore only callable by trusted internal services that present the
shared INT01 internal service key in ``X-Internal-Service-Key``:

  * API Gateway  -> after JWT validation + farm/device ownership checks (resolve_device_access)
  * Management   -> device presence lookups (CP8 adapter)

Browsers and host-local clients never hold this key, so a direct call to the IoT API
cannot bypass Gateway RBAC. Fail-closed: if auth is required and no key is configured,
protected routes answer 503 instead of silently opening.
"""
from __future__ import annotations

import hmac
import logging

from fastapi import Header, HTTPException, WebSocket, WebSocketException, status

from app.config import settings

logger = logging.getLogger("iot_service.security")

INTERNAL_SERVICE_KEY_HEADER = "X-Internal-Service-Key"


def _configured_key() -> str:
    return (settings.internal_service_key or "").strip()


def is_valid_internal_key(presented: str | None) -> bool:
    expected = _configured_key()
    if not expected or not presented:
        return False
    return hmac.compare_digest(presented.strip().encode("utf-8"), expected.encode("utf-8"))


def require_internal_service(
    x_internal_service_key: str | None = Header(default=None, alias=INTERNAL_SERVICE_KEY_HEADER),
) -> None:
    """FastAPI dependency guarding every /api/iot/* route."""
    if not settings.internal_api_auth_required:
        return
    if not _configured_key():
        logger.error("[IOT AUTH] internal service key not configured; failing closed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="IoT internal API authentication is not configured",
        )
    if not is_valid_internal_key(x_internal_service_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid internal service credentials",
        )


async def require_internal_service_ws(websocket: WebSocket) -> None:
    """Guards the internal /ws/iot realtime stream (never exposed to browsers)."""
    if not settings.internal_api_auth_required:
        return
    if not is_valid_internal_key(websocket.headers.get(INTERNAL_SERVICE_KEY_HEADER)):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
