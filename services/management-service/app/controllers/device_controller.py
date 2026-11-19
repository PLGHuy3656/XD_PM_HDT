from fastapi import HTTPException, status
from app.services.device_service import DeviceService, device_service


class DeviceController:
    def __init__(self, service: DeviceService | None = None):
        self.service = service or device_service

    def list_devices(self, farm_id: str | None = None, zone_id: str | None = None):
        try:
            return self.service.list_devices(farm_id=farm_id, zone_id=zone_id)
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

    def create_device(
        self,
        node_id: str,
        farm_uuid: str,
        zone_id: str | None = None,
        name: str | None = None,
        device_type: str = "CONTROLLER",
        firmware_version: str | None = None,
        ip_address: str | None = None,
    ):
        try:
            return self.service.create_device(
                node_id=node_id,
                farm_uuid=farm_uuid,
                zone_id=zone_id,
                name=name,
                device_type=device_type,
                firmware_version=firmware_version,
                ip_address=ip_address,
            )
        except ValueError as exc:
            code = status.HTTP_409_CONFLICT if "already exists" in str(exc) else status.HTTP_400_BAD_REQUEST
            raise HTTPException(status_code=code, detail=str(exc)) from exc

    def update_device(
        self,
        device_id: str,
        name: str | None = None,
        device_type: str | None = None,
        zone_id: str | None = None,
        firmware_version: str | None = None,
        ip_address: str | None = None,
        is_active: bool | None = None,
    ):
        try:
            device = self.service.update_device(
                device_id=device_id,
                name=name,
                device_type=device_type,
                zone_id=zone_id,
                firmware_version=firmware_version,
                ip_address=ip_address,
                is_active=is_active,
            )
            if device is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found in registry")
            return device
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    def delete_device(self, device_id: str):
        deleted = self.service.delete_device(device_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found in registry")
        return {"status": "deleted", "device_id": device_id}


device_controller = DeviceController()
