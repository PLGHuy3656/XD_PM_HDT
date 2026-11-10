"""
Domain Models and Value Objects for Analytics Service.

Defines the core data structures used by analytical routines, ensuring:
- Strict validation of timestamps and values
- Proper segregation between missing data (None) and legitimate zero values
- Representation of domain summaries and time-series buckets
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from app.domain.enums import PeriodEnum, MetricType, AlertSeverity, ClimateStatus


@dataclass(frozen=True)
class TimeWindow:
    """
    Represents an analytical time window.
    [CONFIRMED - Core Domain Model]
    """
    start_time: datetime
    end_time: datetime
    period: PeriodEnum

    def __post_init__(self):
        if self.start_time > self.end_time:
            raise ValueError(f"start_time ({self.start_time}) cannot be after end_time ({self.end_time})")

    @property
    def duration_seconds(self) -> float:
        return (self.end_time - self.start_time).total_seconds()


@dataclass(frozen=True)
class MetricThresholds:
    """
    Defines optimal, tolerable, and physical bounds for an environmental metric.
    [CONFIRMED for Physical Bounds; PROPOSED for exact scoring weights]
    """
    metric: MetricType
    physical_min: float
    physical_max: float
    optimal_min: float
    optimal_max: float
    weight: float = 1.0  # Weight in overall composite score


DEFAULT_THRESHOLDS: Dict[MetricType, MetricThresholds] = {
    MetricType.TEMPERATURE: MetricThresholds(
        metric=MetricType.TEMPERATURE,
        physical_min=-10.0,
        physical_max=60.0,
        optimal_min=27.0,
        optimal_max=31.0,
        weight=0.45,  # Temperature is critical for swiftlet nesting
    ),
    MetricType.HUMIDITY: MetricThresholds(
        metric=MetricType.HUMIDITY,
        physical_min=0.0,
        physical_max=100.0,
        optimal_min=80.0,
        optimal_max=90.0,
        weight=0.45,  # Humidity directly affects nest saliva drying
    ),
    MetricType.CO2: MetricThresholds(
        metric=MetricType.CO2,
        physical_min=0.0,
        physical_max=10000.0,
        optimal_min=0.0,
        optimal_max=1000.0,
        weight=0.10,  # Ventilation proxy
    ),
}


@dataclass
class BirdActivityBucket:
    """
    Aggregated bird entry and exit counts in a specific time bucket.
    [CONFIRMED - SRS 3.9]
    """
    bucket_start: datetime
    label: str
    entries: int = 0
    exits: int = 0

    def __post_init__(self):
        if self.entries < 0:
            raise ValueError(f"entries cannot be negative: {self.entries}")
        if self.exits < 0:
            raise ValueError(f"exits cannot be negative: {self.exits}")

    @property
    def net_flux(self) -> int:
        """Net population difference (entries - exits) in this bucket."""
        return self.entries - self.exits


@dataclass
class BirdPerformanceSummary:
    """
    Aggregated bird activity summary over an evaluation period.
    [CONFIRMED for entries/exits/difference; PROPOSED/APPROXIMATION for return_rate]
    """
    entries: int
    exits: int
    difference: int
    return_rate: Optional[float] = None  # Percentage 0.0 - 100.0, or None if exits == 0
    percentage_change: Optional[float] = None  # Compared to prior period

    def __post_init__(self):
        if self.entries < 0 or self.exits < 0:
            raise ValueError("Entries and exits must be non-negative")
        if self.return_rate is not None and not (0.0 <= self.return_rate <= 100.0):
            raise ValueError(f"return_rate must be between 0.0 and 100.0: got {self.return_rate}")


@dataclass
class MicroclimateZoneScore:
    """
    Microclimate health score and parameter averages for a zone.
    [PROPOSED - UI Contract (analyticsMockData.js)]
    """
    zone_id: str
    zone_name: str
    score: Optional[float]  # 0.0 - 100.0, or None if sensors have no data
    status: ClimateStatus
    avg_temperature: Optional[float] = None
    avg_humidity: Optional[float] = None
    avg_co2: Optional[float] = None

    def __post_init__(self):
        if self.score is not None and not (0.0 <= self.score <= 100.0):
            raise ValueError(f"Microclimate score must be between 0.0 and 100.0: got {self.score}")


@dataclass
class AlertDistribution:
    """
    Distribution of alerts by severity tier.
    [CONFIRMED - Notification/Analytics Contract]
    """
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0

    def __post_init__(self):
        for field_name in ("critical", "high", "medium", "low"):
            val = getattr(self, field_name)
            if val < 0:
                raise ValueError(f"Alert count for {field_name} cannot be negative: {val}")

    @property
    def total(self) -> int:
        return self.critical + self.high + self.medium + self.low


@dataclass
class YieldSummary:
    """
    Periodic harvest yield summary.
    [PROPOSED - Derived from analyticsMockData.js]
    """
    nests: int = 0
    yield_kg: float = 0.0
    yield_change_pct: Optional[float] = None

    def __post_init__(self):
        if self.nests < 0:
            raise ValueError(f"Nests count cannot be negative: {self.nests}")
        if self.yield_kg < 0.0:
            raise ValueError(f"Yield kg cannot be negative: {self.yield_kg}")


@dataclass
class TimeSeriesDataPoint:
    """
    A single point in a time-series curve.
    Distinguishes legitimate 0.0 from missing/null sensor data.
    [CONFIRMED - Architectural Principle]
    """
    timestamp: datetime
    label: str
    value: Optional[float]
    is_missing: bool = False

    def __post_init__(self):
        if self.value is None and not self.is_missing:
            object.__setattr__(self, "is_missing", True)
