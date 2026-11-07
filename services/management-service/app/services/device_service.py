from app.repositories.device_repository import DeviceRepository, device_repository


class DeviceService:
    def __init__(self, repository: DeviceRepository | None = None):
        self.repository = repository or device_repository

    def list_devices(self, farm_id: str | None = None, zone_id: str | None = None):
        return self.repository.list_devices(farm_id=farm_id, zone_id=zone_id)

    def get_device(self, device_id: str):
        if not device_id:
            raise ValueError("device_id is required")
        return self.repository.get_device_by_id(device_id)


device_service = DeviceService()
