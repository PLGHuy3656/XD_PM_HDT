from fastapi import HTTPException, status
from app.services.zone_service import ZoneService, zone_service


class ZoneController:
    def __init__(self, service: ZoneService | None = None):
        self.service = service or zone_service

    def list_zones_by_farm(self, farm_id: str):
        try:
            return self.service.list_zones_by_farm(farm_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    def get_zone(self, zone_id: str):
        try:
            zone = self.service.get_zone(zone_id)
            if zone is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Zone not found",
                )
            return zone
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc


zone_controller = ZoneController()
