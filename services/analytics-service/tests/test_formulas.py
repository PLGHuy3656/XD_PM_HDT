"""
Unit tests for Pure Statistical Calculation Formulas in Analytics Service.
Verifies arithmetic correctness, edge case handling, zero-division avoidance, and score bounds.
"""
import pytest

from app.domain.enums import AlertSeverity, ClimateStatus, MetricType
from app.domain.formulas import (
    calculate_alert_distribution,
    calculate_bird_performance,
    calculate_microclimate_score,
    calculate_percentage_change,
    calculate_return_rate,
    calculate_yield_summary,
    validate_sensor_reading,
)


class TestPercentageChange:
    def test_standard_positive_growth(self):
        # 100 -> 150 = +50%
        assert calculate_percentage_change(150.0, 100.0) == 50.0

    def test_standard_negative_growth(self):
        # 100 -> 80 = -20%
        assert calculate_percentage_change(80.0, 100.0) == -20.0

    def test_zero_baseline_cases(self):
        # 0 -> 0 = 0.0%
        assert calculate_percentage_change(0.0, 0.0) == 0.0
        # 0 -> 50 = None (growth from zero baseline is mathematically undefined; not defaulted to 100%)
        assert calculate_percentage_change(50.0, 0.0) is None
        # 0 -> -10 = None
        assert calculate_percentage_change(-10.0, 0.0) is None

    def test_none_or_nan_baseline(self):
        assert calculate_percentage_change(100.0, None) is None
        assert calculate_percentage_change(float("nan"), 100.0) is None
        assert calculate_percentage_change(100.0, float("nan")) is None
        assert calculate_percentage_change(float("inf"), 100.0) is None


class TestReturnRate:
    def test_standard_return_rate(self):
        # 100 exited, 95 returned = 95.0%
        assert calculate_return_rate(entries=95, exits=100) == 95.0

    def test_clamped_at_100_percent(self):
        # If 120 entered and 100 exited (e.g. flock joining or birds from yesterday), cap at 100%
        assert calculate_return_rate(entries=120, exits=100) == 100.0

    def test_zero_exits_returns_none(self):
        # When exits == 0, denominator is zero -> ratio is undefined (None), not arbitrarily 100%
        assert calculate_return_rate(entries=50, exits=0) is None

    def test_zero_activity_returns_none(self):
        # Exits = 0, entries = 0 -> None (no baseline activity to evaluate return rate)
        assert calculate_return_rate(entries=0, exits=0) is None

    def test_negative_counts_raise(self):
        with pytest.raises(ValueError, match="Bird counts must be non-negative"):
            calculate_return_rate(entries=-1, exits=10)
        with pytest.raises(ValueError, match="Bird counts must be non-negative"):
            calculate_return_rate(entries=10, exits=-1)


class TestBirdPerformance:
    def test_complete_summary_calculation(self):
        # Previous: 200 entries. Current: 250 entries, 220 exits
        res = calculate_bird_performance(entries=250, exits=220, previous_entries=200)
        assert res.entries == 250
        assert res.exits == 220
        assert res.difference == 30  # 250 - 220
        assert res.return_rate == 100.0  # 250 > 220, clamped to 100
        assert res.percentage_change == 25.0  # (250 - 200)/200 * 100

    def test_summary_without_previous_entries(self):
        res = calculate_bird_performance(entries=100, exits=80, previous_entries=None)
        assert res.difference == 20
        assert res.return_rate == 100.0
        assert res.percentage_change is None

    def test_summary_with_zero_exits_has_none_return_rate(self):
        # 50 entries, 0 exits -> return_rate should be None
        res = calculate_bird_performance(entries=50, exits=0, previous_entries=None)
        assert res.difference == 50
        assert res.return_rate is None


class TestSensorValidation:
    def test_valid_temperatures(self):
        assert validate_sensor_reading(MetricType.TEMPERATURE, 28.5) == 28.5
        assert validate_sensor_reading(MetricType.TEMPERATURE, 0.0) == 0.0

    def test_valid_humidities(self):
        assert validate_sensor_reading(MetricType.HUMIDITY, 85.0) == 85.0
        assert validate_sensor_reading(MetricType.HUMIDITY, 0.0) == 0.0
        assert validate_sensor_reading(MetricType.HUMIDITY, 100.0) == 100.0

    def test_out_of_bounds_temperature(self):
        # 120 C is physically impossible for bird farm
        assert validate_sensor_reading(MetricType.TEMPERATURE, 120.0, strict=False) is None
        with pytest.raises(ValueError, match="out of physical bounds"):
            validate_sensor_reading(MetricType.TEMPERATURE, 120.0, strict=True)

    def test_out_of_bounds_humidity(self):
        # -10% or 110% humidity
        assert validate_sensor_reading(MetricType.HUMIDITY, -5.0, strict=False) is None
        assert validate_sensor_reading(MetricType.HUMIDITY, 105.0, strict=False) is None

    def test_none_and_nan(self):
        assert validate_sensor_reading(MetricType.TEMPERATURE, None) is None
        assert validate_sensor_reading(MetricType.TEMPERATURE, float("nan")) is None


class TestMicroclimateScore:
    def test_perfect_optimal_conditions(self):
        # Temp: 29.0C (optimal 27-31)
        # Humidity: 85% (optimal 80-90)
        # CO2: 500ppm (optimal <= 1000)
        res = calculate_microclimate_score(
            zone_id="z1",
            zone_name="Tầng trệt",
            avg_temperature=29.0,
            avg_humidity=85.0,
            avg_co2=500.0,
        )
        assert res.score == 100.0
        assert res.status == ClimateStatus.OPTIMAL

    def test_slight_suboptimal_triggers_warning(self):
        # Temp: 32.0C (+1.0C above optimal max 31.0 -> penalty 15 pts)
        # Humidity: 85% (optimal -> 100 pts)
        # Weighted: 0.45 * 85 + 0.45 * 100 = 38.25 + 45 = 83.25 / 0.9 = 92.5
        # Let's push temp further: 33.0C (+2.0C -> penalty 30 pts -> score 70)
        # Hum: 75% (-5% below optimal min 80 -> penalty 25 pts -> score 75)
        res = calculate_microclimate_score(
            zone_id="z1",
            zone_name="Tầng trệt",
            avg_temperature=33.0,
            avg_humidity=75.0,
            avg_co2=None,
        )
        assert res.score is not None
        assert 70.0 <= res.score < 85.0
        assert res.status == ClimateStatus.WARNING

    def test_extreme_suboptimal_triggers_critical(self):
        # Temp: 38.0C (7C outside -> penalty 105 -> score 0)
        # Hum: 50% (30% outside -> penalty 150 -> score 0)
        res = calculate_microclimate_score(
            zone_id="z1",
            zone_name="Tầng mái",
            avg_temperature=38.0,
            avg_humidity=50.0,
            avg_co2=2500.0,
        )
        assert res.score is not None
        assert res.score < 70.0
        assert res.status == ClimateStatus.CRITICAL

    def test_all_sensors_missing_returns_unknown(self):
        res = calculate_microclimate_score(
            zone_id="z1",
            zone_name="Tầng rỗng",
            avg_temperature=None,
            avg_humidity=None,
            avg_co2=None,
        )
        assert res.score is None
        assert res.status == ClimateStatus.UNKNOWN

    def test_partial_sensor_data_reweights(self):
        # Only temperature is present, humidity & co2 are missing
        res = calculate_microclimate_score(
            zone_id="z1",
            zone_name="Khu A",
            avg_temperature=29.0,
            avg_humidity=None,
            avg_co2=None,
        )
        assert res.score == 100.0
        assert res.status == ClimateStatus.OPTIMAL

    def test_microclimate_out_of_bounds_sensor_ignored(self):
        # Sensor reports 500.0 C (faulty hardware) -> ignored, leaving humidity only
        res = calculate_microclimate_score(
            zone_id="z1",
            zone_name="Khu B",
            avg_temperature=500.0,
            avg_humidity=85.0,
            avg_co2=None,
        )
        # 85% is optimal -> score 100.0
        assert res.score == 100.0
        assert res.avg_temperature is None
        assert res.avg_humidity == 85.0


class TestAlertDistribution:
    def test_distribution_counting(self):
        alerts = [
            AlertSeverity.CRITICAL,
            AlertSeverity.CRITICAL,
            AlertSeverity.HIGH,
            AlertSeverity.MEDIUM,
            AlertSeverity.MEDIUM,
            AlertSeverity.MEDIUM,
            AlertSeverity.LOW,
        ]
        dist = calculate_alert_distribution(alerts)
        assert dist.critical == 2
        assert dist.high == 1
        assert dist.medium == 3
        assert dist.low == 1
        assert dist.total == 7

    def test_empty_alerts(self):
        dist = calculate_alert_distribution([])
        assert dist.critical == 0
        assert dist.high == 0
        assert dist.medium == 0
        assert dist.low == 0
        assert dist.total == 0


class TestYieldSummary:
    def test_standard_yield_calculation(self):
        res = calculate_yield_summary(nests=350, yield_kg=3.5, previous_yield_kg=2.8)
        assert res.nests == 350
        assert res.yield_kg == 3.5
        assert res.yield_change_pct == 25.0  # (3.5 - 2.8)/2.8 * 100

    def test_negative_yield_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            calculate_yield_summary(nests=10, yield_kg=-0.5)
        with pytest.raises(ValueError, match="non-negative"):
            calculate_yield_summary(nests=-2, yield_kg=1.0)
