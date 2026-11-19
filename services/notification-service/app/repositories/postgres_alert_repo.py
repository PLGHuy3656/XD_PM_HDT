"""PostgreSQL durable repository for Alert domain entities (CP8.3)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

import psycopg
from psycopg.types.json import Jsonb

from app.database import get_connection
from app.domain.enums import AlertEventType, AlertSeverity, AlertSource, AlertStatus
from app.ports.alert_repository import AlertRepository
from app.schemas.canonical import Alert

logger = logging.getLogger("notification_service.repositories.alert")


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _row_to_alert(row: tuple[Any, ...]) -> Alert:
    return Alert(
        alert_id=row[0],
        event_type=AlertEventType(row[1]),
        source=AlertSource(row[2]),
        severity=AlertSeverity(row[3]),
        status=AlertStatus(row[4]),
        farm_id=row[5],
        zone_id=row[6],
        device_id=row[7],
        camera_id=row[8],
        title=row[9],
        message=row[10],
        snapshot_url=row[11],
        telemetry_snapshot=row[12],
        occurrence_count=int(row[13]),
        created_at=_ensure_utc(row[14]),
        updated_at=_ensure_utc(row[15]),
        last_occurred_at=_ensure_utc(row[16]),
        acknowledged_at=_ensure_utc(row[17]),
        acknowledged_by=row[18],
        resolved_at=_ensure_utc(row[19]),
        resolved_by=row[20],
        resolution_note=row[21],
        source_event_id=row[22],
        metadata=row[23] if row[23] is not None else {},
    )


_SELECT_COLUMNS = """
    alert_id,
    event_type,
    source,
    severity,
    status,
    farm_id,
    zone_id,
    device_id,
    camera_id,
    title,
    message,
    snapshot_url,
    telemetry_snapshot,
    occurrence_count,
    created_at,
    updated_at,
    last_occurred_at,
    acknowledged_at,
    acknowledged_by,
    resolved_at,
    resolved_by,
    resolution_note,
    source_event_id,
    metadata
"""


class PostgreSQLAlertRepository(AlertRepository):
    """Durable PostgreSQL implementation of AlertRepository backed by `notification_db.alerts`."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        self._database_url = database_url

    def _connect(self) -> psycopg.Connection:
        return get_connection(self._database_url)

    def save(self, alert: Alert) -> Alert:
        """Persist or update an Alert in `notification_db.alerts`.

        Handles active deduplication atomically: if a concurrent transaction
        already inserted an OPEN/ACKNOWLEDGED alert for the same deduplication key
        (`uq_alerts_active_dedup_key`), merges into that active alert by
        incrementing `occurrence_count` and updating `last_occurred_at`.
        """
        created_at = _ensure_utc(alert.created_at) or datetime.now(timezone.utc)
        updated_at = _ensure_utc(alert.updated_at) or datetime.now(timezone.utc)
        last_occurred_at = _ensure_utc(alert.last_occurred_at) or created_at
        acknowledged_at = _ensure_utc(alert.acknowledged_at)
        resolved_at = _ensure_utc(alert.resolved_at)
        telemetry_json = Jsonb(alert.telemetry_snapshot) if alert.telemetry_snapshot is not None else None
        metadata_json = Jsonb(alert.metadata or {})

        try:
            with self._connect() as conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            f"""
                            INSERT INTO alerts (
                                alert_id,
                                event_type,
                                source,
                                severity,
                                status,
                                farm_id,
                                zone_id,
                                device_id,
                                camera_id,
                                title,
                                message,
                                snapshot_url,
                                telemetry_snapshot,
                                occurrence_count,
                                created_at,
                                updated_at,
                                last_occurred_at,
                                acknowledged_at,
                                acknowledged_by,
                                resolved_at,
                                resolved_by,
                                resolution_note,
                                source_event_id,
                                metadata
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                            )
                            ON CONFLICT (alert_id) DO UPDATE SET
                                event_type = EXCLUDED.event_type,
                                source = EXCLUDED.source,
                                severity = EXCLUDED.severity,
                                status = EXCLUDED.status,
                                farm_id = EXCLUDED.farm_id,
                                zone_id = EXCLUDED.zone_id,
                                device_id = EXCLUDED.device_id,
                                camera_id = EXCLUDED.camera_id,
                                title = EXCLUDED.title,
                                message = EXCLUDED.message,
                                snapshot_url = EXCLUDED.snapshot_url,
                                telemetry_snapshot = EXCLUDED.telemetry_snapshot,
                                occurrence_count = EXCLUDED.occurrence_count,
                                updated_at = EXCLUDED.updated_at,
                                last_occurred_at = EXCLUDED.last_occurred_at,
                                acknowledged_at = EXCLUDED.acknowledged_at,
                                acknowledged_by = EXCLUDED.acknowledged_by,
                                resolved_at = EXCLUDED.resolved_at,
                                resolved_by = EXCLUDED.resolved_by,
                                resolution_note = EXCLUDED.resolution_note,
                                source_event_id = EXCLUDED.source_event_id,
                                metadata = EXCLUDED.metadata
                            RETURNING {_SELECT_COLUMNS}
                            """,
                            (
                                alert.alert_id,
                                alert.event_type.value,
                                alert.source.value,
                                alert.severity.value,
                                alert.status.value,
                                alert.farm_id,
                                alert.zone_id,
                                alert.device_id,
                                alert.camera_id,
                                alert.title,
                                alert.message,
                                alert.snapshot_url,
                                telemetry_json,
                                alert.occurrence_count,
                                created_at,
                                updated_at,
                                last_occurred_at,
                                acknowledged_at,
                                alert.acknowledged_by,
                                resolved_at,
                                alert.resolved_by,
                                alert.resolution_note,
                                alert.source_event_id,
                                metadata_json,
                            ),
                        )
                        row = cur.fetchone()
                    conn.commit()
                    assert row is not None
                    return _row_to_alert(row)
                except psycopg.errors.UniqueViolation:
                    # Concurrent active alert inserted on uq_alerts_active_dedup_key:
                    # Rollback failed statement and atomically merge into active alert.
                    conn.rollback()
                    target_zone = alert.zone_id or ""
                    target_source_id = alert.device_id or alert.camera_id or ""
                    with conn.cursor() as cur:
                        cur.execute(
                            f"""
                            UPDATE alerts
                            SET occurrence_count = occurrence_count + 1,
                                last_occurred_at = GREATEST(last_occurred_at, %s),
                                updated_at = %s,
                                snapshot_url = COALESCE(snapshot_url, %s),
                                telemetry_snapshot = COALESCE(%s, telemetry_snapshot)
                            WHERE farm_id = %s
                              AND COALESCE(zone_id, '') = %s
                              AND COALESCE(device_id, camera_id, '') = %s
                              AND event_type = %s
                              AND status IN ('OPEN', 'ACKNOWLEDGED')
                            RETURNING {_SELECT_COLUMNS}
                            """,
                            (
                                last_occurred_at,
                                updated_at,
                                alert.snapshot_url,
                                telemetry_json,
                                alert.farm_id,
                                target_zone,
                                target_source_id,
                                alert.event_type.value,
                            ),
                        )
                        merged_row = cur.fetchone()
                    conn.commit()
                    if merged_row is not None:
                        return _row_to_alert(merged_row)
                    raise
        except Exception as exc:
            logger.error(
                "[NOTIFICATION ALERT PERSISTENCE FAILED] Failed to save Alert alertId='%s' farmId='%s': %s",
                alert.alert_id,
                alert.farm_id,
                exc,
            )
            raise

    def get_by_id(self, alert_id: str) -> Optional[Alert]:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT {_SELECT_COLUMNS} FROM alerts WHERE alert_id = %s",
                        (alert_id,),
                    )
                    row = cur.fetchone()
                    return _row_to_alert(row) if row is not None else None
        except Exception as exc:
            logger.error(
                "[NOTIFICATION ALERT QUERY FAILED] Failed to query Alert alertId='%s': %s",
                alert_id,
                exc,
            )
            raise

    def find_active_by_dedup_key(
        self,
        farm_id: str,
        zone_id: Optional[str],
        device_id: Optional[str],
        event_type: AlertEventType,
    ) -> Optional[Alert]:
        target_zone = zone_id or ""
        target_device = device_id or ""
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT {_SELECT_COLUMNS}
                        FROM alerts
                        WHERE farm_id = %s
                          AND COALESCE(zone_id, '') = %s
                          AND COALESCE(device_id, camera_id, '') = %s
                          AND event_type = %s
                          AND status IN ('OPEN', 'ACKNOWLEDGED')
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        (farm_id, target_zone, target_device, event_type.value),
                    )
                    row = cur.fetchone()
                    return _row_to_alert(row) if row is not None else None
        except Exception as exc:
            logger.error(
                "[NOTIFICATION ALERT DEDUP QUERY FAILED] Failed to lookup active Alert for farmId='%s' eventType='%s': %s",
                farm_id,
                event_type.value,
                exc,
            )
            raise

    def list_alerts(
        self,
        farm_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        status: Optional[AlertStatus] = None,
        severity: Optional[AlertSeverity] = None,
        event_type: Optional[AlertEventType] = None,
        source: Optional[AlertSource] = None,
        limit: int = 100,
        offset: int = 0,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Alert]:
        clauses: list[str] = []
        params: list[Any] = []

        if farm_id is not None:
            clauses.append("farm_id = %s")
            params.append(farm_id)
        if zone_id is not None:
            clauses.append("zone_id = %s")
            params.append(zone_id)
        if status is not None:
            clauses.append("status = %s")
            params.append(status.value if isinstance(status, AlertStatus) else str(status))
        if severity is not None:
            clauses.append("severity = %s")
            params.append(severity.value if isinstance(severity, AlertSeverity) else str(severity))
        if event_type is not None:
            clauses.append("event_type = %s")
            params.append(event_type.value if isinstance(event_type, AlertEventType) else str(event_type))
        if source is not None:
            clauses.append("source = %s")
            params.append(source.value if isinstance(source, AlertSource) else str(source))
        if start_time is not None:
            clauses.append("created_at >= %s")
            params.append(_ensure_utc(start_time))
        if end_time is not None:
            clauses.append("created_at <= %s")
            params.append(_ensure_utc(end_time))

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, offset])

        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT {_SELECT_COLUMNS}
                        FROM alerts
                        {where_sql}
                        ORDER BY created_at DESC, alert_id DESC
                        LIMIT %s OFFSET %s
                        """,
                        tuple(params),
                    )
                    rows = cur.fetchall()
                    return [_row_to_alert(r) for r in rows]
        except Exception as exc:
            logger.error("[NOTIFICATION ALERT LIST FAILED] Failed to list Alerts: %s", exc)
            raise

    def list_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        farm_id: Optional[str] = None,
        status: Optional[AlertStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Alert]:
        return self.list_alerts(
            farm_id=farm_id,
            status=status,
            limit=limit,
            offset=offset,
            start_time=start_time,
            end_time=end_time,
        )

    def count_alerts(
        self,
        farm_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        status: Optional[AlertStatus] = None,
        severity: Optional[AlertSeverity] = None,
        event_type: Optional[AlertEventType] = None,
        source: Optional[AlertSource] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        clauses: list[str] = []
        params: list[Any] = []

        if farm_id is not None:
            clauses.append("farm_id = %s")
            params.append(farm_id)
        if zone_id is not None:
            clauses.append("zone_id = %s")
            params.append(zone_id)
        if status is not None:
            clauses.append("status = %s")
            params.append(status.value if isinstance(status, AlertStatus) else str(status))
        if severity is not None:
            clauses.append("severity = %s")
            params.append(severity.value if isinstance(severity, AlertSeverity) else str(severity))
        if event_type is not None:
            clauses.append("event_type = %s")
            params.append(event_type.value if isinstance(event_type, AlertEventType) else str(event_type))
        if source is not None:
            clauses.append("source = %s")
            params.append(source.value if isinstance(source, AlertSource) else str(source))
        if start_time is not None:
            clauses.append("created_at >= %s")
            params.append(_ensure_utc(start_time))
        if end_time is not None:
            clauses.append("created_at <= %s")
            params.append(_ensure_utc(end_time))

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT COUNT(*) FROM alerts {where_sql}",
                        tuple(params),
                    )
                    row = cur.fetchone()
                    return int(row[0]) if row else 0
        except Exception as exc:
            logger.error("[NOTIFICATION ALERT COUNT FAILED] Failed to count Alerts: %s", exc)
            raise


__all__ = ["PostgreSQLAlertRepository"]
