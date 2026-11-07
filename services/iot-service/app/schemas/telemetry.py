from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TelemetryMetrics(BaseModel):
    """Environmental and biological sensor readings."""
    model_config = ConfigDict(extra="forbid", strict=True)

    temperature: float = Field(
        ...,
        ge=-40.0,
        le=85.0,
        description="Temperature in Celsius within valid environmental limits (-40..85 °C)",
    )
    humidity: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Relative humidity in percentage (0..100 %)",
    )
    lux: float = Field(
        ...,
        ge=0.0,
        description="Ambient light level in lux (>= 0)",
    )
    co2: float = Field(
        ...,
        ge=0.0,
        description="Carbon dioxide concentration in ppm (>= 0)",
    )
    audioRms: float = Field(
        ...,
        ge=0.0,
        description="Audio RMS amplitude representing bird sound activity (>= 0)",
    )
    audioHealthy: bool = Field(
        ...,
        description="Boolean indicating acoustic sound health flag",
    )


class ActuatorState(BaseModel):
    """Actuator relay states on the device."""
    model_config = ConfigDict(extra="forbid", strict=True)

    misting: bool = Field(..., description="Misting pump relay state")
    fan: bool = Field(..., description="Exhaust fan relay state")
    heater: bool = Field(..., description="Heater relay state")
    alarm: bool = Field(..., description="Alarm / strobe relay state")


class DeviceRuntimeState(BaseModel):
    """Device runtime operational state and telemetry diagnostics."""
    model_config = ConfigDict(extra="forbid", strict=True)

    mode: Literal["AUTO", "MANUAL"] = Field(
        ...,
        description="Current operating mode: AUTO or MANUAL",
    )
    networkRssi: int | None = Field(
        default=None,
        ge=-120,
        le=0,
        description="Network RSSI in dBm (-120..0)",
    )
    freeHeap: int | None = Field(
        default=None,
        ge=0,
        description="Free memory heap in bytes (>= 0)",
    )


class TelemetryPayload(BaseModel):
    """Canonical V1 Inbound Telemetry Payload received from device via MQTT."""
    model_config = ConfigDict(extra="forbid", strict=True)

    deviceId: str = Field(..., min_length=1, description="Device identity code")
    metrics: TelemetryMetrics
    actuators: ActuatorState
    state: DeviceRuntimeState


class AcceptedTelemetry(BaseModel):
    """Normalized telemetry record with server-assigned authoritative UTC timestamp."""
    model_config = ConfigDict(extra="forbid")

    device_id: str
    received_at: datetime
    metrics: TelemetryMetrics
    actuators: ActuatorState
    state: DeviceRuntimeState
