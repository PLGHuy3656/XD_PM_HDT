from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Metrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature: float = Field(ge=-20, le=80)
    humidity: float = Field(ge=0, le=100)
    lux: float = Field(ge=0, le=100000)
    co2: float = Field(ge=0, le=100000)
    audioRms: float = Field(ge=0)
    audioHealthy: bool


class Actuators(BaseModel):
    model_config = ConfigDict(extra="forbid")

    misting: bool
    fan: bool
    heater: bool
    alarm: bool


class DeviceState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["AUTO", "MANUAL"]
    networkRssi: int | None = Field(default=None, ge=-120, le=0)
    freeHeap: int | None = Field(default=None, ge=0)


class TelemetryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodeId: str = Field(min_length=1, max_length=100)
    timestamp: int = Field(ge=1)
    metrics: Metrics
    actuators: Actuators
    state: DeviceState