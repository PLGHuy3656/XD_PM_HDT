from pydantic import BaseModel, Field


class ZoneResponse(BaseModel):
    zone_id: str
    farm_id: str
    zone_code: str
    name: str
    device_count: int = Field(ge=0, default=0)
    created_at: str | None = None
