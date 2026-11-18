from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from app.database import get_connection


def get_telemetry_analytics(
    node_ids: list[str],
    start: datetime,
    end: datetime,
    bucket: str,
) -> list[tuple]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH samples AS (
                    SELECT
                        date_trunc(
                            %s,
                            t.recorded_at AT TIME ZONE 'UTC'
                        ) AT TIME ZONE 'UTC' AS bucket,
                        t.temperature,
                        t.humidity,
                        t.co2,
                        t.lux,
                        t.audio_rms
                    FROM public.telemetry t
                    JOIN public.devices d ON d.id = t.device_id
                    WHERE d.node_id = ANY(%s)
                      AND t.recorded_at >= %s
                      AND t.recorded_at < %s
                )
                SELECT
                    bucket,
                    COUNT(*)::bigint,
                    AVG(temperature),
                    MIN(temperature),
                    MAX(temperature),
                    AVG(humidity),
                    MIN(humidity),
                    MAX(humidity),
                    AVG(co2),
                    MIN(co2),
                    MAX(co2),
                    AVG(lux),
                    MIN(lux),
                    MAX(lux),
                    AVG(audio_rms),
                    MIN(audio_rms),
                    MAX(audio_rms)
                FROM samples
                GROUP BY GROUPING SETS ((), (bucket))
                ORDER BY bucket NULLS FIRST
                """,
                (bucket, node_ids, start, end),
            )
            return cur.fetchall()


def get_latest_telemetry(node_ids: list[str]) -> list[tuple]:
    if not node_ids:
        return []

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (d.node_id)
                    d.node_id,
                    t.recorded_at,
                    t.temperature,
                    t.humidity,
                    t.co2,
                    t.lux,
                    c.target_temp,
                    c.temp_deadband,
                    c.target_hum,
                    c.hum_deadband,
                    c.co2_threshold
                FROM public.telemetry AS t
                JOIN public.devices AS d ON d.id = t.device_id
                LEFT JOIN public.environment_control_configs AS c
                    ON c.device_id = d.id
                WHERE d.node_id = ANY(%s)
                ORDER BY d.node_id, t.recorded_at DESC
                """,
                (node_ids,),
            )
            return cur.fetchall()


def get_anomaly_baselines(
    node_ids: list[str],
    start: datetime,
    end: datetime,
) -> dict[tuple[str, str], tuple[int, float | None, float | None]]:
    if not node_ids:
        return {}

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH metric_samples AS (
                    SELECT
                        d.node_id,
                        metric.name,
                        metric.value
                    FROM public.telemetry AS t
                    JOIN public.devices AS d ON d.id = t.device_id
                    CROSS JOIN LATERAL (
                        VALUES
                            ('temperature', t.temperature),
                            ('humidity', t.humidity),
                            ('co2', t.co2),
                            ('lux', t.lux)
                    ) AS metric(name, value)
                    WHERE d.node_id = ANY(%s)
                      AND t.recorded_at >= %s
                      AND t.recorded_at < %s
                      AND metric.value IS NOT NULL
                ),
                medians AS (
                    SELECT
                        node_id,
                        name,
                        COUNT(*)::integer AS sample_count,
                        percentile_cont(0.5) WITHIN GROUP (
                            ORDER BY value
                        ) AS median
                    FROM metric_samples
                    GROUP BY node_id, name
                ),
                deviations AS (
                    SELECT
                        samples.node_id,
                        samples.name,
                        medians.sample_count,
                        medians.median,
                        percentile_cont(0.5) WITHIN GROUP (
                            ORDER BY abs(samples.value - medians.median)
                        ) AS mad
                    FROM metric_samples AS samples
                    JOIN medians
                      ON medians.node_id = samples.node_id
                     AND medians.name = samples.name
                    GROUP BY
                        samples.node_id,
                        samples.name,
                        medians.sample_count,
                        medians.median
                )
                SELECT node_id, name, sample_count, median, mad
                FROM deviations
                """,
                (node_ids, start, end),
            )
            return {
                (row[0], row[1]): (
                    row[2],
                    float(row[3]) if row[3] is not None else None,
                    float(row[4]) if row[4] is not None else None,
                )
                for row in cur.fetchall()
            }


def open_analytics_alert(
    *,
    alert_key: str,
    node_id: str,
    farm_id: str,
    farm_name: str,
    zone_name: str | None,
    alert_type: str,
    metric: str,
    value: float,
    threshold: float | None,
    direction: str,
    baseline: dict[str, Any],
    event: dict[str, Any],
) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.analytics_alerts (
                    alert_key, node_id, farm_id, farm_name, zone_name,
                    alert_type, metric, value, threshold, direction, baseline
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (alert_key) WHERE resolved_at IS NULL
                DO NOTHING
                RETURNING id
                """,
                (
                    alert_key,
                    node_id,
                    farm_id,
                    farm_name,
                    zone_name,
                    alert_type,
                    metric,
                    value,
                    threshold,
                    direction,
                    Jsonb(baseline),
                ),
            )
            if cur.fetchone() is None:
                return False

            cur.execute(
                """
                INSERT INTO public.analytics_event_outbox (
                    event_id, event_type, payload
                )
                VALUES (%s, %s, %s)
                """,
                (
                    event["event_id"],
                    event["event_type"],
                    Jsonb(event),
                ),
            )
            return True


def resolve_analytics_alert(alert_key: str) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.analytics_alerts
                SET resolved_at = NOW()
                WHERE alert_key = %s
                  AND resolved_at IS NULL
                RETURNING id
                """,
                (alert_key,),
            )
            return cur.fetchone() is not None


def get_pending_analytics_events(limit: int = 50) -> list[tuple]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT event_id, payload
                FROM public.analytics_event_outbox
                WHERE published_at IS NULL
                  AND next_attempt_at <= NOW()
                ORDER BY created_at
                LIMIT %s
                """,
                (limit,),
            )
            return cur.fetchall()


def mark_analytics_event_published(event_id: UUID) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.analytics_event_outbox
                SET published_at = NOW(),
                    last_error = NULL
                WHERE event_id = %s
                """,
                (event_id,),
            )


def mark_analytics_event_failed(event_id: UUID, error: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.analytics_event_outbox
                SET attempts = attempts + 1,
                    next_attempt_at = NOW() + make_interval(
                        secs => LEAST(
                            300,
                            5 * power(2, LEAST(attempts, 6))
                        )::integer
                    ),
                    last_error = %s
                WHERE event_id = %s
                """,
                (error[:1000], event_id),
            )


def save_ai_count_snapshot(
    camera_id: str,
    reported_at: datetime,
    entry_count: int,
    exit_count: int,
) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.ai_count_snapshots (
                    camera_id, reported_at, entry_count, exit_count
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (camera_id, reported_at)
                DO UPDATE SET
                    entry_count = EXCLUDED.entry_count,
                    exit_count = EXCLUDED.exit_count
                WHERE public.ai_count_snapshots.entry_count
                          IS DISTINCT FROM EXCLUDED.entry_count
                   OR public.ai_count_snapshots.exit_count
                          IS DISTINCT FROM EXCLUDED.exit_count
                RETURNING id
                """,
                (camera_id, reported_at, entry_count, exit_count),
            )
            return cur.fetchone() is not None


def get_bird_analytics(
    node_ids: list[str],
    start: datetime,
    end: datetime,
    bucket: str,
) -> list[tuple]:
    if not node_ids:
        return []

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH prior AS (
                    SELECT DISTINCT ON (camera_id)
                        camera_id, reported_at, entry_count, exit_count
                    FROM public.ai_count_snapshots
                    WHERE camera_id = ANY(%s)
                      AND reported_at < %s
                    ORDER BY camera_id, reported_at DESC
                ),
                windowed AS (
                    SELECT camera_id, reported_at, entry_count, exit_count
                    FROM public.ai_count_snapshots
                    WHERE camera_id = ANY(%s)
                      AND reported_at >= %s
                      AND reported_at < %s
                ),
                camera_counts AS (
                    SELECT COUNT(DISTINCT camera_id)::integer AS camera_count
                    FROM windowed
                ),
                scoped AS (
                    SELECT * FROM prior
                    UNION ALL
                    SELECT * FROM windowed
                ),
                ordered AS (
                    SELECT
                        camera_id,
                        reported_at,
                        entry_count,
                        exit_count,
                        LAG(entry_count) OVER (
                            PARTITION BY camera_id ORDER BY reported_at
                        ) AS previous_entries,
                        LAG(exit_count) OVER (
                            PARTITION BY camera_id ORDER BY reported_at
                        ) AS previous_exits
                    FROM scoped
                ),
                deltas AS (
                    SELECT
                        date_trunc(%s, reported_at AT TIME ZONE 'UTC')
                            AT TIME ZONE 'UTC' AS bucket,
                        CASE
                            WHEN previous_entries IS NULL THEN 0
                            WHEN entry_count >= previous_entries
                                THEN entry_count - previous_entries
                            ELSE entry_count
                        END AS entries,
                        CASE
                            WHEN previous_exits IS NULL THEN 0
                            WHEN exit_count >= previous_exits
                                THEN exit_count - previous_exits
                            ELSE exit_count
                        END AS exits
                    FROM ordered
                    WHERE reported_at >= %s
                )
                SELECT
                    bucket,
                    SUM(entries),
                    SUM(exits),
                    camera_counts.camera_count
                FROM deltas
                CROSS JOIN camera_counts
                GROUP BY bucket, camera_counts.camera_count
                ORDER BY bucket
                """,
                (node_ids, start, node_ids, start, end, bucket, start),
            )
            return cur.fetchall()


def create_harvest_record(
    *,
    farm_id: UUID,
    zone_id: UUID | None,
    harvest_date: date,
    nest_count: int,
    yield_kg: Decimal,
    notes: str | None,
    recorded_by: UUID,
) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.harvest_records (
                    farm_id, zone_id, harvest_date, nest_count,
                    yield_kg, notes, recorded_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, farm_id, zone_id, harvest_date,
                          nest_count, yield_kg, notes, created_at
                """,
                (
                    farm_id,
                    zone_id,
                    harvest_date,
                    nest_count,
                    yield_kg,
                    notes,
                    recorded_by,
                ),
            )
            row = cur.fetchone()

    return {
        "id": str(row[0]),
        "farm_id": str(row[1]),
        "zone_id": str(row[2]) if row[2] else None,
        "harvest_date": row[3].isoformat(),
        "nest_count": row[4],
        "yield_kg": float(row[5]),
        "notes": row[6],
        "created_at": row[7].isoformat(),
    }


def get_harvest_records(
    farm_ids: list[str],
    start: date,
    end: date,
    zone_id: str | None = None,
) -> list[tuple]:
    if not farm_ids:
        return []

    query = """
        SELECT
            id, farm_id, zone_id, harvest_date, nest_count,
            yield_kg, notes, created_at
        FROM public.harvest_records
        WHERE farm_id::text = ANY(%s)
          AND harvest_date >= %s
          AND harvest_date < %s
    """
    params: list[Any] = [farm_ids, start, end]
    if zone_id is not None:
        query += " AND zone_id::text = %s"
        params.append(zone_id)
    query += " ORDER BY harvest_date, id"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            return cur.fetchall()


def get_analytics_alerts(
    node_ids: list[str],
    start: datetime,
    end: datetime,
) -> list[tuple]:
    if not node_ids:
        return []

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id, node_id, farm_name, zone_name, alert_type,
                    metric, value, threshold, direction, baseline,
                    opened_at, resolved_at
                FROM public.analytics_alerts
                WHERE node_id = ANY(%s)
                  AND (
                      (opened_at >= %s AND opened_at < %s)
                      OR resolved_at IS NULL
                  )
                ORDER BY opened_at DESC
                """,
                (node_ids, start, end),
            )
            return cur.fetchall()
