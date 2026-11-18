"""
Schemas package export for Analytics Service.
"""
from app.schemas.common import ErrorDetail, ErrorResponse, HealthResponse
from app.schemas.summary import (
    AlertSeverityCount,
    BirdPerformanceResponse,
    FarmAnalyticsSummaryResponse,
    MicroClimateScoreItem,
    YieldSummaryResponse,
)
from app.schemas.trends import (
    AlertTrendItem,
    BirdTrendItem,
    EnvironmentComparisonItem,
    EnvironmentZoneMetrics,
    FarmAnalyticsTrendsResponse,
    HourlyBirdActivityItem,
    YieldTrendItem,
)

__all__ = [
    "HealthResponse",
    "ErrorDetail",
    "ErrorResponse",
    "BirdPerformanceResponse",
    "MicroClimateScoreItem",
    "AlertSeverityCount",
    "YieldSummaryResponse",
    "FarmAnalyticsSummaryResponse",
    "HourlyBirdActivityItem",
    "EnvironmentZoneMetrics",
    "EnvironmentComparisonItem",
    "BirdTrendItem",
    "AlertTrendItem",
    "YieldTrendItem",
    "FarmAnalyticsTrendsResponse",
]
