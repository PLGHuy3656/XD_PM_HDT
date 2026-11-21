from pydantic import BaseModel, Field


class FarmResponse(BaseModel):
    farm_id: str
    farm_code: str
    farm_name: str
    address: str | None = None
    status: str = "ACTIVE"
    approval_status: str = "APPROVED"
    rejection_reason: str | None = None
    zone_count: int = Field(ge=0, default=0)
    device_count: int = Field(ge=0, default=0)


class FarmTechnicianInfo(BaseModel):
    technician_id: str
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    is_primary: bool = False
    assignment_status: str = "ACTIVE"
    assigned_at: str | None = None


class FarmDetailResponse(FarmResponse):
    technicians: list[FarmTechnicianInfo] = Field(default_factory=list)
    owner_name: str | None = None
    owner_phone: str | None = None
    technician_id: str | None = None
    technician_name: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    created_at: str | None = None


class FarmCreateRequest(BaseModel):
    farm_code: str | None = Field(default=None, max_length=100)
    farm_name: str = Field(..., min_length=1, max_length=255)
    address: str | None = None
    status: str = Field(default="ACTIVE", max_length=50)
    owner_id: str | None = None


class FarmUpdateRequest(BaseModel):
    farm_name: str | None = Field(default=None, min_length=1, max_length=255)
    address: str | None = None
    status: str | None = Field(default=None, max_length=50)
    owner_id: str | None = None


class FarmRejectRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=1, max_length=500)
