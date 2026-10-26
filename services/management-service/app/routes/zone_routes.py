from fastapi import APIRouter, Depends, HTTPException, status

from app.controllers.zone_controller import zone_controller
from app.core.dependencies import get_current_user, verify_farm_resource_access
from app.repositories.user_repository import user_repository
from app.schemas.zone import ZoneResponse

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
    parent_farm_id = user_repository.get_farm_id_for_zone(zone_id)
    if not parent_farm_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )
    verify_farm_resource_access(current_user, parent_farm_id)
    return zone_controller.get_zone(zone_id)
