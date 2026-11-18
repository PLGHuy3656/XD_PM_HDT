from fastapi import HTTPException, status
from app.services.farm_service import FarmService, farm_service


class FarmController:
    def __init__(self, service: FarmService | None = None):
        self.service = service or farm_service

    def list_farms(self, current_user: dict | None = None):
        try:
            return self.service.list_farms(current_user)
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

    def create_farm(
        self,
        farm_code: str,
        farm_name: str,
        address: str | None = None,
        status_val: str = "ACTIVE",
        owner_id: str | None = None,
    ):
        try:
            return self.service.create_farm(
                farm_code=farm_code,
                farm_name=farm_name,
                address=address,
                status=status_val,
                owner_id=owner_id,
            )
        except ValueError as exc:
            code = status.HTTP_409_CONFLICT if "already exists" in str(exc) else status.HTTP_400_BAD_REQUEST
            raise HTTPException(status_code=code, detail=str(exc)) from exc

    def update_farm(
        self,
        farm_id: str,
        farm_name: str | None = None,
        address: str | None = None,
        status_val: str | None = None,
        owner_id: str | None = None,
    ):
        try:
            farm = self.service.update_farm(
                farm_id=farm_id,
                farm_name=farm_name,
                address=address,
                status=status_val,
                owner_id=owner_id,
            )
            if farm is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
            return farm
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    def delete_farm(self, farm_id: str):
        deleted = self.service.delete_farm(farm_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
        return {"status": "deleted", "farm_id": farm_id}


farm_controller = FarmController()
