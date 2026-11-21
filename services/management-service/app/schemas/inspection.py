from typing import Literal

from pydantic import BaseModel, Field, field_validator

InspectionPriority = Literal["LOW", "MEDIUM", "HIGH", "URGENT"]
InspectionStatus = Literal["NEW", "ACCEPTED", "IN_PROGRESS", "COMPLETED", "CANCELLED"]


class InspectionRequestCreate(BaseModel):
    farm_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    priority: InspectionPriority = "MEDIUM"
    zone_id: str | None = None
    device_id: str | None = None


class InspectionAssignRequest(BaseModel):
    technician_id: str = Field(..., min_length=1, max_length=100)


class InspectionNoteRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class InspectionCompleteRequest(BaseModel):
    result_note: str = Field(..., min_length=1, max_length=4000)

    @field_validator("result_note", mode="before")
    @classmethod
    def strip_result_note(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class InspectionHistoryItem(BaseModel):
    from_status: str | None = None
    to_status: str
    action: str
    actor_id: str | None = None
    actor_name: str | None = None
    note: str | None = None
    created_at: str | None = None


class InspectionRequestResponse(BaseModel):
    id: str
    request_code: str
    farm_id: str
    farm_name: str | None = None
    zone_id: str | None = None
    zone_name: str | None = None
    device_id: str | None = None
    device_name: str | None = None
    title: str
    description: str | None = None
    priority: str
    status: str
    requested_by: str
    requested_by_name: str | None = None
    assigned_technician_id: str | None = None
    assigned_technician_name: str | None = None
    result_note: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    accepted_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    cancelled_at: str | None = None
    history: list[InspectionHistoryItem] | None = None
