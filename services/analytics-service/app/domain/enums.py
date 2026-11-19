"""
Domain Enums for Analytics Service.

Defines periods, metrics, and severity tiers consistent with:
- SRS Section 3.9 (Analytics & Reports)
- API Gateway routes (/api/v1/analytics/...)
- Frontend analytics contract (analyticsMockData.js)
"""
from enum import Enum


class PeriodEnum(str, Enum):
    """
    Time aggregation periods supported by analytics.
    [CONFIRMED - SRS 3.9 & Gateway Contract]
    """
    HOUR = "hour"
    DAY = "day"
    TODAY = "today"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"

    @classmethod
    def normalize(cls, value: str) -> "PeriodEnum":
        """Normalize period string, mapping 'today' to 'day' where appropriate."""
        val = value.lower().strip()
        return cls(val)


class MetricType(str, Enum):
    """
    Types of metrics tracked across the swiftlet farm.
    [CONFIRMED - SRS 3.9 & IoT Telemetry Specs]
    """
    # Continuous Environmental Sensors
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    CO2 = "co2"
    LIGHT = "light"
    AUDIO = "audio"

    # Discrete Event Counters
    BIRD_ENTRIES = "bird_entries"
    BIRD_EXITS = "bird_exits"
    ALERTS = "alerts"

    # Periodic Harvest / Yield
    YIELD_KG = "yield_kg"


class AlertSeverity(str, Enum):
    """
    Alert severity classifications.
    [CONFIRMED - Notification & Analytics Contract]
    """
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ClimateStatus(str, Enum):
    """
    Health classification status for zone microclimate scores.
    [PROPOSED - UI Contract (analyticsMockData.js)]
    """
    OPTIMAL = "optimal"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"
