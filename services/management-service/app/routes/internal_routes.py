"""Internal Service-to-Service Router (CP11.4-B1-R2-MGMT-R2).

Exposes non-public management endpoints for internal service consumption (e.g., IoT Service).
Protected by dedicated service authentication (verify_internal_service).
Completely separate from public user RBAC and isolated from the public Gateway.
"""
from __future__ import annotations

import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Path, status
import psycopg

from app.core.service_auth import verify_internal_service
from app.repositories.device_repository import AmbiguousDeviceIdentifierError
from app.schemas.internal import (
    InternalDeviceMetadataResponse,
    InternalFarmRecipientsResponse,
)
from app.services.device_service import device_service
from app.services.farm_service import farm_service

logger = logging.getLogger("management_service.internal_routes")

router = APIRouter(
    prefix="/internal/v1",
    tags=["Internal Service-to-Service"],
    dependencies=[Depends(verify_internal_service)],
)


@router.get(
    "/devices/{node_id}",
    response_model=InternalDeviceMetadataResponse,
    summary="Get authoritative device metadata for internal services",
    description="Resolves device-to-farm boundary mapping by MQTT node ID or canonical UUID. "
                "Protected by service credentials. Never exposes owner PII.",
)
def get_internal_device_metadata(
    node_id: str = Path(..., description="Authoritative MQTT device node_id or canonical UUID"),
    _service_auth: Dict[str, Any] = Depends(verify_internal_service),
):
    # Reject NUL-containing strings before database access to avoid DataError / ValueError
    if "\x00" in node_id or "\0" in node_id:
        logger.warning("[INTERNAL_ROUTES] Rejected device identifier containing NUL character")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device identifier contains invalid characters",
        )

    clean_id = str(node_id).strip()
    if not clean_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device identifier cannot be empty",
        )

    # Reject control characters
    if any(ord(c) < 32 or ord(c) == 127 for c in clean_id):
        logger.warning("[INTERNAL_ROUTES] Rejected device identifier containing control characters")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device identifier contains invalid control characters",
        )

    if len(clean_id) > 100:
        logger.warning("[INTERNAL_ROUTES] Rejected device identifier exceeding 100 characters")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device identifier exceeds maximum allowed length of 100 characters",
        )

    try:
        metadata = device_service.get_internal_metadata(clean_id)
    except AmbiguousDeviceIdentifierError as exc:
        logger.warning("[INTERNAL_ROUTES] Ambiguous device identifier '%s': %s", clean_id, exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except psycopg.errors.UndefinedColumn as exc:
        # Schema migration missing (metadata_version column not present)
        logger.error("[INTERNAL_ROUTES] Database schema migration missing for metadata_version: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable: schema migration pending",
        ) from exc
    except psycopg.OperationalError as exc:
        # True database connection or network outage
        logger.error("[INTERNAL_ROUTES] Database operational outage: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable",
        ) from exc
    except (psycopg.DataError, ValueError) as exc:
        # Data representation / syntax error from caller
        logger.warning("[INTERNAL_ROUTES] Bad request data for device '%s': %s", clean_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid device identifier syntax",
        ) from exc
    except psycopg.Error as exc:
        # Generic database error (safe fallback without information disclosure)
        logger.error("[INTERNAL_ROUTES] Database error occurred: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable",
        ) from exc
    except RuntimeError as exc:
        logger.error("[INTERNAL_ROUTES] Runtime configuration error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable",
        ) from exc

    if metadata is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    return metadata


@router.get(
    "/farms/{farm_id}/recipients",
    response_model=InternalFarmRecipientsResponse,
    summary="Get authoritative owner & assigned technicians for a farm (AUD-C-02)",
)
def get_internal_farm_recipients(
    farm_id: str = Path(..., description="Canonical farm UUID or farm_code"),
    _service_auth: Dict[str, Any] = Depends(verify_internal_service),
):
    recipients = farm_service.get_farm_recipients(farm_id)
    if recipients is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farm not found",
        )
    return recipients
