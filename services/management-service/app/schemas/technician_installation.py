from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


TechnicianInstallationStatus = Literal[
    "REGISTERED",
    "CONFIGURED",
    "ACTIVATED",
    "VALIDATED",
    "HANDED_OVER",
]


class TechnicianInstallationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(min_length=1, max_length=100)
    farm_id: UUID
    zone_id: UUID | None = None
    name: str | None = Field(default=None, max_length=255)
    device_type: str = Field(default="ENVIRONMENT_MONITOR", max_length=100)
    firmware_version: str | None = Field(default=None, max_length=50)
    ip_address: str | None = Field(default=None, max_length=50)


class TechnicianInstallationConfigurationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    configuration: dict[str, Any] = Field(min_length=1)


class TechnicianInstallationResponse(BaseModel):
    installation_id: UUID
    device_id: UUID
    node_id: str
    technician_id: UUID
    farm_id: UUID
    zone_id: UUID | None
    name: str | None
    device_type: str
    firmware_version: str | None
    ip_address: str | None
    is_active: bool
    status: TechnicianInstallationStatus
    configuration: dict[str, Any]
    validation_report: dict[str, Any]
    farm_zone_linked: bool
    created_at: str
    updated_at: str
    activated_at: str | None
    validated_at: str | None
    handed_over_at: str | None


class TechnicianInstallationValidationChecks(BaseModel):
    device_registered: bool
    device_activated: bool
    farm_zone_linked: bool
    configuration_present: bool
    connectivity: bool


class TechnicianInstallationValidationResponse(BaseModel):
    installation: TechnicianInstallationResponse
    passed: bool
    checked_at: str
    checks: TechnicianInstallationValidationChecks
    failure_reasons: list[str]
