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

    def create_zone(self, farm_uuid: str, zone_code: str | None = None, name: str = ""):
        try:
            return self.service.create_zone(farm_uuid=farm_uuid, zone_code=zone_code, name=name)
        except ValueError as exc:
            code = status.HTTP_409_CONFLICT if "already exists" in str(exc) else status.HTTP_400_BAD_REQUEST
            raise HTTPException(status_code=code, detail=str(exc)) from exc

    def update_zone(self, zone_id: str, zone_code: str | None = None, name: str | None = None):
        try:
            zone = self.service.update_zone(zone_id=zone_id, zone_code=zone_code, name=name)
            if zone is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found")
            return zone
        except ValueError as exc:
            code = status.HTTP_409_CONFLICT if "already exists" in str(exc) else status.HTTP_400_BAD_REQUEST
            raise HTTPException(status_code=code, detail=str(exc)) from exc

    def delete_zone(self, zone_id: str):
        deleted = self.service.delete_zone(zone_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found")
        return {"status": "deleted", "zone_id": zone_id}


zone_controller = ZoneController()
