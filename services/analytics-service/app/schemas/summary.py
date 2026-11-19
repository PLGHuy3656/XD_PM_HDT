"""
Pydantic DTOs for Farm Analytics Summary endpoint.
Follows UI contract (analyticsMockData.js) and Gateway forwarding specs.
Ensures missing data is serialized as JSON null, never coerced to 0.
"""
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BirdPerformanceResponse(BaseModel):
    """
    Bird activity and flux summary.
    [CONFIRMED for entries/exits/difference; PROPOSED for returnRate]
    """
    entries: int = Field(..., description="Total bird entries in period")
    exits: int = Field(..., description="Total bird exits in period")
    difference: int = Field(..., description="Net bird difference (entries - exits)")
    returnRate: Optional[float] = Field(
        None,
        description="Return rate percentage. Serializes to null when exits == 0 (undefined baseline)",
    )
    change: Optional[float] = Field(
        None,
        description="Percentage change vs prior period. Serializes to null when prior entries == 0 (undefined baseline)",
    )

    model_config = ConfigDict(populate_by_name=True)


class MicroClimateScoreItem(BaseModel):
    """
    Zone microclimate score item.
    [PROPOSED - UI Contract]
    """
    id: str = Field(..., description="Zone identifier")
    name: str = Field(..., description="Zone human-readable name")
    score: Optional[float] = Field(
        None,
        description="Score between 0-100. Serializes to null if sensor data is unavailable",
    )
    status: str = Field(..., description="Status label: 'optimal', 'warning', 'critical', or 'unknown'")

    model_config = ConfigDict(populate_by_name=True)


class AlertSeverityCount(BaseModel):
    """
    Count of alerts by severity.
    [CONFIRMED - Notification/Analytics Contract]
    """
    severity: str = Field(..., description="Severity tier: CRITICAL, HIGH, MEDIUM, LOW")
    count: int = Field(..., ge=0, description="Total alerts in this tier")


class YieldSummaryResponse(BaseModel):
    """
    Periodic harvest yield summary.
    [PROPOSED - UI Contract]
    """
    totalNests: int = Field(..., ge=0, description="Total active nests in farm")
    harvestedNests: int = Field(..., ge=0, description="Nests harvested in this period")
    currentYield: float = Field(..., ge=0.0, description="Yield in kg for current period")
    previousYield: Optional[float] = Field(None, ge=0.0, description="Yield in kg for previous period")
    yieldChange: Optional[float] = Field(
        None,
        description="Percentage change in yield. Serializes to null when previousYield == 0",
    )

    model_config = ConfigDict(populate_by_name=True)


class FarmAnalyticsSummaryResponse(BaseModel):
    """
    Complete response payload for GET /api/v1/analytics/farms/{farm_id}/summary.
    """
    farmId: str
    farmName: str
    period: str
    birdPerformance: BirdPerformanceResponse
    microClimateScores: List[MicroClimateScoreItem]
    alertDistribution: List[AlertSeverityCount]
    yieldSummary: Optional[YieldSummaryResponse] = None
    hasDataGaps: bool = Field(
        False,
        description="True if any sensor outages or unobserved intervals were detected",
    )

    model_config = ConfigDict(populate_by_name=True)
