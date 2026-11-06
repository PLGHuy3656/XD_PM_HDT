from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.controllers.device_controller import device_controller
from app.core.dependencies import get_current_user, verify_farm_resource_access
from app.repositories.user_repository import user_repository
from app.schemas.device import DeviceRegistryResponse

router = APIRouter(
    prefix="/api/devices",
    tags=["Device Registry"],
)


@router.get(
    "",
    response_model=list[DeviceRegistryResponse],
    summary="List registered devices with farm filtering and authorization",
)
def list_devices(
    farm_id: str | None = Query(None, description="Filter by Farm / House ID"),
    farmId: str | None = Query(None, description="Filter by Farm / House ID (alias)"),
    zone_id: str | None = Query(None, description="Filter by Zone ID"),
    current_user: dict = Depends(get_current_user),
):
    # Parameter normalization & conflict check
    effective_farm_id = None
    if farm_id and farmId and farm_id.strip() != farmId.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ambiguous or conflicting farm_id/farmId parameters",
        )
    effective_farm_id = (farm_id or farmId)
    if effective_farm_id:
        effective_farm_id = effective_farm_id.strip()

    roles = current_user.get("roles") or []
    if not effective_farm_id and "ADMIN" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: 'farm_id' parameter is required for non-admin users",
        )

    if effective_farm_id:
        verify_farm_resource_access(current_user, effective_farm_id)

    return device_controller.list_devices(farm_id=effective_farm_id, zone_id=zone_id)


@router.get(
    "/{device_id}",
    response_model=DeviceRegistryResponse,
    summary="Get registered device metadata with parent farm resource authorization",
)
def get_device(device_id: str, current_user: dict = Depends(get_current_user)):
    parent_farm_id = user_repository.get_farm_id_for_device(device_id)
    if not parent_farm_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    verify_farm_resource_access(current_user, parent_farm_id)
    return device_controller.get_device(device_id)
