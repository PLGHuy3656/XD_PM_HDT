"""
Pydantic DTOs for Analytics Trends endpoints (/trends).
Ensures all continuous sensor and event metrics serialize missing gaps to JSON null.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class HourlyBirdActivityItem(BaseModel):
    """
    Bird entries and exits per time slot.
    """
    label: str
    entries: Optional[int] = Field(
        None,
        description="Entry events. Serializes to null if coverage was missing/outage",
    )
    exits: Optional[int] = Field(
        None,
        description="Exit events. Serializes to null if coverage was missing/outage",
    )

    model_config = ConfigDict(populate_by_name=True)


class EnvironmentZoneMetrics(BaseModel):
    """
    Microclimate readings for a zone in a given time slot.
    Never coerces missing sensor readings to 0.0.
    """
    temperature: Optional[float] = Field(None, description="Temperature in °C (null if sensor offline)")
    humidity: Optional[float] = Field(None, description="Humidity in % (null if sensor offline)")
    co2: Optional[float] = Field(None, description="CO2 in ppm (null if sensor offline)")
    light: Optional[float] = Field(None, description="Light in lux (null if sensor offline)")
    audio: Optional[float] = Field(None, description="Audio in dB (null if sensor offline)")

    model_config = ConfigDict(populate_by_name=True)


class EnvironmentComparisonItem(BaseModel):
    """
    Comparison of zone metrics across a single time slot.
    """
    label: str
    zones: Dict[str, EnvironmentZoneMetrics] = Field(
        default_factory=dict,
        description="Mapping of zone_id -> EnvironmentZoneMetrics",
    )

    model_config = ConfigDict(populate_by_name=True)


class BirdTrendItem(BaseModel):
    """
    Day/Month aggregated bird trend.
    """
    label: str
    entries: Optional[int] = Field(None, description="Total entries (null if outage)")
    exits: Optional[int] = Field(None, description="Total exits (null if outage)")

    model_config = ConfigDict(populate_by_name=True)


class AlertTrendItem(BaseModel):
    """
    Severity distribution of alerts across a time bucket.
    """
    label: str
    critical: Optional[int] = Field(None, description="Critical count (null if outage)")
    high: Optional[int] = Field(None, description="High count (null if outage)")
    medium: Optional[int] = Field(None, description="Medium count (null if outage)")
    low: Optional[int] = Field(None, description="Low count (null if outage)")

    model_config = ConfigDict(populate_by_name=True)


class YieldTrendItem(BaseModel):
    """
    Harvest yield data point across months.
    """
    label: str
    value: Optional[float] = Field(None, description="Harvested yield in kg")

    model_config = ConfigDict(populate_by_name=True)


class FarmAnalyticsTrendsResponse(BaseModel):
    """
    Response payload for GET /api/v1/analytics/farms/{farm_id}/trends
    and GET /api/v1/analytics/trends (global admin).
    """
    farmId: Optional[str] = None
    farmName: Optional[str] = None
    period: str
    hourlyBirdActivity: List[HourlyBirdActivityItem] = Field(default_factory=list)
    environmentComparison: List[EnvironmentComparisonItem] = Field(default_factory=list)
    birdTrendAnalytics: List[BirdTrendItem] = Field(default_factory=list)
    alertTrend: List[AlertTrendItem] = Field(default_factory=list)
    yieldTrend: List[YieldTrendItem] = Field(default_factory=list)
    hasDataGaps: bool = Field(False, description="Flag indicating presence of unobserved or missing intervals")

    model_config = ConfigDict(populate_by_name=True)
