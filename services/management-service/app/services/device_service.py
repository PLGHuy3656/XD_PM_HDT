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

    def get_internal_metadata(self, identifier: str) -> dict | None:
        if not identifier or not str(identifier).strip():
            raise ValueError("Device identifier cannot be empty")
        return self.repository.get_internal_device_metadata(identifier)

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
        if not node_id or not node_id.strip():
            raise ValueError("node_id is required")
        if not farm_uuid:
            raise ValueError("farm_id is required")
        return self.repository.create_device(
            node_id=node_id,
            farm_uuid=farm_uuid,
            zone_id=zone_id,
            name=name,
            device_type=device_type,
            firmware_version=firmware_version,
            ip_address=ip_address,
        )

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
        if not device_id:
            raise ValueError("device_id is required")
        return self.repository.update_device(
            device_id=device_id,
            name=name,
            device_type=device_type,
            zone_id=zone_id,
            firmware_version=firmware_version,
            ip_address=ip_address,
            is_active=is_active,
        )

    def delete_device(self, device_id: str) -> bool:
        if not device_id:
            raise ValueError("device_id is required")
        return self.repository.delete_device(device_id)


device_service = DeviceService()
