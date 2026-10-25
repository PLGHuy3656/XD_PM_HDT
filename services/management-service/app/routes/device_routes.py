from fastapi import APIRouter, Query
from app.controllers.device_controller import device_controller
from app.schemas.device import DeviceRegistryResponse

router = APIRouter(
    prefix="/api/devices",
    tags=["Device Registry"],
)


@router.get("", response_model=list[DeviceRegistryResponse])
def list_devices(
    farm_id: str | None = Query(None, description="Filter by Farm / House ID"),
    zone_id: str | None = Query(None, description="Filter by Zone ID"),
):
    return device_controller.list_devices(farm_id=farm_id, zone_id=zone_id)


@router.get("/{device_id}", response_model=DeviceRegistryResponse)
def get_device(device_id: str):
    return device_controller.get_device(device_id)
