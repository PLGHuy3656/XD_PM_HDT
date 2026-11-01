from app.repositories.device_repository import DeviceRepository, device_repository


class DeviceService:
    def __init__(self, repository: DeviceRepository | None = None):
        self.repository = repository or device_repository

    def list_devices(
        self,
        farm_id: str | None = None,
        zone_id: str | None = None,
        farm_ids: list[str] | None = None,
    ):
        return self.repository.list_devices(
            farm_id=farm_id,
            zone_id=zone_id,
            farm_ids=farm_ids,
        )

    def get_device(self, device_id: str):
        if not device_id:
            raise ValueError("device_id is required")
        return self.repository.get_device_by_id(device_id)

    def update_device_zone(
        self,
        device_id: str,
        farm_id: str,
        zone_id: str,
    ):
        if not device_id or not farm_id or not zone_id:
            raise ValueError("device_id, farm_id, and zone_id are required")
        return self.repository.update_device_zone(
            device_id,
            farm_id,
            zone_id,
        )


device_service = DeviceService()
