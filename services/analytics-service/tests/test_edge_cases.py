"""
Edge Case and Data Integrity Unit Tests for Analytics Service.

Specifically validates:
1. Preservation of valid 0 values vs missing data (None/null).
2. Time-series bucket filling policies (Discrete counters vs Continuous sensors).
3. Out-of-bounds sensory noise filtering.
4. Division by zero resistance.
5. Large magnitude stability.
"""
from datetime import datetime, timezone
import pytest

from app.domain.enums import MetricType
from app.domain.formulas import (
    calculate_percentage_change,
    calculate_return_rate,
    fill_time_series_buckets,
    validate_sensor_reading,
)


class TestTimeSeriesMissingDataHandling:
    """
    CRITICAL ARCHITECTURAL GUARANTEE:
    Continuous environmental sensors must NEVER be filled with zero (0.0).
    Discrete counters (events) must be filled with zero (0.0).
    """

    def setup_method(self):
        self.time_slots = [
            (datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc), "00:00"),
            (datetime(2026, 11, 1, 1, 0, tzinfo=timezone.utc), "01:00"),
            (datetime(2026, 11, 1, 2, 0, tzinfo=timezone.utc), "02:00"),
            (datetime(2026, 11, 1, 3, 0, tzinfo=timezone.utc), "03:00"),
        ]

    def test_continuous_sensor_missing_slot_filled_with_none_not_zero(self):
        # Temperature data only exists for 00:00 and 03:00. 01:00 and 02:00 are missing.
        existing_data = {
            "00:00": 28.5,
            "03:00": 29.0,
        }
        points = fill_time_series_buckets(
            expected_slots=self.time_slots,
            existing_data=existing_data,
            metric_type=MetricType.TEMPERATURE,
        )

        assert len(points) == 4
        # 00:00 is present
        assert points[0].label == "00:00"
        assert points[0].value == 28.5
        assert not points[0].is_missing

        # 01:00 is missing -> must be None, NOT 0.0
        assert points[1].label == "01:00"
        assert points[1].value is None
        assert points[1].is_missing

        # 02:00 is missing -> must be None, NOT 0.0
        assert points[2].label == "02:00"
        assert points[2].value is None
        assert points[2].is_missing

        # 03:00 is present
        assert points[3].label == "03:00"
        assert points[3].value == 29.0
        assert not points[3].is_missing

    def test_continuous_sensor_legitimate_zero_is_preserved(self):
        # For Light intensity or Audio at dead of night, 0.0 is a legitimate measurement, not missing!
        existing_data = {
            "00:00": 0.0,
            "01:00": 0.0,
        }
        points = fill_time_series_buckets(
            expected_slots=self.time_slots[:2],
            existing_data=existing_data,
            metric_type=MetricType.LIGHT,
        )
        assert points[0].value == 0.0
        assert not points[0].is_missing
        assert points[1].value == 0.0
        assert not points[1].is_missing

    def test_discrete_counter_with_confirmed_coverage_zero_fills(self):
        # When observation coverage is confirmed (cameras online, recording continuously),
        # an absence of events in an hour means 0 events occurred.
        existing_data = {
            "00:00": 15.0,
            # 01:00, 02:00 missing in detected events
            "03:00": 8.0,
        }
        coverage_map = {
            "00:00": True,
            "01:00": True,
            "02:00": True,
            "03:00": True,
        }
        points = fill_time_series_buckets(
            expected_slots=self.time_slots,
            existing_data=existing_data,
            metric_type=MetricType.BIRD_ENTRIES,
            coverage_map=coverage_map,
        )

        assert len(points) == 4
        assert points[0].value == 15.0
        assert not points[0].is_missing

        # 01:00 confirmed coverage -> safely filled with 0.0
        assert points[1].value == 0.0
        assert not points[1].is_missing

        # 02:00 confirmed coverage -> safely filled with 0.0
        assert points[2].value == 0.0
        assert not points[2].is_missing

        assert points[3].value == 8.0
        assert not points[3].is_missing

    def test_discrete_counter_with_unknown_or_failed_coverage_preserves_none(self):
        # If camera was offline or coverage is unconfirmed, do NOT assume 0 birds!
        # It must remain None (is_missing=True).
        existing_data = {
            "00:00": 15.0,
            # 01:00 missing, coverage is False (camera outage)
            # 02:00 missing, not in coverage map (unknown status)
        }
        coverage_map = {
            "00:00": True,
            "01:00": False,  # Camera was down
        }
        points = fill_time_series_buckets(
            expected_slots=self.time_slots[:3],
            existing_data=existing_data,
            metric_type=MetricType.BIRD_ENTRIES,
            coverage_map=coverage_map,
        )

        assert points[0].value == 15.0
        assert not points[0].is_missing

        # 01:00 outage -> None, is_missing=True
        assert points[1].value is None
        assert points[1].is_missing

        # 02:00 unknown coverage -> None, is_missing=True
        assert points[2].value is None
        assert points[2].is_missing

    def test_corrupted_sensor_reading_treated_as_missing(self):
        # A faulty sensor emits 999.0°C. In time-series filling, it should become None (is_missing=True)
        existing_data = {
            "00:00": 28.0,
            "01:00": 999.0,  # Corrupted / out of bounds
        }
        points = fill_time_series_buckets(
            expected_slots=self.time_slots[:2],
            existing_data=existing_data,
            metric_type=MetricType.TEMPERATURE,
        )
        assert points[0].value == 28.0
        assert not points[0].is_missing

        assert points[1].value is None
        assert points[1].is_missing


class TestArithmeticSafety:
    def test_percentage_change_extreme_magnitudes(self):
        # Normal high growth: 10 -> 10,000,000
        res = calculate_percentage_change(10_000_000.0, 10.0)
        assert res == 99_999_900.0

        # High shrinkage: 10,000,000 -> 0
        res2 = calculate_percentage_change(0.0, 10_000_000.0)
        assert res2 == -100.0

    def test_return_rate_large_flock(self):
        # 50,000 birds
        rate = calculate_return_rate(entries=48_500, exits=50_000)
        assert rate == 97.0

    def test_validate_sensor_reading_boundary_edges(self):
        # Exactly at physical bounds
        assert validate_sensor_reading(MetricType.HUMIDITY, 0.0) == 0.0
        assert validate_sensor_reading(MetricType.HUMIDITY, 100.0) == 100.0

        # Just outside physical bounds
        assert validate_sensor_reading(MetricType.HUMIDITY, -0.01) is None
        assert validate_sensor_reading(MetricType.HUMIDITY, 100.01) is None

    def test_fill_time_series_empty_slots(self):
        assert fill_time_series_buckets(expected_slots=[], existing_data={}, metric_type=MetricType.TEMPERATURE) == []

    def test_percentage_change_both_negative(self):
        # -100 -> -50: delta is ((-50 - (-100)) / 100) * 100 = +50%
        assert calculate_percentage_change(-50.0, -100.0) == 50.0
        # -50 -> -100: delta is ((-100 - (-50)) / 50) * 100 = -100%
        assert calculate_percentage_change(-100.0, -50.0) == -100.0
