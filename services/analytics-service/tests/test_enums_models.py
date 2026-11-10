"""
Unit tests for Domain Enums and Models in Analytics Service.
"""
from datetime import datetime, timezone
import pytest

from app.domain.enums import AlertSeverity, ClimateStatus, MetricType, PeriodEnum
from app.domain.models import (
    AlertDistribution,
    BirdActivityBucket,
    BirdPerformanceSummary,
    DEFAULT_THRESHOLDS,
    MicroclimateZoneScore,
    TimeSeriesDataPoint,
    TimeWindow,
    YieldSummary,
)


class TestDomainEnums:
    def test_period_enum_values_and_normalization(self):
        assert PeriodEnum.HOUR.value == "hour"
        assert PeriodEnum.DAY.value == "day"
        assert PeriodEnum.WEEK.value == "week"
        assert PeriodEnum.MONTH.value == "month"
        assert PeriodEnum.YEAR.value == "year"
        assert PeriodEnum.TODAY.value == "today"

        assert PeriodEnum.normalize("HOUR") == PeriodEnum.HOUR
        assert PeriodEnum.normalize(" Day ") == PeriodEnum.DAY
        assert PeriodEnum.normalize("today") == PeriodEnum.TODAY

    def test_metric_type_values(self):
        assert MetricType.TEMPERATURE.value == "temperature"
        assert MetricType.HUMIDITY.value == "humidity"
        assert MetricType.CO2.value == "co2"
        assert MetricType.LIGHT.value == "light"
        assert MetricType.AUDIO.value == "audio"
        assert MetricType.BIRD_ENTRIES.value == "bird_entries"
        assert MetricType.BIRD_EXITS.value == "bird_exits"
        assert MetricType.ALERTS.value == "alerts"
        assert MetricType.YIELD_KG.value == "yield_kg"

    def test_alert_severity_values(self):
        assert AlertSeverity.LOW.value == "LOW"
        assert AlertSeverity.MEDIUM.value == "MEDIUM"
        assert AlertSeverity.HIGH.value == "HIGH"
        assert AlertSeverity.CRITICAL.value == "CRITICAL"

    def test_climate_status_values(self):
        assert ClimateStatus.OPTIMAL.value == "optimal"
        assert ClimateStatus.WARNING.value == "warning"
        assert ClimateStatus.CRITICAL.value == "critical"
        assert ClimateStatus.UNKNOWN.value == "unknown"


class TestDomainModels:
    def test_time_window_valid(self):
        start = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)
        tw = TimeWindow(start_time=start, end_time=end, period=PeriodEnum.DAY)
        assert tw.duration_seconds == 86400.0

    def test_time_window_invalid_order(self):
        start = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="cannot be after end_time"):
            TimeWindow(start_time=start, end_time=end, period=PeriodEnum.DAY)

    def test_bird_activity_bucket_valid(self):
        dt = datetime(2026, 11, 1, 6, 0, tzinfo=timezone.utc)
        bucket = BirdActivityBucket(bucket_start=dt, label="06:00", entries=45, exits=12)
        assert bucket.entries == 45
        assert bucket.exits == 12
        assert bucket.net_flux == 33

    def test_bird_activity_bucket_negative_counts(self):
        dt = datetime(2026, 11, 1, 6, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="entries cannot be negative"):
            BirdActivityBucket(bucket_start=dt, label="06:00", entries=-5, exits=10)

        with pytest.raises(ValueError, match="exits cannot be negative"):
            BirdActivityBucket(bucket_start=dt, label="06:00", entries=10, exits=-2)

    def test_bird_performance_summary_bounds(self):
        valid = BirdPerformanceSummary(
            entries=100,
            exits=95,
            difference=5,
            return_rate=95.0,
            percentage_change=12.5,
        )
        assert valid.difference == 5
        assert valid.return_rate == 95.0

        with pytest.raises(ValueError, match="return_rate must be between"):
            BirdPerformanceSummary(
                entries=100,
                exits=95,
                difference=5,
                return_rate=105.0,
            )

    def test_microclimate_zone_score_bounds(self):
        score_obj = MicroclimateZoneScore(
            zone_id="zone-1",
            zone_name="Tầng 1",
            score=88.5,
            status=ClimateStatus.OPTIMAL,
            avg_temperature=29.2,
            avg_humidity=84.0,
            avg_co2=550.0,
        )
        assert score_obj.score == 88.5
        assert score_obj.status == ClimateStatus.OPTIMAL

        with pytest.raises(ValueError, match="score must be between 0.0 and 100.0"):
            MicroclimateZoneScore(
                zone_id="zone-1",
                zone_name="Tầng 1",
                score=105.0,
                status=ClimateStatus.OPTIMAL,
            )

    def test_alert_distribution_counts(self):
        dist = AlertDistribution(critical=2, high=5, medium=10, low=20)
        assert dist.total == 37

        with pytest.raises(ValueError, match="cannot be negative"):
            AlertDistribution(critical=-1, high=5, medium=10, low=20)

    def test_yield_summary_valid(self):
        y = YieldSummary(nests=350, yield_kg=3.25, yield_change_pct=15.0)
        assert y.nests == 350
        assert y.yield_kg == 3.25
        assert y.yield_change_pct == 15.0

        with pytest.raises(ValueError, match="cannot be negative"):
            YieldSummary(nests=-1, yield_kg=2.0)

    def test_time_series_data_point(self):
        dt = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
        p1 = TimeSeriesDataPoint(timestamp=dt, label="12:00", value=28.5)
        assert not p1.is_missing
        assert p1.value == 28.5

        p2 = TimeSeriesDataPoint(timestamp=dt, label="12:00", value=None)
        assert p2.is_missing
        assert p2.value is None
