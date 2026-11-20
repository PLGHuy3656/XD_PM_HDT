from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# INT01-R1: data provenance labels.
#   PHYSICAL    - declared by firmware as read from a real sensor
#   SIMULATED   - declared by the ESP32 simulator / mock sensor module
#   UNAVAILABLE - no such sensor / no value (never replaced by a default)
#   UNVERIFIED  - a value exists but the sender did not declare its origin (never shown as PHYSICAL)
SensorSource = Literal["PHYSICAL", "SIMULATED", "UNAVAILABLE"]
PROVENANCE_METRIC_KEYS: tuple[str, ...] = (
    "temperature",
    "humidity",
    "co2",
    "lux",
    "audio",
    "networkRssi",
)


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
    # INT01-R1: optional (null = sensor not installed / no reading). Never defaulted to a fake number.
    lux: float | None = Field(
        default=None,
        ge=0.0,
        description="Ambient light level in lux (>= 0); null when no light sensor",
    )
    co2: float | None = Field(
        default=None,
        ge=0.0,
        description="Carbon dioxide concentration in ppm (>= 0); null when no CO2 sensor",
    )
    audioRms: float | None = Field(
        default=None,
        ge=0.0,
        description="Audio RMS amplitude representing bird sound activity (>= 0); null when unavailable",
    )
    audioHealthy: bool | None = Field(
        default=None,
        description="Boolean indicating acoustic sound health flag; null when unavailable",
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


class TelemetryProvenance(BaseModel):
    """INT01-R1 optional, backward-compatible origin declaration sent by the device/simulator."""
    model_config = ConfigDict(extra="forbid", strict=True)

    source: Literal["PHYSICAL", "SIMULATED", "MIXED"]
    sensors: dict[
        Literal["temperature", "humidity", "co2", "lux", "audio", "networkRssi"],
        SensorSource,
    ] = Field(default_factory=dict)


def resolve_metric_sources(
    metrics: TelemetryMetrics,
    state: "DeviceRuntimeState | None",
    provenance: TelemetryProvenance | None,
) -> dict[str, str]:
    """Per-metric source label. A missing value is always UNAVAILABLE; an undeclared value is UNVERIFIED."""
    values = {
        "temperature": metrics.temperature,
        "humidity": metrics.humidity,
        "co2": metrics.co2,
        "lux": metrics.lux,
        "audio": metrics.audioRms if metrics.audioRms is not None else metrics.audioHealthy,
        "networkRssi": state.networkRssi if state is not None else None,
    }
    declared = provenance.sensors if provenance is not None else {}
    out: dict[str, str] = {}
    for key in PROVENANCE_METRIC_KEYS:
        if values[key] is None:
            out[key] = "UNAVAILABLE"
        elif key in declared:
            out[key] = declared[key]
        elif provenance is not None and provenance.source in ("PHYSICAL", "SIMULATED"):
            out[key] = provenance.source
        else:
            out[key] = "UNVERIFIED"
    return out


class TelemetryPayload(BaseModel):
    """Canonical V1 Inbound Telemetry Payload received from device via MQTT."""
    model_config = ConfigDict(extra="forbid", strict=True)

    deviceId: str = Field(..., min_length=1, description="Device identity code")
    metrics: TelemetryMetrics
    actuators: ActuatorState
    state: DeviceRuntimeState
    provenance: TelemetryProvenance | None = None

    @model_validator(mode="after")
    def _drop_values_declared_unavailable(self) -> "TelemetryPayload":
        """A metric declared UNAVAILABLE must not carry a (possibly fabricated) value."""
        if self.provenance is not None:
            s = self.provenance.sensors
            if s.get("co2") == "UNAVAILABLE":
                self.metrics.co2 = None
            if s.get("lux") == "UNAVAILABLE":
                self.metrics.lux = None
            if s.get("audio") == "UNAVAILABLE":
                self.metrics.audioRms = None
                self.metrics.audioHealthy = None
            if s.get("networkRssi") == "UNAVAILABLE":
                self.state.networkRssi = None
        return self


class AcceptedTelemetry(BaseModel):
    """Normalized telemetry record with server-assigned authoritative UTC timestamp."""
    model_config = ConfigDict(extra="forbid")

    device_id: str
    received_at: datetime
    metrics: TelemetryMetrics
    actuators: ActuatorState
    state: DeviceRuntimeState
    farm_id: str | None = None
    provenance: TelemetryProvenance | None = None
