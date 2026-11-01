from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.controllers.device_controller import device_controller
from app.controllers.farm_controller import farm_controller
from app.core.dependencies import get_current_user, verify_farm_resource_access
from app.repositories.user_repository import user_repository
from app.schemas.device import DeviceRegistryResponse, DeviceZoneUpdateRequest

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

    if zone_id:
        parent_farm_id = user_repository.get_farm_id_for_zone(zone_id)
        if parent_farm_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Zone not found",
            )
        verify_farm_resource_access(current_user, parent_farm_id)

    roles = current_user.get("roles") or []
    farm_ids = None
    if "ADMIN" not in roles:
        accessible_farms = farm_controller.list_farms(current_user)
        farm_ids = [farm["farm_id"] for farm in accessible_farms]

    return device_controller.list_devices(
        farm_id=farm_id,
        zone_id=zone_id,
        farm_ids=farm_ids,
    )


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


@router.patch(
    "/{device_id}/zone",
    summary="Move a device to a zone in its authorized farm",
)
def update_device_zone(
    device_id: str,
    request: DeviceZoneUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    roles = set(current_user.get("roles") or [])
    if not roles.intersection({"ADMIN", "TECHNICIAN"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators and assigned technicians can move devices",
        )

    farm_id = user_repository.get_farm_id_for_device(device_id)
    if farm_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    verify_farm_resource_access(current_user, farm_id)

    zone_farm_id = user_repository.get_farm_id_for_zone(request.zone_id)
    if zone_farm_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )
    if zone_farm_id != farm_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device can only be moved to a zone in its own farm",
        )

    return device_controller.update_device_zone(
        device_id,
        farm_id,
        request.zone_id,
    )
