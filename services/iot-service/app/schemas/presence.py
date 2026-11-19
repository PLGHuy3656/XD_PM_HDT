import ipaddress
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PresenceStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    STALE = "STALE"


class HeartbeatPayload(BaseModel):
    """Canonical V1 Inbound Heartbeat Payload."""
    model_config = ConfigDict(extra="forbid", strict=True)

    deviceId: str = Field(..., min_length=1, description="Device identity code")
    uptime: int = Field(..., ge=0, description="Uptime in seconds since edge boot (duration, not Unix epoch)")
    ip: str = Field(..., description="Device IP address")
    freeHeap: int = Field(..., ge=0, description="Free memory heap in bytes")
    mockMode: bool = Field(..., description="Whether edge controller is in mock sensor mode")

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        try:
            ipaddress.ip_address(v)
        except ValueError as exc:
            raise ValueError(f"Invalid IP address format: {v}") from exc
        return v


class StatusPayload(BaseModel):
    """Canonical V1 Inbound MQTT Status / LWT Payload."""
    model_config = ConfigDict(extra="forbid", strict=True)

    status: Literal["online", "offline"] = Field(
        ...,
        description="Explicit broker retained status or LWT payload",
    )


class DevicePresence(BaseModel):
    """In-memory runtime tracking model for device presence."""
    model_config = ConfigDict(extra="forbid")

    device_id: str
    status: Literal["ONLINE", "OFFLINE", "STALE"]
    last_seen: datetime | None = None
    last_heartbeat_at: datetime | None = None
    last_status_at: datetime | None = None
    uptime: int | None = None
    ip: str | None = None
    free_heap: int | None = None
    mock_mode: bool | None = None
