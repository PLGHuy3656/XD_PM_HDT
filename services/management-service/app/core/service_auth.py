"""Dedicated Pre-Shared Key (PSK) Service Authentication (CP11.4-B1-R2-MGMT-R2).

Enforces strict machine-to-machine trust boundary:
1. Accepts ONLY 'X-Internal-Service-Key' header.
2. Strictly rejects 'Authorization: Bearer' tokens (user, ADMIN, and service JWTs).
3. Rejects conflicting credentials (both Authorization and X-Internal-Service-Key present).
4. No fallback to user JWT_SECRET, no ADMIN role bypass, no substring identity matching.
5. Enforces minimum 32-byte high-entropy PSK credentials.
6. Handles invalid/non-ASCII credential encoding safely without throwing HTTP 500.
7. Constant-time byte-level comparison (secrets.compare_digest) to prevent timing attacks.
8. Supports zero-downtime key rotation via comma-separated active tokens.
9. Strictly fail-closed if service auth is unconfigured or weak.
10. Never logs credentials.
"""
from __future__ import annotations

import logging
import secrets
from typing import Any, Dict
from fastapi import Header, HTTPException, Request, status

from app.config import MIN_PSK_BYTES, settings

logger = logging.getLogger("management_service.service_auth")


def verify_internal_service(request: Request) -> Dict[str, Any]:
    """FastAPI dependency enforcing dedicated PSK authentication for internal routes."""
    auth_header = request.headers.get("authorization")
    internal_key_header = request.headers.get("x-internal-service-key")

    # 1. Reject conflicting credentials
    if auth_header and internal_key_header:
        logger.warning("[SERVICE_AUTH] Rejected request with conflicting credentials (both Authorization and X-Internal-Service-Key present)")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conflicting credentials: Authorization header is not permitted on internal endpoints",
        )

    # 2. Reject Bearer tokens (User JWT, ADMIN JWT, or Service JWT)
    if auth_header:
        logger.warning("[SERVICE_AUTH] Rejected Authorization header on internal endpoint")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer tokens are not accepted on internal endpoints; supply X-Internal-Service-Key",
        )

    # 3. Reject missing X-Internal-Service-Key
    if not internal_key_header or not internal_key_header.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required header: X-Internal-Service-Key",
        )

    token = internal_key_header.strip()

    # 4. Safely handle and reject non-ASCII credentials without triggering TypeError/HTTP 500
    if not token.isascii():
        logger.warning("[SERVICE_AUTH] Rejected non-ASCII credential format")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service credentials",
        )

    # 5. Fail closed on server configuration errors (unconfigured or weak configured key)
    if settings.has_weak_service_token:
        logger.error("[SERVICE_AUTH] Server misconfigured: configured service key has fewer than 32 bytes")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service authentication misconfigured: configured service key is weak (< 32 bytes)",
        )

    if not settings.is_service_auth_configured:
        logger.error("[SERVICE_AUTH] Server misconfigured: no service key configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service authentication misconfigured: no service key configured",
        )

    # 6. Reject incoming key if shorter than 32 bytes
    token_bytes = token.encode("ascii", errors="ignore")
    if len(token_bytes) < MIN_PSK_BYTES:
        logger.warning("[SERVICE_AUTH] Rejected client key shorter than minimum 32 bytes")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service credentials",
        )

    # 7. Byte-level constant-time comparison against configured valid keys (supporting rotation)
    try:
        is_valid = any(
            secrets.compare_digest(token_bytes, valid_key.encode("ascii", errors="ignore"))
            for valid_key in settings.valid_service_tokens
        )
    except Exception as exc:
        logger.warning("[SERVICE_AUTH] Credential comparison failed safely: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service credentials",
        ) from exc

    if not is_valid:
        logger.warning("[SERVICE_AUTH] Invalid service key provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service credentials",
        )

    logger.debug("[SERVICE_AUTH] Successfully authenticated via dedicated PSK")
    return {
        "service": "internal-service",
        "auth_type": "psk",
    }
