from datetime import date
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


AnalyticsPeriod = Literal["1h", "6h", "24h", "7d", "30d"]
HarvestPeriod = Literal["30d", "90d", "365d"]


class MetricStatistics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    average: float | None
    minimum: float | None
    maximum: float | None


class TelemetryAnalyticsPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: str
    samples: int
    temperature: MetricStatistics
    humidity: MetricStatistics
    co2: MetricStatistics
    lux: MetricStatistics
    audio_rms: MetricStatistics


class TelemetryAnalyticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: AnalyticsPeriod
    start: str
    end: str
    bucket: Literal["minute", "hour", "day"]
    device_count: int
    sample_count: int
    summary: dict[str, MetricStatistics]
    series: list[TelemetryAnalyticsPoint]


class AICountSnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    camera_id: str = Field(alias="cameraId", min_length=1, max_length=100)
    timestamp: int = Field(ge=1, le=4102444800)
    entry_count: int = Field(alias="entryCount", ge=0)
    exit_count: int = Field(alias="exitCount", ge=0)
    net_change: int = Field(alias="netChange")

    @model_validator(mode="after")
    def net_change_matches_counters(self) -> Self:
        if self.net_change != self.entry_count - self.exit_count:
            raise ValueError("netChange must equal entryCount - exitCount")
        return self


class BirdAnalyticsPoint(BaseModel):
    timestamp: str
    entries: int
    exits: int
    net_change: int


class BirdAnalyticsResponse(BaseModel):
    period: AnalyticsPeriod
    start: str
    end: str
    camera_count: int
    entries: int
    exits: int
    net_change: int
    series: list[BirdAnalyticsPoint]


class HarvestRecordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    farm_id: UUID
    zone_id: UUID | None = None
    harvest_date: date
    nest_count: int = Field(ge=0)
    yield_kg: Decimal = Field(ge=0, max_digits=12, decimal_places=3)
    notes: str | None = Field(default=None, max_length=2000)


class HarvestRecordResponse(BaseModel):
    id: UUID
    farm_id: UUID
    zone_id: UUID | None
    harvest_date: date
    nest_count: int
    yield_kg: float
    notes: str | None
    created_at: str


class HarvestAnalyticsResponse(BaseModel):
    period: HarvestPeriod
    start: str
    end: str
    record_count: int
    nest_count: int
    yield_kg: float
    previous_yield_kg: float
    yield_change_percent: float | None
    trend: list[dict]
    zones: list[dict]
    records: list[HarvestRecordResponse]


class AnalyticsAlertResponse(BaseModel):
    id: UUID
    node_id: str
    farm_name: str
    zone_name: str | None
    alert_type: Literal["threshold_exceeded", "anomaly_detected"]
    metric: Literal["temperature", "humidity", "co2", "lux"]
    value: float
    threshold: float | None
    direction: str
    baseline: dict
    opened_at: str
    resolved_at: str | None
