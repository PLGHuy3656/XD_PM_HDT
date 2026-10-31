from pydantic import BaseModel


class DeviceRegistryResponse(BaseModel):
    device_id: str
    node_id: str
    name: str | None = None
    device_type: str | None = None
    farm_id: str
    zone_id: str | None = None
    zone_name: str | None = None
    ip_address: str | None = None
    firmware_version: str | None = None
    is_active: bool = True
    status: str | None = None
    created_at: str | None = None


class DeviceCreateRequest(BaseModel):
    node_id: str
    farm_id: str
    zone_id: str | None = None
    name: str | None = None
    device_type: str = "CONTROLLER"
    firmware_version: str | None = None
    ip_address: str | None = None
