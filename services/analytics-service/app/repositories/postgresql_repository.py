"""
PostgreSQL Analytics Repository Adapter.

Implements IAnalyticsRepository using PostgreSQL 18+ (analytics_db).
Follows Hexagonal / Ports & Adapters Architecture.
Adheres strictly to the OLAP Read Model constraint:
- ONLY reads from analytics_db.
- Zero connection to operational databases (management_db, iot_db, ai_db, notification_db).
- All queries use parameterized SQL (zero string concatenation for parameters).
- Missing continuous metrics are preserved as Python None (serialized to JSON null).
"""
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

from app.domain.enums import AlertSeverity, MetricType, PeriodEnum
from app.domain.models import BirdActivityBucket
from app.ports.analytics_repository import IAnalyticsRepository


class PostgreSQLAnalyticsRepository(IAnalyticsRepository):
    """
    Production-grade PostgreSQL repository implementing IAnalyticsRepository.
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        timeout_seconds: float = 5.0,
    ):
        resolved_url = database_url or os.getenv("ANALYTICS_DATABASE_URL")
        if not resolved_url:
            host = os.getenv("PGHOST", "127.0.0.1")
            port = int(os.getenv("PGPORT", "5432"))
            user = os.getenv("PGUSER", "postgres")
            pw = os.getenv("PGPASSWORD", "263656")
            db = os.getenv("PGDATABASE", "analytics_db")
            resolved_url = make_conninfo(host=host, port=port, user=user, password=pw, dbname=db)
        self.database_url = resolved_url
        self.timeout_seconds = timeout_seconds

    @contextmanager
    def _get_connection(self):
        """
        Context manager for acquiring and closing PostgreSQL connections.
        Ensures strict connection cleanup and timeout enforcement.
        """
        if not self.database_url:
            raise ValueError(
                "ANALYTICS_DATABASE_URL is not configured. "
                "Please configure connection string or inject database_url."
            )
        conn = psycopg.connect(
            self.database_url,
            connect_timeout=self.timeout_seconds,
            row_factory=dict_row,
        )
        try:
            yield conn
        finally:
            conn.close()

    def _calculate_time_window(
        self,
        period: PeriodEnum,
        reference_time: Optional[datetime] = None,
    ) -> Tuple[datetime, datetime, datetime, datetime]:
        """
        Calculates (start_time, end_time, prev_start_time, prev_end_time) in UTC.
        """
        ref = reference_time or datetime.now(timezone.utc)
        if period in (PeriodEnum.DAY, PeriodEnum.TODAY):
            start = ref.replace(hour=0, minute=0, second=0, microsecond=0)
            end = ref
            prev_start = start - timedelta(days=1)
            prev_end = start
        elif period == PeriodEnum.HOUR:
            start = ref - timedelta(hours=1)
            end = ref
            prev_start = ref - timedelta(hours=2)
            prev_end = start
        elif period == PeriodEnum.WEEK:
            start = ref - timedelta(days=7)
            end = ref
            prev_start = ref - timedelta(days=14)
            prev_end = start
        elif period == PeriodEnum.MONTH:
            start = ref - timedelta(days=30)
            end = ref
            prev_start = ref - timedelta(days=60)
            prev_end = start
        elif period == PeriodEnum.YEAR:
            start = ref - timedelta(days=365)
            end = ref
            prev_start = ref - timedelta(days=730)
            prev_end = start
        else:
            # Fallback for custom periods
            start = ref - timedelta(days=1)
            end = ref
            prev_start = ref - timedelta(days=2)
            prev_end = start

        return start, end, prev_start, prev_end

    async def get_farm_metadata(self, farm_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves farm metadata and its zones from dim_farms and dim_zones.
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT farm_id, name FROM dim_farms WHERE farm_id = %s;",
                    (farm_id,),
                )
                farm_row = cur.fetchone()
                if not farm_row:
                    return None

                cur.execute(
                    "SELECT zone_id, name FROM dim_zones WHERE farm_id = %s ORDER BY name ASC;",
                    (farm_id,),
                )
                zones_rows = cur.fetchall()

                return {
                    "id": farm_row["farm_id"],
                    "name": farm_row["name"],
                    "zones": [{"id": z["zone_id"], "name": z["name"]} for z in zones_rows],
                }

    async def get_bird_activity_buckets(
        self,
        farm_id: str,
        period: PeriodEnum,
    ) -> Tuple[List[BirdActivityBucket], Optional[int], Dict[str, bool]]:
        """
        Retrieves aggregated bird activity buckets from fact_bird_activity_hourly.
        """
        start_t, end_t, prev_start_t, prev_end_t = self._calculate_time_window(period)

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Current Period Buckets
                cur.execute(
                    """
                    SELECT
                        time_bucket,
                        COALESCE(SUM(entries), 0) AS entries,
                        COALESCE(SUM(exits), 0) AS exits,
                        BOOL_AND(is_coverage_healthy) AS healthy
                    FROM fact_bird_activity_hourly
                    WHERE farm_id = %s AND time_bucket >= %s AND time_bucket <= %s
                    GROUP BY time_bucket
                    ORDER BY time_bucket ASC;
                    """,
                    (farm_id, start_t, end_t),
                )
                rows = cur.fetchall()

                buckets: List[BirdActivityBucket] = []
                coverage_map: Dict[str, bool] = {}

                for r in rows:
                    tb: datetime = r["time_bucket"]
                    label = f"{tb.strftime('%H')}h"
                    is_healthy = bool(r["healthy"]) if r["healthy"] is not None else True
                    coverage_map[label] = is_healthy

                    buckets.append(
                        BirdActivityBucket(
                            bucket_start=tb,
                            label=label,
                            entries=int(r["entries"]),
                            exits=int(r["exits"]),
                        )
                    )

                # 2. Previous Period Baseline (for change percentage calculation)
                cur.execute(
                    """
                    SELECT SUM(entries) AS prev_entries, COUNT(*) AS row_count
                    FROM fact_bird_activity_hourly
                    WHERE farm_id = %s AND time_bucket >= %s AND time_bucket < %s;
                    """,
                    (farm_id, prev_start_t, prev_end_t),
                )
                prev_row = cur.fetchone()
                previous_entries: Optional[int] = None
                if prev_row and prev_row["row_count"] > 0 and prev_row["prev_entries"] is not None:
                    previous_entries = int(prev_row["prev_entries"])

                return buckets, previous_entries, coverage_map

    async def get_zone_climate_averages(
        self,
        farm_id: str,
        period: PeriodEnum,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves average microclimate metrics per zone.
        Preserves NULL when data is missing or sensor is offline.
        """
        start_t, end_t, _, _ = self._calculate_time_window(period)

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        z.zone_id,
                        z.name AS zone_name,
                        AVG(f.avg_temperature) AS avg_temperature,
                        AVG(f.avg_humidity) AS avg_humidity,
                        AVG(f.avg_co2) AS avg_co2
                    FROM dim_zones z
                    LEFT JOIN fact_telemetry_hourly f
                        ON z.zone_id = f.zone_id
                        AND f.farm_id = %s
                        AND f.time_bucket >= %s
                        AND f.time_bucket <= %s
                    WHERE z.farm_id = %s
                    GROUP BY z.zone_id, z.name
                    ORDER BY z.name ASC;
                    """,
                    (farm_id, start_t, end_t, farm_id),
                )
                rows = cur.fetchall()

                results: List[Dict[str, Any]] = []
                for r in rows:
                    results.append(
                        {
                            "zone_id": r["zone_id"],
                            "zone_name": r["zone_name"],
                            "avg_temperature": round(r["avg_temperature"], 1) if r["avg_temperature"] is not None else None,
                            "avg_humidity": round(r["avg_humidity"], 1) if r["avg_humidity"] is not None else None,
                            "avg_co2": round(r["avg_co2"], 1) if r["avg_co2"] is not None else None,
                        }
                    )
                return results

    async def get_alerts(
        self,
        farm_id: str,
        period: PeriodEnum,
    ) -> List[AlertSeverity]:
        """
        Retrieves alerts distribution from fact_alerts_hourly.
        """
        start_t, end_t, _, _ = self._calculate_time_window(period)

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COALESCE(SUM(critical_count), 0) AS critical,
                        COALESCE(SUM(high_count), 0) AS high,
                        COALESCE(SUM(medium_count), 0) AS medium,
                        COALESCE(SUM(low_count), 0) AS low
                    FROM fact_alerts_hourly
                    WHERE farm_id = %s AND time_bucket >= %s AND time_bucket <= %s;
                    """,
                    (farm_id, start_t, end_t),
                )
                row = cur.fetchone()
                if not row:
                    return []

                alerts_list: List[AlertSeverity] = []
                alerts_list.extend([AlertSeverity.CRITICAL] * int(row["critical"]))
                alerts_list.extend([AlertSeverity.HIGH] * int(row["high"]))
                alerts_list.extend([AlertSeverity.MEDIUM] * int(row["medium"]))
                alerts_list.extend([AlertSeverity.LOW] * int(row["low"]))
                return alerts_list

    async def get_yield_data(
        self,
        farm_id: str,
        period: PeriodEnum,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves periodic harvest yield data from fact_harvest_yield.
        """
        start_t, end_t, prev_start_t, prev_end_t = self._calculate_time_window(period)
        start_date = start_t.date()
        end_date = end_t.date()
        prev_start_date = prev_start_t.date()
        prev_end_date = prev_end_t.date()

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Current period yield
                cur.execute(
                    """
                    SELECT
                        COALESCE(SUM(total_nests), 0) AS total_nests,
                        COALESCE(SUM(harvested_nests), 0) AS harvested_nests,
                        COALESCE(SUM(yield_kg), 0.0) AS current_yield,
                        COUNT(*) AS record_count
                    FROM fact_harvest_yield
                    WHERE farm_id = %s AND harvest_date >= %s AND harvest_date <= %s;
                    """,
                    (farm_id, start_date, end_date),
                )
                curr_row = cur.fetchone()
                if not curr_row or curr_row["record_count"] == 0:
                    return None

                # Previous period yield
                cur.execute(
                    """
                    SELECT SUM(yield_kg) AS prev_yield, COUNT(*) AS prev_count
                    FROM fact_harvest_yield
                    WHERE farm_id = %s AND harvest_date >= %s AND harvest_date < %s;
                    """,
                    (farm_id, prev_start_date, prev_end_date),
                )
                prev_row = cur.fetchone()
                previous_yield = float(prev_row["prev_yield"]) if prev_row and prev_row["prev_count"] > 0 and prev_row["prev_yield"] is not None else None

                return {
                    "total_nests": int(curr_row["total_nests"]),
                    "harvested_nests": int(curr_row["harvested_nests"]),
                    "current_yield": float(curr_row["current_yield"]),
                    "previous_yield": previous_yield,
                }

    async def get_trends_data(
        self,
        farm_id: Optional[str],
        period: PeriodEnum,
        zone_id: Optional[str] = None,
        metric: Optional[MetricType] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves multi-dimensional time series trends.
        """
        start_t, end_t, _, _ = self._calculate_time_window(period)

        hourly_bird_activity: List[Dict[str, Any]] = []
        environment_comparison: List[Dict[str, Any]] = []
        bird_trend_analytics: List[Dict[str, Any]] = []
        alert_trend: List[Dict[str, Any]] = []
        yield_trend: List[Dict[str, Any]] = []
        has_data_gaps = False

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Hourly Bird Activity
                where_clause = "WHERE time_bucket >= %s AND time_bucket <= %s"
                params: List[Any] = [start_t, end_t]
                if farm_id:
                    where_clause += " AND farm_id = %s"
                    params.append(farm_id)
                if zone_id:
                    where_clause += " AND zone_id = %s"
                    params.append(zone_id)

                cur.execute(
                    f"""
                    SELECT
                        time_bucket,
                        SUM(entries) AS entries,
                        SUM(exits) AS exits,
                        BOOL_AND(is_coverage_healthy) AS healthy
                    FROM fact_bird_activity_hourly
                    {where_clause}
                    GROUP BY time_bucket
                    ORDER BY time_bucket ASC;
                    """,
                    params,
                )
                for r in cur.fetchall():
                    tb: datetime = r["time_bucket"]
                    label = f"{tb.strftime('%H')}h"
                    is_h = bool(r["healthy"]) if r["healthy"] is not None else True
                    if not is_h:
                        has_data_gaps = True
                    hourly_bird_activity.append(
                        {
                            "label": label,
                            "entries": int(r["entries"]) if is_h and r["entries"] is not None else None,
                            "exits": int(r["exits"]) if is_h and r["exits"] is not None else None,
                        }
                    )

                # 2. Environment Comparison
                cur.execute(
                    f"""
                    SELECT
                        time_bucket,
                        zone_id,
                        AVG(avg_temperature) AS avg_temperature,
                        AVG(avg_humidity) AS avg_humidity,
                        AVG(avg_co2) AS avg_co2,
                        AVG(avg_lux) AS avg_lux,
                        AVG(avg_audio_rms) AS avg_audio_rms,
                        BOOL_OR(has_data_gaps) AS gap
                    FROM fact_telemetry_hourly
                    {where_clause}
                    GROUP BY time_bucket, zone_id
                    ORDER BY time_bucket ASC, zone_id ASC;
                    """,
                    params,
                )
                env_by_time: Dict[str, Dict[str, Any]] = {}
                for r in cur.fetchall():
                    tb: datetime = r["time_bucket"]
                    label = f"{tb.strftime('%H')}h"
                    if label not in env_by_time:
                        env_by_time[label] = {"label": label, "zones": {}}
                    if r["gap"]:
                        has_data_gaps = True
                    env_by_time[label]["zones"][r["zone_id"]] = {
                        "temperature": round(r["avg_temperature"], 1) if r["avg_temperature"] is not None else None,
                        "humidity": round(r["avg_humidity"], 1) if r["avg_humidity"] is not None else None,
                        "co2": round(r["avg_co2"], 1) if r["avg_co2"] is not None else None,
                        "light": round(r["avg_lux"], 1) if r["avg_lux"] is not None else None,
                        "audio": round(r["avg_audio_rms"], 1) if r["avg_audio_rms"] is not None else None,
                    }
                environment_comparison = list(env_by_time.values())

                # 3. Bird Trends by Day
                cur.execute(
                    f"""
                    SELECT
                        DATE_TRUNC('day', time_bucket) AS day_bucket,
                        SUM(entries) AS entries,
                        SUM(exits) AS exits,
                        BOOL_AND(is_coverage_healthy) AS healthy
                    FROM fact_bird_activity_hourly
                    {where_clause}
                    GROUP BY DATE_TRUNC('day', time_bucket)
                    ORDER BY day_bucket ASC;
                    """,
                    params,
                )
                for r in cur.fetchall():
                    db: datetime = r["day_bucket"]
                    label = db.strftime("%d/%m")
                    is_h = bool(r["healthy"]) if r["healthy"] is not None else True
                    if not is_h:
                        has_data_gaps = True
                    bird_trend_analytics.append(
                        {
                            "label": label,
                            "entries": int(r["entries"]) if is_h and r["entries"] is not None else None,
                            "exits": int(r["exits"]) if is_h and r["exits"] is not None else None,
                        }
                    )

                # 4. Alert Trends by Day
                cur.execute(
                    f"""
                    SELECT
                        DATE_TRUNC('day', time_bucket) AS day_bucket,
                        SUM(critical_count) AS critical,
                        SUM(high_count) AS high,
                        SUM(medium_count) AS medium,
                        SUM(low_count) AS low
                    FROM fact_alerts_hourly
                    {where_clause}
                    GROUP BY DATE_TRUNC('day', time_bucket)
                    ORDER BY day_bucket ASC;
                    """,
                    params,
                )
                for r in cur.fetchall():
                    db: datetime = r["day_bucket"]
                    label = db.strftime("%d/%m")
                    alert_trend.append(
                        {
                            "label": label,
                            "critical": int(r["critical"]) if r["critical"] is not None else None,
                            "high": int(r["high"]) if r["high"] is not None else None,
                            "medium": int(r["medium"]) if r["medium"] is not None else None,
                            "low": int(r["low"]) if r["low"] is not None else None,
                        }
                    )

                # 5. Yield Trends
                y_params: List[Any] = [start_t.date(), end_t.date()]
                y_where = "WHERE harvest_date >= %s AND harvest_date <= %s"
                if farm_id:
                    y_where += " AND farm_id = %s"
                    y_params.append(farm_id)
                if zone_id:
                    y_where += " AND zone_id = %s"
                    y_params.append(zone_id)

                cur.execute(
                    f"""
                    SELECT
                        TO_CHAR(harvest_date, 'MM') AS month_label,
                        SUM(yield_kg) AS value
                    FROM fact_harvest_yield
                    {y_where}
                    GROUP BY TO_CHAR(harvest_date, 'MM')
                    ORDER BY month_label ASC;
                    """,
                    y_params,
                )
                for r in cur.fetchall():
                    m_num = r["month_label"]
                    yield_trend.append(
                        {
                            "label": f"T{int(m_num)}",
                            "value": float(r["value"]) if r["value"] is not None else None,
                        }
                    )

        return {
            "hourly_bird_activity": hourly_bird_activity,
            "environment_comparison": environment_comparison,
            "bird_trend_analytics": bird_trend_analytics,
            "alert_trend": alert_trend,
            "yield_trend": yield_trend,
            "has_data_gaps": has_data_gaps,
        }
