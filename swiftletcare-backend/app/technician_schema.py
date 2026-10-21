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
    status: str
    zone_count: int = Field(ge=0)
    device_count: int = Field(ge=0)


class TechnicianFarmDetailResponse(AssignedFarmResponse):
    owner_name: str | None = None
    owner_phone: str | None = None