"""Internal service-to-service API schemas (CP11.4-B1-R2-MGMT)."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class InternalDeviceMetadataResponse(BaseModel):
    """Authoritative Device Metadata Contract for internal microservices (e.g., IoT Service).

    Provides minimal, validated device-to-farm boundary mapping without exposing
    owner personal identifiable information (PII).
    Supports both camelCase and snake_case field resolution.
    """
    model_config = ConfigDict(populate_by_name=True)

    deviceId: str = Field(..., description="Canonical device UUID")
    nodeId: str = Field(..., description="Authoritative MQTT device identifier")
    farmId: str = Field(..., description="Canonical farm UUID")
    status: str = Field(..., description="Device operational status (e.g. ACTIVE, DISABLED)")
    isActive: bool = Field(True, description="Whether device is active in registry")
    updatedAt: Optional[str] = Field(None, description="ISO 8601 timestamp of last metadata modification")
    metadataVersion: Optional[int] = Field(None, description="Monotonic or epoch version for cache consistency")

    # Snake_case compatibility aliases
    device_id: Optional[str] = None
    node_id: Optional[str] = None
    farm_id: Optional[str] = None
    is_active: Optional[bool] = None
    updated_at: Optional[str] = None
    metadata_version: Optional[int] = None

    def model_post_init(self, __context) -> None:
        if self.device_id is None:
            self.device_id = self.deviceId
        if self.node_id is None:
            self.node_id = self.nodeId
        if self.farm_id is None:
            self.farm_id = self.farmId
        if self.is_active is None:
            self.is_active = self.isActive
        if self.updated_at is None:
            self.updated_at = self.updatedAt
        if self.metadata_version is None:
            self.metadata_version = self.metadataVersion


class InternalFarmRecipientsResponse(BaseModel):
    """Authoritative farm-to-recipient mapping for Notification Service (AUD-C-02)."""
    farm_id: str
    farm_code: str
    owner_id: Optional[str] = None
    technician_ids: list[str] = Field(default_factory=list)
