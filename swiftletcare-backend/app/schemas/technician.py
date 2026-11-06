from pydantic import BaseModel, Field


class TechnicianProfileResponse(BaseModel):
    technician_id: str
    full_name: str
    email: str
    phone: str | None = None
    status: str = "ACTIVE"


class AssignedFarmResponse(BaseModel):
    farm_id: str
    farm_code: str
    farm_name: str
    address: str | None = None
    status: str | None = None
    zone_count: int = Field(ge=0)
    device_count: int = Field(ge=0)


class TechnicianFarmDetailResponse(AssignedFarmResponse):
    owner_name: str | None = None
    owner_phone: str | None = None


class TechnicianDeviceResponse(BaseModel):
    device_id: str
    node_id: str
    name: str | None = None
    device_type: str | None = None
    type_label: str | None = None

    farm_id: str
    zone_id: str | None = None
    zone_name: str | None = None

    status: str
    rssi: int | None = None
    mqtt_status: str

    ip_address: str | None = None
    firmware_version: str | None = None

    last_seen: str | None = None


class TechnicianDeviceDetailResponse(TechnicianDeviceResponse):
    pass

class TechnicianDashboardResponse(BaseModel):
    technician_id: str

    assigned_farm_count: int = Field(ge=0)
    zone_count: int = Field(ge=0)
    device_count: int = Field(ge=0)

    online_device_count: int = Field(ge=0)
    offline_device_count: int = Field(ge=0)