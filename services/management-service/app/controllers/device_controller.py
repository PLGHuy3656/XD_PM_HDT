from fastapi import HTTPException, status
from app.services.device_service import DeviceService, device_service


class DeviceController:
    def __init__(self, service: DeviceService | None = None):
        self.service = service or device_service

    def list_devices(
        self,
        farm_id: str | None = None,
        zone_id: str | None = None,
        farm_ids: list[str] | None = None,
    ):
        try:
            return self.service.list_devices(
                farm_id=farm_id,
                zone_id=zone_id,
                farm_ids=farm_ids,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    def get_device(self, device_id: str):
        try:
            device = self.service.get_device(device_id)
            if device is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Device not found in registry",
                )
            return device
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    def update_device_zone(
        self,
        device_id: str,
        farm_id: str,
        zone_id: str,
    ):
        try:
            updated = self.service.update_device_zone(
                device_id,
                farm_id,
                zone_id,
            )
            if not updated:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Device or zone not found in the selected farm",
                )
            return {"status": "updated"}
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc


device_controller = DeviceController()
