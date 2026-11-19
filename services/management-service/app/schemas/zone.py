from pydantic import BaseModel, Field


class ZoneResponse(BaseModel):
    zone_id: str
    farm_id: str
    zone_code: str
    name: str
    device_count: int = Field(ge=0, default=0)
    created_at: str | None = None


class ZoneCreateRequest(BaseModel):
    zone_code: str | None = Field(default=None, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)


class ZoneUpdateRequest(BaseModel):
    zone_code: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=255)
