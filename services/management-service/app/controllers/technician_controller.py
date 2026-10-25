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
            profile = self.service.get_profile(technician_id)

            if profile is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Technician not found",
                )

            return profile

        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    def get_assigned_farms(self, technician_id: str):
        try:
            return self.service.get_assigned_farms(
                technician_id,
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    def get_assigned_farm_detail(
        self,
        technician_id: str,
        farm_id: str,
    ):
        try:
            farm = self.service.get_assigned_farm_detail(
                technician_id,
                farm_id,
            )

            if farm is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Farm not found or not assigned to technician",
                )

            return farm

        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    def get_assigned_farm_devices(
        self,
        technician_id: str,
        farm_id: str,
    ):
        try:
            return self.service.get_assigned_farm_devices(
                technician_id,
                farm_id,
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    def get_assigned_farm_device_detail(
        self,
        technician_id: str,
        farm_id: str,
        device_id: str,
    ):
        try:
            device = self.service.get_assigned_farm_device_detail(
                technician_id,
                farm_id,
                device_id,
            )

            if device is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        "Device not found or not assigned "
                        "to technician"
                    ),
                )

            return device

        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    def get_dashboard_summary(
        self,
        technician_id: str,
    ):
        try:
            return self.service.get_dashboard_summary(
                technician_id,
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc


technician_controller = TechnicianController()
