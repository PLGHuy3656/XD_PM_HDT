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
    zone_id: str | None = Query(None, description="Filter by Zone ID"),
    current_user: dict = Depends(get_current_user),
):
    if farm_id:
        verify_farm_resource_access(current_user, farm_id)
    return device_controller.list_devices(farm_id=farm_id, zone_id=zone_id)


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
