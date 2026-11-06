from pydantic import BaseModel, Field


class FarmResponse(BaseModel):
    farm_id: str
    farm_code: str
    farm_name: str
    address: str | None = None
    status: str = "ACTIVE"
    zone_count: int = Field(ge=0, default=0)
    device_count: int = Field(ge=0, default=0)


class FarmDetailResponse(FarmResponse):
    owner_name: str | None = None
    owner_phone: str | None = None
    technician_id: str | None = None
    technician_name: str | None = None
    created_at: str | None = None
