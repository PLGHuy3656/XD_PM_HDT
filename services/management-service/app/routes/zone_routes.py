import uuid
from fastapi import APIRouter, Depends, HTTPException, status

from app.controllers.zone_controller import zone_controller
from app.core.dependencies import (
    get_current_user,
    require_roles,
    verify_farm_resource_access,
)
from app.repositories.farm_repository import farm_repository
from app.repositories.user_repository import user_repository
from app.schemas.zone import ZoneCreateRequest, ZoneResponse, ZoneUpdateRequest

router = APIRouter(
    tags=["Zones"],
)


@router.get(
    "/api/farms/{farm_id}/zones",
    response_model=list[ZoneResponse],
    summary="List zones for an authorized farm",
)
def list_zones_by_farm(farm_id: str, current_user: dict = Depends(get_current_user)):
    verify_farm_resource_access(current_user, farm_id)
    return zone_controller.list_zones_by_farm(farm_id)


@router.get(
    "/api/zones/{zone_id}",
    response_model=ZoneResponse,
    summary="Get zone by ID with parent farm resource authorization",
)
def get_zone(zone_id: str, current_user: dict = Depends(get_current_user)):
    # 1. Detail endpoint strictly requires UUID. Non-UUID yields 404 (or 422).
    try:
        uuid.UUID(str(zone_id).strip())
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found: invalid UUID",
        )

    # 2. Load the exact single Zone record
    zone = zone_controller.get_zone(zone_id)
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )

    # 3. Authorize strictly against the farm_id of the loaded record (eliminates dual lookup IDOR)
    verify_farm_resource_access(current_user, zone["farm_id"])
    return zone


@router.post(
    "/api/farms/{farm_id}/zones",
    response_model=ZoneResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a zone inside an authorized farm (Admin or owning Farm Owner)",
)
def create_zone(
    farm_id: str,
    payload: ZoneCreateRequest,
    current_user: dict = Depends(require_roles("ADMIN", "FARM_OWNER")),
):
    verify_farm_resource_access(current_user, farm_id)
    farm_uuid = user_repository.resolve_farm_uuid(farm_id)
    if not farm_uuid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
    farm = farm_repository.get_farm_by_id(farm_uuid)
    if not farm or farm.get("approval_status") != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Farm must be approved by Admin before creating zones",
        )
    return zone_controller.create_zone(farm_uuid=farm_uuid, zone_code=payload.zone_code, name=payload.name)


@router.put(
    "/api/zones/{zone_id}",
    response_model=ZoneResponse,
    summary="Update a zone (Admin or owning Farm Owner)",
)
def update_zone(
    zone_id: str,
    payload: ZoneUpdateRequest,
    current_user: dict = Depends(require_roles("ADMIN", "FARM_OWNER")),
):
    zone = zone_controller.get_zone(zone_id)
    verify_farm_resource_access(current_user, zone["farm_id"])
    return zone_controller.update_zone(zone_id=zone_id, zone_code=payload.zone_code, name=payload.name)


@router.delete(
    "/api/zones/{zone_id}",
    summary="Delete a zone (Admin or owning Farm Owner)",
)
def delete_zone(
    zone_id: str,
    current_user: dict = Depends(require_roles("ADMIN", "FARM_OWNER")),
):
    zone = zone_controller.get_zone(zone_id)
    verify_farm_resource_access(current_user, zone["farm_id"])
    return zone_controller.delete_zone(zone_id)
