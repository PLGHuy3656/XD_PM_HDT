"""
Analytics Application Service.

Orchestrates data retrieval from repository ports and coordinates domain formulas.
Separates application use cases from FastAPI controllers/routers.
"""
from typing import Optional

from app.domain.enums import AlertSeverity, MetricType, PeriodEnum
from app.domain.formulas import (
    calculate_alert_distribution,
    calculate_bird_performance,
    calculate_microclimate_score,
    calculate_yield_summary,
)
from app.ports.analytics_repository import IAnalyticsRepository
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


class FarmNotFoundError(Exception):
    """Raised when the requested farm does not exist."""
    pass


class InvalidPeriodError(Exception):
    """Raised when an invalid period string is requested."""
    pass


class AnalyticsService:
    """
    Application service orchestrating analytics workflows.
    """

    def __init__(self, repository: IAnalyticsRepository):
        self.repository = repository

    def _parse_period(self, period_str: str) -> PeriodEnum:
        """Validates and normalizes period string to PeriodEnum."""
        try:
            return PeriodEnum.normalize(period_str)
        except (ValueError, KeyError):
            raise InvalidPeriodError(
                f"Invalid period '{period_str}'. Supported periods: hour, day, today, week, month, year"
            )

    async def get_farm_summary(
        self,
        farm_id: str,
        period_str: str = "day",
    ) -> FarmAnalyticsSummaryResponse:
        """
        Retrieves farm analytics summary for the specified evaluation period.
        """
        # 1. Validate Farm Existence
        farm_meta = await self.repository.get_farm_metadata(farm_id)
        if not farm_meta:
            raise FarmNotFoundError(f"Farm with id '{farm_id}' was not found.")

        # 2. Parse & Validate Period
        period = self._parse_period(period_str)

        # 3. Retrieve raw telemetry & events from repository port
        buckets, prev_entries, coverage_map = await self.repository.get_bird_activity_buckets(farm_id, period)
        zone_climate_list = await self.repository.get_zone_climate_averages(farm_id, period)
        alerts_list = await self.repository.get_alerts(farm_id, period)
        yield_raw = await self.repository.get_yield_data(farm_id, period)

        # 4. Domain Calculations (Coordination via pure formulas)
        # 4a. Bird Performance
        total_entries = sum(b.entries for b in buckets)
        total_exits = sum(b.exits for b in buckets)
        bird_perf = calculate_bird_performance(
            entries=total_entries,
            exits=total_exits,
            previous_entries=prev_entries,
        )

        # 4b. Zone Microclimate Scores [PROPOSED]
        microclimate_items = []
        has_sensor_gaps = False

        for z in zone_climate_list:
            zone_id = z["zone_id"]
            zone_name = z["zone_name"]
            score_obj = calculate_microclimate_score(
                zone_id=zone_id,
                zone_name=zone_name,
                avg_temperature=z.get("avg_temperature"),
                avg_humidity=z.get("avg_humidity"),
                avg_co2=z.get("avg_co2"),
            )
            if score_obj.score is None:
                has_sensor_gaps = True

            microclimate_items.append(
                MicroClimateScoreItem(
                    id=zone_id,
                    name=zone_name,
                    score=score_obj.score,
                    status=score_obj.status.value,
                )
            )

        # 4c. Alert Distribution
        alert_dist = calculate_alert_distribution(alerts_list)
        alert_counts = [
            AlertSeverityCount(severity=AlertSeverity.CRITICAL.value, count=alert_dist.critical),
            AlertSeverityCount(severity=AlertSeverity.HIGH.value, count=alert_dist.high),
            AlertSeverityCount(severity=AlertSeverity.MEDIUM.value, count=alert_dist.medium),
            AlertSeverityCount(severity=AlertSeverity.LOW.value, count=alert_dist.low),
        ]

        # 4d. Yield Summary [PROPOSED]
        yield_resp: Optional[YieldSummaryResponse] = None
        if yield_raw:
            y_summary = calculate_yield_summary(
                nests=yield_raw.get("total_nests", 0),
                yield_kg=yield_raw.get("current_yield", 0.0),
                previous_yield_kg=yield_raw.get("previous_yield"),
            )
            yield_resp = YieldSummaryResponse(
                totalNests=y_summary.nests,
                harvestedNests=yield_raw.get("harvested_nests", 0),
                currentYield=y_summary.yield_kg,
                previousYield=yield_raw.get("previous_yield"),
                yieldChange=y_summary.yield_change_pct,
            )

        # 4e. Detect data coverage gaps
        if coverage_map and any(not is_healthy for is_healthy in coverage_map.values()):
            has_sensor_gaps = True

        return FarmAnalyticsSummaryResponse(
            farmId=farm_id,
            farmName=farm_meta["name"],
            period=period.value,
            birdPerformance=BirdPerformanceResponse(
                entries=bird_perf.entries,
                exits=bird_perf.exits,
                difference=bird_perf.difference,
                returnRate=bird_perf.return_rate,
                change=bird_perf.percentage_change,
            ),
            microClimateScores=microclimate_items,
            alertDistribution=alert_counts,
            yieldSummary=yield_resp,
            hasDataGaps=has_sensor_gaps,
        )

    async def get_trends(
        self,
        farm_id: Optional[str] = None,
        period_str: str = "today",
        zone_id: Optional[str] = None,
        metric_str: Optional[str] = None,
    ) -> FarmAnalyticsTrendsResponse:
        """
        Retrieves historical trends across zones and metrics.
        """
        farm_name: Optional[str] = None
        if farm_id:
            farm_meta = await self.repository.get_farm_metadata(farm_id)
            if not farm_meta:
                raise FarmNotFoundError(f"Farm with id '{farm_id}' was not found.")
            farm_name = farm_meta["name"]

        period = self._parse_period(period_str)
        metric = MetricType(metric_str) if metric_str else None

        trends_raw = await self.repository.get_trends_data(
            farm_id=farm_id,
            period=period,
            zone_id=zone_id,
            metric=metric,
        )

        hourly_items = [
            HourlyBirdActivityItem(
                label=item["label"],
                entries=item.get("entries"),
                exits=item.get("exits"),
            )
            for item in trends_raw.get("hourly_bird_activity", [])
        ]

        env_items = []
        for item in trends_raw.get("environment_comparison", []):
            zones_map = {}
            for z_id, z_m in item.get("zones", {}).items():
                zones_map[z_id] = EnvironmentZoneMetrics(
                    temperature=z_m.get("temperature"),
                    humidity=z_m.get("humidity"),
                    co2=z_m.get("co2"),
                    light=z_m.get("light"),
                    audio=z_m.get("audio"),
                )
            env_items.append(EnvironmentComparisonItem(label=item["label"], zones=zones_map))

        bird_trend_items = [
            BirdTrendItem(
                label=item["label"],
                entries=item.get("entries"),
                exits=item.get("exits"),
            )
            for item in trends_raw.get("bird_trend_analytics", [])
        ]

        alert_trend_items = [
            AlertTrendItem(
                label=item["label"],
                critical=item.get("critical"),
                high=item.get("high"),
                medium=item.get("medium"),
                low=item.get("low"),
            )
            for item in trends_raw.get("alert_trend", [])
        ]

        yield_trend_items = [
            YieldTrendItem(
                label=item["label"],
                value=item.get("value"),
            )
            for item in trends_raw.get("yield_trend", [])
        ]

        return FarmAnalyticsTrendsResponse(
            farmId=farm_id,
            farmName=farm_name,
            period=period.value,
            hourlyBirdActivity=hourly_items,
            environmentComparison=env_items,
            birdTrendAnalytics=bird_trend_items,
            alertTrend=alert_trend_items,
            yieldTrend=yield_trend_items,
            hasDataGaps=trends_raw.get("has_data_gaps", False),
        )
