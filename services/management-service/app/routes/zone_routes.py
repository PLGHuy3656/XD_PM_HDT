from fastapi import APIRouter
from app.controllers.zone_controller import zone_controller
from app.schemas.zone import ZoneResponse

router = APIRouter(
    tags=["Zones"],
)


@router.get("/api/farms/{farm_id}/zones", response_model=list[ZoneResponse])
def list_zones_by_farm(farm_id: str):
    return zone_controller.list_zones_by_farm(farm_id)


@router.get("/api/zones/{zone_id}", response_model=ZoneResponse)
def get_zone(zone_id: str):
    return zone_controller.get_zone(zone_id)
