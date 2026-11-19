import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from app.config import settings
from app.database import get_connection


def save_telemetry_sample(
    *,
    node_id: str,
    recorded_at: datetime,
    temperature: float | None = None,
    humidity: float | None = None,
    co2: float | None = None,
    lux: float | None = None,
    audio_rms: float | None = None,
    target_temp: float | None = None,
    temp_deadband: float | None = None,
    target_hum: float | None = None,
    hum_deadband: float | None = None,
    co2_threshold: float | None = None,
) -> bool:
    """Persist an analytics-owned telemetry sample into analytics_db (deduplicated by node_id + recorded_at)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.analytics_telemetry_samples (
                    node_id, recorded_at, temperature, humidity, co2, lux, audio_rms,
                    target_temp, temp_deadband, target_hum, hum_deadband, co2_threshold
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (node_id, recorded_at) DO NOTHING
                RETURNING id
                """,
                (
                    node_id,
                    recorded_at,
                    temperature,
                    humidity,
                    co2,
                    lux,
                    audio_rms,
                    target_temp,
                    temp_deadband,
                    target_hum,
                    hum_deadband,
                    co2_threshold,
                ),
            )
            return cur.fetchone() is not None


def get_telemetry_analytics(
    node_ids: list[str],
    start: datetime,
    end: datetime,
    bucket: str,
) -> list[tuple]:
    if not node_ids:
        return []

    if settings.telemetry_source == "iot_legacy":
        samples_cte = """
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
        """
    else:
        samples_cte = """
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
                    FROM public.analytics_telemetry_samples t
                    WHERE t.node_id = ANY(%s)
                      AND t.recorded_at >= %s
                      AND t.recorded_at < %s
        """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                WITH samples AS (
                    {samples_cte}
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

    if settings.telemetry_source == "iot_legacy":
        sql = """
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
        """
    else:
        sql = """
                SELECT DISTINCT ON (t.node_id)
                    t.node_id,
                    t.recorded_at,
                    t.temperature,
                    t.humidity,
                    t.co2,
                    t.lux,
                    t.target_temp,
                    t.temp_deadband,
                    t.target_hum,
                    t.hum_deadband,
                    t.co2_threshold
                FROM public.analytics_telemetry_samples AS t
                WHERE t.node_id = ANY(%s)
                ORDER BY t.node_id, t.recorded_at DESC
        """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (node_ids,))
            return cur.fetchall()


def get_anomaly_baselines(
    node_ids: list[str],
    start: datetime,
    end: datetime,
) -> dict[tuple[str, str], tuple[int, float | None, float | None]]:
    if not node_ids:
        return {}

    if settings.telemetry_source == "iot_legacy":
        metric_source = """
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
        """
    else:
        metric_source = """
                    SELECT
                        t.node_id,
                        metric.name,
                        metric.value
                    FROM public.analytics_telemetry_samples AS t
                    CROSS JOIN LATERAL (
                        VALUES
                            ('temperature', t.temperature),
                            ('humidity', t.humidity),
                            ('co2', t.co2),
                            ('lux', t.lux)
                    ) AS metric(name, value)
                    WHERE t.node_id = ANY(%s)
                      AND t.recorded_at >= %s
                      AND t.recorded_at < %s
                      AND metric.value IS NOT NULL
        """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                WITH metric_samples AS (
                    {metric_source}
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
                    event.get("eventId") or event["event_id"],
                    event.get("eventType") or event["event_type"],
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


def save_ai_event(
    *,
    event_key: str,
    source_event_id: UUID | None,
    source_type: str,
    camera_id: str,
    event_type: str,
    label: str,
    confidence: float,
    observed_at: datetime,
    context: dict[str, Any],
    payload: dict[str, Any],
    notification_event: dict[str, Any],
) -> UUID | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.ai_events (
                    event_key, source_event_id, source_type, camera_id,
                    event_type, label, confidence, observed_at,
                    farm_id, farm_code, farm_name, zone_id, zone_code,
                    zone_name, payload
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s
                )
                ON CONFLICT DO NOTHING
                RETURNING id
                """,
                (
                    event_key,
                    source_event_id,
                    source_type,
                    camera_id,
                    event_type,
                    label,
                    confidence,
                    observed_at,
                    UUID(context["farm_id"]),
                    context["farm_code"],
                    context["farm_name"],
                    UUID(context["zone_id"]) if context["zone_id"] else None,
                    context.get("zone_code"),
                    context.get("zone_name"),
                    Jsonb(payload),
                ),
            )
            row = cur.fetchone()
            if row is None:
                return None

            cur.execute(
                """
                INSERT INTO public.analytics_event_outbox (
                    event_id, event_type, payload
                )
                VALUES (%s, %s, %s)
                """,
                (
                    UUID(notification_event["event_id"]),
                    notification_event["event_type"],
                    Jsonb(notification_event),
                ),
            )
            return row[0]


def get_ai_events(
    node_ids: list[str],
    start: datetime,
    end: datetime,
    source_type: str | None = None,
    event_type: str | None = None,
    camera_id: str | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[tuple]:
    if not node_ids:
        return []

    query = """
        SELECT
            id, source_type, camera_id, event_type, label, confidence,
            observed_at, farm_id, farm_code, farm_name, zone_id, zone_code,
            zone_name, payload
        FROM public.ai_events
        WHERE camera_id = ANY(%s)
          AND observed_at >= %s
          AND observed_at < %s
    """
    params: list[Any] = [node_ids, start, end]
    if source_type is not None:
        query += " AND source_type = %s"
        params.append(source_type)
    if event_type is not None:
        query += " AND event_type = %s"
        params.append(event_type)
    if camera_id is not None:
        query += " AND camera_id = %s"
        params.append(camera_id)
    query += " ORDER BY observed_at DESC, id DESC LIMIT %s OFFSET %s"
    params.extend((limit, offset))

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            return cur.fetchall()


def get_ai_event_by_id(
    node_ids: list[str],
    event_id: UUID,
) -> tuple | None:
    if not node_ids:
        return None

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id, source_type, camera_id, event_type, label, confidence,
                    observed_at, farm_id, farm_code, farm_name, zone_id,
                    zone_code, zone_name, payload
                FROM public.ai_events
                WHERE id = %s
                  AND camera_id = ANY(%s)
                """,
                (event_id, node_ids),
            )
            return cur.fetchone()


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
    camera_id: str | None = None,
) -> list[tuple]:
    if not node_ids:
        return []

    if camera_id is not None and camera_id not in node_ids:
        return []
    scoped_node_ids = [camera_id] if camera_id is not None else node_ids
    if not scoped_node_ids:
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
                (
                    scoped_node_ids,
                    start,
                    scoped_node_ids,
                    start,
                    end,
                    bucket,
                    start,
                ),
            )
            return cur.fetchall()


def save_bird_track_points(
    *,
    camera_id: str,
    observed_at: datetime,
    detections: list[dict[str, Any]],
    context: dict[str, Any],
) -> tuple[int, int]:
    accepted = 0
    duplicates = 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            for detection in detections:
                track_id = detection.get("track_id")
                object_class = detection["object_class"]
                if track_id is None or object_class.casefold() != "swiftlet":
                    continue

                bbox = detection["bbox"]
                center_x = (bbox[0] + bbox[2]) / 2
                center_y = (bbox[1] + bbox[3]) / 2
                identity = json.dumps(
                    {
                        "camera_id": camera_id,
                        "track_id": track_id,
                        "observed_at": observed_at.isoformat(),
                        "object_class": object_class,
                        "confidence": detection["confidence"],
                        "bbox": bbox,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                point_key = hashlib.sha256(
                    identity.encode("utf-8"),
                ).hexdigest()
                cur.execute(
                    """
                    INSERT INTO public.bird_track_points (
                        point_key, camera_id, track_id, object_class,
                        confidence, observed_at, center_x, center_y, bbox,
                        farm_id, farm_name, zone_id, zone_name
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s)
                    ON CONFLICT (point_key) DO NOTHING
                    """,
                    (
                        point_key,
                        camera_id,
                        track_id,
                        object_class,
                        detection["confidence"],
                        observed_at,
                        center_x,
                        center_y,
                        Jsonb(list(bbox)),
                        UUID(context["farm_id"]),
                        context["farm_name"],
                        UUID(context["zone_id"]) if context["zone_id"] else None,
                        context.get("zone_name"),
                    ),
                )
                if cur.rowcount:
                    accepted += 1
                else:
                    duplicates += 1
    return accepted, duplicates


def get_bird_movement_history(
    camera_id: str,
    start: datetime,
    end: datetime,
    track_id: int | None = None,
    limit: int = 500,
) -> list[tuple]:
    query = """
        SELECT
            camera_id, track_id, object_class, confidence, observed_at,
            center_x, center_y, bbox, farm_id, farm_name, zone_id, zone_name
        FROM public.bird_track_points
        WHERE camera_id = %s
          AND observed_at >= %s
          AND observed_at < %s
    """
    params: list[Any] = [camera_id, start, end]
    if track_id is not None:
        query += " AND track_id = %s"
        params.append(track_id)
    query += " ORDER BY observed_at DESC, track_id LIMIT %s"
    params.append(limit)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
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
