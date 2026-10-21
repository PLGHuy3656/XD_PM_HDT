from fastapi import HTTPException, status

from app.services.technician_service import TechnicianService


class TechnicianController:
    def __init__(
        self,
        service: TechnicianService | None = None,
    ):
        self.service = service or TechnicianService()

    def get_profile(self, technician_id: str):
        try:
            return self.service.get_profile(technician_id)

        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        except NotImplementedError as exc:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=str(exc),
            ) from exc

    def get_assigned_farms(self, technician_id: str):
        try:
            return self.service.get_assigned_farms(technician_id)

        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        except NotImplementedError as exc:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=str(exc),
            ) from exc

    def get_assigned_farm_detail(
        self,
        technician_id: str,
        farm_id: str,
    ):
        try:
            return self.service.get_assigned_farm_detail(
                technician_id,
                farm_id,
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        except NotImplementedError as exc:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=str(exc),
            ) from exc


technician_controller = TechnicianController()