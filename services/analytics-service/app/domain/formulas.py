"""
Statistical and Analytical Calculation Formulas for Analytics Service.

Implements pure Python domain calculations with strict safety guarantees:
- Zero-division guards
- Distinction between missing data (None) and legitimate zero values
- Out-of-bounds sensor reading filtering
- Explicit distinction between [CONFIRMED] SRS formulas and [PROPOSED] UI heuristics
"""
import math
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from app.domain.enums import AlertSeverity, ClimateStatus, MetricType
from app.domain.models import (
    DEFAULT_THRESHOLDS,
    AlertDistribution,
    BirdPerformanceSummary,
    MicroclimateZoneScore,
    TimeSeriesDataPoint,
    YieldSummary,
)


def calculate_percentage_change(
    current: float,
    previous: Optional[float],
) -> Optional[float]:
    """
    Calculates the relative percentage change between current and previous periods.
    [CONFIRMED - Standard Statistical Metric]

    Formula:
      Delta_pct = ((current - previous) / abs(previous)) * 100

    Edge Cases & Safety Rules:
      - previous is None -> None (no baseline available)
      - previous == 0.0:
          - If current == 0.0 -> 0.0 (zero change between two inactive periods)
          - If current != 0.0 -> None (relative rate of change from zero baseline is mathematically undefined; per SRS/CP9 requirement, do not default to +100%)
      - NaN or Inf inputs -> None
    """
    if previous is None or math.isnan(current) or math.isnan(previous):
        return None
    if math.isinf(current) or math.isinf(previous):
        return None

    if previous == 0.0:
        if current == 0.0:
            return 0.0
        return None

    delta = ((current - previous) / abs(previous)) * 100.0
    return round(delta, 2)


def calculate_return_rate(entries: int, exits: int) -> Optional[float]:
    """
    Calculates the bird flock in/out activity ratio (or return rate approximation).
    [PROPOSED / APPROXIMATION - Derived from analyticsMockData.js]

    Important Business Note:
      AI video counters record movement passes (lượt qua vạch), not individual bird IDs.
      A true biological "tỷ lệ cá thể chim quay về" requires individual bird tracking.
      This function calculates the ratio of entry events to exit events over an observation period.

    Formula:
      Return Ratio R = min(100.0, (entries / exits) * 100.0) if exits > 0

    Edge Cases & Safety Rules:
      - exits == 0: Returns None.
        (When exits == 0, the denominator is zero. Even if entries > 0, we cannot calculate
        a valid return ratio without an observed exit baseline; per system policy, we do NOT
        assume 100% without business confirmation).
      - entries < 0 or exits < 0 -> ValueError (physical impossibility).
      - entries > exits -> clamped at 100.0% if treating as flock return percentage.
    """
    if entries < 0 or exits < 0:
        raise ValueError(f"Bird counts must be non-negative: entries={entries}, exits={exits}")

    if exits == 0:
        return None

    rate = (entries / exits) * 100.0
    # Flock return rate is clamped at 100.0%
    return min(100.0, round(rate, 2))


def calculate_bird_performance(
    entries: int,
    exits: int,
    previous_entries: Optional[int] = None,
) -> BirdPerformanceSummary:
    """
    Calculates complete bird performance summary metrics.
    [CONFIRMED for entries/exits/difference; PROPOSED for return_rate approximation]

    Metrics:
      - Total entries
      - Total exits
      - Net population difference (entries - exits)
      - Return rate ratio (%) or None if exits == 0
      - Relative change in entries compared to previous period (%) or None if previous == 0
    """
    if entries < 0 or exits < 0:
        raise ValueError("Entries and exits must be non-negative")

    difference = entries - exits
    return_rate = calculate_return_rate(entries, exits)
    change_pct = calculate_percentage_change(float(entries), float(previous_entries) if previous_entries is not None else None)

    return BirdPerformanceSummary(
        entries=entries,
        exits=exits,
        difference=difference,
        return_rate=return_rate,
        percentage_change=change_pct,
    )


def validate_sensor_reading(
    metric: MetricType,
    value: Optional[float],
    strict: bool = False,
) -> Optional[float]:
    """
    Validates a continuous sensor reading against physical impossibility boundaries.
    [CONFIRMED - Telemetry Data Integrity]

    Returns:
      - Sanitized float if valid
      - None if input is None, NaN, Inf, or out-of-bounds (when strict=False)
      - Raises ValueError if out-of-bounds and strict=True
    """
    if value is None:
        return None
    if math.isnan(value) or math.isinf(value):
        if strict:
            raise ValueError(f"Invalid non-finite sensor value for {metric}: {value}")
        return None

    threshold = DEFAULT_THRESHOLDS.get(metric)
    if threshold:
        if value < threshold.physical_min or value > threshold.physical_max:
            if strict:
                raise ValueError(
                    f"Sensor reading out of physical bounds for {metric}: "
                    f"{value} not in [{threshold.physical_min}, {threshold.physical_max}]"
                )
            return None

    return round(value, 2)


def calculate_microclimate_score(
    zone_id: str,
    zone_name: str,
    avg_temperature: Optional[float],
    avg_humidity: Optional[float],
    avg_co2: Optional[float] = None,
) -> MicroclimateZoneScore:
    """
    Calculates an aggregated microclimate health score (0 - 100) for a farm zone.
    [PROPOSED - PENDING OFFICIAL BUSINESS APPROVAL]

    Status Note:
      Individual thresholds (Temp 27-31C, Humidity 80-90%, CO2 < 1000ppm) are
      confirmed by swiftlet biology and SRS specifications. However, the exact composite
      weighting formula below is PROPOSED to fulfill the frontend mock UI contract.
      It is not yet an officially approved business rule.

    Calculation:
      For each available metric m:
        - If optimal_min <= val <= optimal_max: component_score = 100.0
        - If outside, deduct points proportional to deviation distance:
            penalty = min(100.0, distance * penalty_factor)
            component_score = max(0.0, 100.0 - penalty)
      Composite score = weighted average of available component scores.

    Rules for missing data:
      - If all metrics are missing/invalid: returns score=None, status=UNKNOWN.
      - Never substitutes 0 for missing environmental metrics.
    """
    # Sanitize inputs
    clean_temp = validate_sensor_reading(MetricType.TEMPERATURE, avg_temperature)
    clean_hum = validate_sensor_reading(MetricType.HUMIDITY, avg_humidity)
    clean_co2 = validate_sensor_reading(MetricType.CO2, avg_co2) if avg_co2 is not None else None

    # Penalty factors per unit deviation
    # Temp: 1°C outside optimal costs 15 points
    # Hum: 1% outside optimal costs 5 points
    # CO2: 100 ppm above 1000 costs 5 points
    penalty_factors = {
        MetricType.TEMPERATURE: 15.0,
        MetricType.HUMIDITY: 5.0,
        MetricType.CO2: 0.05,
    }

    component_scores: List[Tuple[float, float]] = []  # (score, weight)

    if clean_temp is not None:
        th = DEFAULT_THRESHOLDS[MetricType.TEMPERATURE]
        if th.optimal_min <= clean_temp <= th.optimal_max:
            s = 100.0
        else:
            dist = (th.optimal_min - clean_temp) if clean_temp < th.optimal_min else (clean_temp - th.optimal_max)
            s = max(0.0, 100.0 - min(100.0, dist * penalty_factors[MetricType.TEMPERATURE]))
        component_scores.append((s, th.weight))

    if clean_hum is not None:
        th = DEFAULT_THRESHOLDS[MetricType.HUMIDITY]
        if th.optimal_min <= clean_hum <= th.optimal_max:
            s = 100.0
        else:
            dist = (th.optimal_min - clean_hum) if clean_hum < th.optimal_min else (clean_hum - th.optimal_max)
            s = max(0.0, 100.0 - min(100.0, dist * penalty_factors[MetricType.HUMIDITY]))
        component_scores.append((s, th.weight))

    if clean_co2 is not None:
        th = DEFAULT_THRESHOLDS[MetricType.CO2]
        if clean_co2 <= th.optimal_max:
            s = 100.0
        else:
            dist = clean_co2 - th.optimal_max
            s = max(0.0, 100.0 - min(100.0, dist * penalty_factors[MetricType.CO2]))
        component_scores.append((s, th.weight))

    if not component_scores:
        return MicroclimateZoneScore(
            zone_id=zone_id,
            zone_name=zone_name,
            score=None,
            status=ClimateStatus.UNKNOWN,
            avg_temperature=clean_temp,
            avg_humidity=clean_hum,
            avg_co2=clean_co2,
        )

    total_weight = sum(w for _, w in component_scores)
    raw_score = sum(s * w for s, w in component_scores) / total_weight
    final_score = round(max(0.0, min(100.0, raw_score)), 1)

    if final_score >= 85.0:
        status = ClimateStatus.OPTIMAL
    elif final_score >= 70.0:
        status = ClimateStatus.WARNING
    else:
        status = ClimateStatus.CRITICAL

    return MicroclimateZoneScore(
        zone_id=zone_id,
        zone_name=zone_name,
        score=final_score,
        status=status,
        avg_temperature=clean_temp,
        avg_humidity=clean_hum,
        avg_co2=clean_co2,
    )


def calculate_alert_distribution(alerts: List[AlertSeverity]) -> AlertDistribution:
    """
    Counts alert instances aggregated by severity tier.
    [CONFIRMED - Notification/Analytics Contract]
    """
    counts = {
        AlertSeverity.CRITICAL: 0,
        AlertSeverity.HIGH: 0,
        AlertSeverity.MEDIUM: 0,
        AlertSeverity.LOW: 0,
    }
    for severity in alerts:
        if severity in counts:
            counts[severity] += 1

    return AlertDistribution(
        critical=counts[AlertSeverity.CRITICAL],
        high=counts[AlertSeverity.HIGH],
        medium=counts[AlertSeverity.MEDIUM],
        low=counts[AlertSeverity.LOW],
    )


def fill_time_series_buckets(
    expected_slots: List[Tuple[datetime, str]],
    existing_data: Dict[str, Optional[float]],
    metric_type: MetricType,
    coverage_map: Optional[Dict[str, bool]] = None,
) -> List[TimeSeriesDataPoint]:
    """
    Aligns and fills time-series data against an expected series of time slots.
    [CONFIRMED - Architectural Principle on Missing Data Handling]

    Rules:
      - Continuous environmental sensors (TEMPERATURE, HUMIDITY, CO2, LIGHT, AUDIO):
        Missing slot -> None (JSON null), is_missing=True.
        *NEVER* fills continuous sensor gaps with 0.0, as 0°C or 0% humidity is physically false!
      - Discrete event counts (BIRD_ENTRIES, BIRD_EXITS, ALERTS):
        *ONLY* zero-filled (value = 0.0) when the slot is confirmed to have full observation coverage
        (i.e., coverage_map is provided and coverage_map[label] is True).
        If coverage is unknown (coverage_map is None or False) and no data was reported,
        keep value as None (is_missing=True) to avoid misrepresenting a sensor outage / AI downtime as 0 events.
    """
    is_discrete_counter = metric_type in (
        MetricType.BIRD_ENTRIES,
        MetricType.BIRD_EXITS,
        MetricType.ALERTS,
    )

    result: List[TimeSeriesDataPoint] = []
    for dt, label in expected_slots:
        val = existing_data.get(label)
        if val is None:
            if is_discrete_counter:
                has_coverage = coverage_map.get(label, False) if coverage_map is not None else False
                if has_coverage:
                    result.append(TimeSeriesDataPoint(timestamp=dt, label=label, value=0.0, is_missing=False))
                else:
                    result.append(TimeSeriesDataPoint(timestamp=dt, label=label, value=None, is_missing=True))
            else:
                result.append(TimeSeriesDataPoint(timestamp=dt, label=label, value=None, is_missing=True))
        else:
            # Validate physical boundaries if continuous
            clean_val = validate_sensor_reading(metric_type, val) if not is_discrete_counter else val
            if clean_val is None and not is_discrete_counter:
                result.append(TimeSeriesDataPoint(timestamp=dt, label=label, value=None, is_missing=True))
            else:
                result.append(TimeSeriesDataPoint(timestamp=dt, label=label, value=clean_val, is_missing=False))

    return result


def calculate_yield_summary(
    nests: int,
    yield_kg: float,
    previous_yield_kg: Optional[float] = None,
) -> YieldSummary:
    """
    Calculates harvest yield summary and growth change rate.
    [PROPOSED - PENDING OFFICIAL BUSINESS APPROVAL]
    """
    if nests < 0 or yield_kg < 0.0:
        raise ValueError("Nests and yield_kg must be non-negative")

    change_pct = calculate_percentage_change(yield_kg, previous_yield_kg)
    return YieldSummary(
        nests=nests,
        yield_kg=round(yield_kg, 2),
        yield_change_pct=change_pct,
    )
