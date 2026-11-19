import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from app.repository import (
    get_analytics_alerts,
    get_bird_analytics,
    get_harvest_records,
    get_telemetry_analytics,
)


PERIODS = {
    "1h": (timedelta(hours=1), "minute"),
    "6h": (timedelta(hours=6), "hour"),
    "24h": (timedelta(hours=24), "hour"),
    "7d": (timedelta(days=7), "day"),
    "30d": (timedelta(days=30), "day"),
}
METRICS = ("temperature", "humidity", "co2", "lux", "audio_rms")
STATISTIC_OFFSETS = {
    "temperature": (2, 3, 4),
    "humidity": (5, 6, 7),
    "co2": (8, 9, 10),
    "lux": (11, 12, 13),
    "audio_rms": (14, 15, 16),
}


def _pkg_fn(name: str, fallback):
    pkg = sys.modules.get("app.services")
    return getattr(pkg, name, fallback) if pkg is not None else fallback


def _statistics(row: tuple, metric: str) -> dict[str, float | None]:
    average, minimum, maximum = (
        row[offset] for offset in STATISTIC_OFFSETS[metric]
    )
    return {
        "average": float(average) if average is not None else None,
        "minimum": float(minimum) if minimum is not None else None,
        "maximum": float(maximum) if maximum is not None else None,
    }


def _empty_statistics() -> dict[str, dict[str, None]]:
    return {
        metric: {
            "average": None,
            "minimum": None,
            "maximum": None,
        }
        for metric in METRICS
    }


def get_telemetry_analytics_data(
    node_ids: list[str],
    period: str,
    now: datetime | None = None,
) -> dict:
    duration, bucket = PERIODS[period]
    end = now or datetime.now(timezone.utc)
    start = end - duration

    query_fn = _pkg_fn("get_telemetry_analytics", get_telemetry_analytics)
    rows = query_fn(node_ids, start, end, bucket) if node_ids else []
    summary_row = next((row for row in rows if row[0] is None), None)
    series_rows = [row for row in rows if row[0] is not None]

    summary = (
        {metric: _statistics(summary_row, metric) for metric in METRICS}
        if summary_row is not None
        else _empty_statistics()
    )
    return {
        "period": period,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "bucket": bucket,
        "device_count": len(node_ids),
        "sample_count": summary_row[1] if summary_row is not None else 0,
        "summary": summary,
        "series": [
            {
                "timestamp": row[0].isoformat(),
                "samples": row[1],
                **{
                    metric: _statistics(row, metric)
                    for metric in METRICS
                },
            }
            for row in series_rows
        ],
    }


def get_bird_analytics_data(
    node_ids: list[str],
    period: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    duration, bucket = PERIODS[period]
    end = now or datetime.now(timezone.utc)
    start = end - duration
    query_fn = _pkg_fn("get_bird_analytics", get_bird_analytics)
    rows = query_fn(node_ids, start, end, bucket)
    series = [
        {
            "timestamp": row[0].isoformat(),
            "entries": int(row[1] or 0),
            "exits": int(row[2] or 0),
            "net_change": int(row[1] or 0) - int(row[2] or 0),
        }
        for row in rows
    ]
    entries = sum(point["entries"] for point in series)
    exits = sum(point["exits"] for point in series)
    return {
        "period": period,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "camera_count": int(rows[0][3]) if rows else 0,
        "entries": entries,
        "exits": exits,
        "net_change": entries - exits,
        "series": series,
    }


HARVEST_PERIODS = {
    "30d": 30,
    "90d": 90,
    "365d": 365,
}


def _harvest_values(rows: list[tuple]) -> tuple[int, Decimal]:
    return (
        sum(int(row[4]) for row in rows),
        sum((Decimal(row[5]) for row in rows), Decimal("0")),
    )


def get_harvest_analytics_data(
    farm_ids: list[str],
    period: str,
    zone_id: str | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    end_date = (today or datetime.now(timezone.utc).date()) + timedelta(days=1)
    start_date = end_date - timedelta(days=HARVEST_PERIODS[period])
    previous_start = start_date - timedelta(days=HARVEST_PERIODS[period])
    query_fn = _pkg_fn("get_harvest_records", get_harvest_records)
    rows = query_fn(
        farm_ids,
        start_date,
        end_date,
        zone_id,
    )
    previous_rows = query_fn(
        farm_ids,
        previous_start,
        start_date,
        zone_id,
    )

    nest_count, yield_kg = _harvest_values(rows)
    _, previous_yield = _harvest_values(previous_rows)
    yield_change = (
        float((yield_kg - previous_yield) * 100 / previous_yield)
        if previous_yield
        else None
    )

    grouped_trend: dict[str, dict[str, Decimal | int]] = defaultdict(
        lambda: {"nest_count": 0, "yield_kg": Decimal("0")},
    )
    grouped_zones: dict[str, dict[str, Decimal | int]] = defaultdict(
        lambda: {"nest_count": 0, "yield_kg": Decimal("0")},
    )
    for row in rows:
        month = row[3].strftime("%Y-%m")
        grouped_trend[month]["nest_count"] += int(row[4])
        grouped_trend[month]["yield_kg"] += Decimal(row[5])

        zone_key = str(row[2]) if row[2] else "unassigned"
        grouped_zones[zone_key]["nest_count"] += int(row[4])
        grouped_zones[zone_key]["yield_kg"] += Decimal(row[5])

    return {
        "period": period,
        "start": start_date.isoformat(),
        "end": (end_date - timedelta(days=1)).isoformat(),
        "record_count": len(rows),
        "nest_count": nest_count,
        "yield_kg": float(yield_kg),
        "previous_yield_kg": float(previous_yield),
        "yield_change_percent": yield_change,
        "trend": [
            {
                "month": month,
                "nest_count": values["nest_count"],
                "yield_kg": float(values["yield_kg"]),
            }
            for month, values in sorted(grouped_trend.items())
        ],
        "zones": [
            {
                "zone_id": zone_id,
                "nest_count": values["nest_count"],
                "yield_kg": float(values["yield_kg"]),
            }
            for zone_id, values in sorted(grouped_zones.items())
        ],
        "records": [
            {
                "id": str(row[0]),
                "farm_id": str(row[1]),
                "zone_id": str(row[2]) if row[2] else None,
                "harvest_date": row[3].isoformat(),
                "nest_count": int(row[4]),
                "yield_kg": float(row[5]),
                "notes": row[6],
                "created_at": row[7].isoformat(),
            }
            for row in rows
        ],
    }


def get_alerts_data(
    node_ids: list[str],
    period: str,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    duration, _ = PERIODS[period]
    end = now or datetime.now(timezone.utc)
    query_fn = _pkg_fn("get_analytics_alerts", get_analytics_alerts)
    rows = query_fn(node_ids, end - duration, end)
    return [
        {
            "id": str(row[0]),
            "node_id": row[1],
            "farm_name": row[2],
            "zone_name": row[3],
            "alert_type": row[4],
            "metric": row[5],
            "value": float(row[6]),
            "threshold": float(row[7]) if row[7] is not None else None,
            "direction": row[8],
            "baseline": row[9],
            "opened_at": row[10].isoformat(),
            "resolved_at": row[11].isoformat() if row[11] else None,
        }
        for row in rows
    ]
