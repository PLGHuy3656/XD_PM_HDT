from fastapi import HTTPException, status
from app.services.farm_service import FarmService, farm_service


class FarmController:
    def __init__(self, service: FarmService | None = None):
        self.service = service or farm_service

    def list_farms(self):
        try:
            return self.service.list_farms()
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    def get_farm(self, farm_id: str):
        try:
            farm = self.service.get_farm(farm_id)
            if farm is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Farm not found",
                )
            return farm
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc


farm_controller = FarmController()
