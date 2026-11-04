import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RelayTarget = Literal["misting", "fan", "heater", "alarm"]
CommandAction = Literal["SET_RELAY", "UPDATE_THRESHOLDS"]
CommandStatus = Literal["PENDING", "PUBLISHED", "SUCCESS", "FAILED", "ERROR"]
AckStatus = Literal["SUCCESS", "FAILED", "ERROR"]
ControlMode = Literal["AUTO", "MANUAL"]


class SetRelayPayload(BaseModel):
    """Canonical V1 SET_RELAY command payload published to ESP32."""
    model_config = ConfigDict(extra="forbid", strict=True)

    commandId: str = Field(..., description="Unique UUID string identifying this command")
    action: Literal["SET_RELAY"] = "SET_RELAY"
    target: RelayTarget = Field(..., description="Actuator target relay")
    state: Literal[0, 1] = Field(..., description="0 = OFF, 1 = ON")


class UpdateThresholdsPayload(BaseModel):
    """Canonical V1 UPDATE_THRESHOLDS command payload published to ESP32."""
    model_config = ConfigDict(extra="forbid", strict=True)

    commandId: str = Field(..., description="Unique UUID string identifying this command")
    action: Literal["UPDATE_THRESHOLDS"] = "UPDATE_THRESHOLDS"
    targetTemp: float = Field(
        ...,
        ge=-20.0,
        le=60.0,
        description="Target microclimate temperature in °C (-20..60)",
    )
    targetHum: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Target microclimate relative humidity in % (0..100)",
    )
    isAutoMode: bool = Field(
        ...,
        description="True for local AUTO rule engine, False for MANUAL override",
    )


class AckPayload(BaseModel):
    """Canonical V1 command execution acknowledgment received from ESP32."""
    model_config = ConfigDict(extra="forbid", strict=True)

    commandId: str = Field(..., description="UUID matching the original command")
    deviceId: str = Field(..., min_length=1, description="Device identity code")
    status: AckStatus = Field(..., description="Execution outcome: SUCCESS, FAILED, or ERROR")
    mode: ControlMode = Field(..., description="Operating mode on the device: AUTO or MANUAL")
    message: str | None = Field(default=None, description="Diagnostic human-readable message")

    @field_validator("commandId")
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        try:
            uuid.UUID(v)
        except (ValueError, AttributeError) as exc:
            raise ValueError(f"commandId must be a valid UUID string: {v}") from exc
        return v


class DeviceCommand(BaseModel):
    """Runtime tracking record for device commands."""
    model_config = ConfigDict(extra="forbid")

    command_id: str
    device_id: str
    action: CommandAction
    payload: dict[str, Any]
    status: CommandStatus
    created_at: datetime
    published_at: datetime | None = None
    acknowledged_at: datetime | None = None
    ack_status: AckStatus | None = None
    ack_message: str | None = None
    ack_mode: ControlMode | None = None
