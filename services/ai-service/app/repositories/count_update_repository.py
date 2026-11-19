"""Repository abstractions and PostgreSQL implementation for durable CountUpdate records (CP8.2)."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, List, Optional, Protocol
import uuid

from psycopg.rows import dict_row

from app.config import settings
from app.database import get_connection
from app.ports.metadata_resolver import (
    CameraMetadataResolver,
    default_camera_metadata_resolver,
)
from app.schemas.canonical import CountUpdate, epoch_to_iso8601_utc

logger = logging.getLogger("ai_service.repository.count_update")


def _parse_iso_to_utc(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    raw = str(value).strip()
    candidate = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    dt = datetime.fromisoformat(candidate)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _dt_to_iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return epoch_to_iso8601_utc(dt.timestamp())


class CountUpdateRepository(Protocol):
    """Abstract protocol for durable CountUpdate persistence."""

    def save(self, update: CountUpdate) -> str:
        """Persists a CountUpdate record and returns its durable row UUID string."""
        ...

    def get_latest_by_camera(self, camera_id: str) -> Optional[CountUpdate]:
        """Retrieves the most recent CountUpdate for a camera."""
        ...

    def list_by_camera(self, camera_id: str, limit: int = 100) -> List[CountUpdate]:
        """Lists recent CountUpdate records for a camera, newest first."""
        ...

    def list_by_farm(self, farm_id: str, limit: int = 100) -> List[CountUpdate]:
        """Lists recent CountUpdate records for a farm, newest first."""
        ...

    def list_by_zone(self, zone_id: str, limit: int = 100) -> List[CountUpdate]:
        """Lists recent CountUpdate records for a zone, newest first."""
        ...

    def list_by_time_range(
        self,
        camera_id: str,
        start_time: datetime | str,
        end_time: datetime | str,
        limit: int = 500,
    ) -> List[CountUpdate]:
        """Lists CountUpdate records for a camera within [start_time, end_time], newest first."""
        ...

    def clear(self) -> None:
        """Clears all CountUpdate records (for test isolation)."""
        ...


class InMemoryCountUpdateRepository:
    """In-memory implementation of CountUpdateRepository for isolated unit tests."""

    def __init__(self) -> None:
        self._records: List[CountUpdate] = []

    def save(self, update: CountUpdate) -> str:
        self._records.append(update)
        return str(uuid.uuid4())

    def get_latest_by_camera(self, camera_id: str) -> Optional[CountUpdate]:
        items = self.list_by_camera(camera_id, limit=1)
        return items[0] if items else None

    def list_by_camera(self, camera_id: str, limit: int = 100) -> List[CountUpdate]:
        items = [r for r in self._records if r.cameraId == camera_id]
        items.sort(key=lambda r: _parse_iso_to_utc(r.recordedAt), reverse=True)
        return items[:limit]

    def list_by_farm(self, farm_id: str, limit: int = 100) -> List[CountUpdate]:
        items = [r for r in self._records if r.farmId == farm_id]
        items.sort(key=lambda r: _parse_iso_to_utc(r.recordedAt), reverse=True)
        return items[:limit]

    def list_by_zone(self, zone_id: str, limit: int = 100) -> List[CountUpdate]:
        items = [r for r in self._records if r.zoneId == zone_id]
        items.sort(key=lambda r: _parse_iso_to_utc(r.recordedAt), reverse=True)
        return items[:limit]

    def list_by_time_range(
        self,
        camera_id: str,
        start_time: datetime | str,
        end_time: datetime | str,
        limit: int = 500,
    ) -> List[CountUpdate]:
        s_dt = _parse_iso_to_utc(start_time)
        e_dt = _parse_iso_to_utc(end_time)
        items = [
            r
            for r in self._records
            if r.cameraId == camera_id
            and s_dt <= _parse_iso_to_utc(r.recordedAt) <= e_dt
        ]
        items.sort(key=lambda r: _parse_iso_to_utc(r.recordedAt), reverse=True)
        return items[:limit]

    def clear(self) -> None:
        self._records.clear()


class PostgreSQLCountUpdateRepository:
    """Durable PostgreSQL repository for CountUpdate records in ai_db.ai_count_updates (CP8.2)."""

    def __init__(
        self,
        database_url: Optional[str] = None,
        metadata_resolver: Optional[CameraMetadataResolver] = None,
    ) -> None:
        self._database_url = database_url
        self._metadata_resolver = metadata_resolver or default_camera_metadata_resolver

    def _connect(self):
        return get_connection(self._database_url)

    @staticmethod
    def _row_to_domain(row: dict[str, Any]) -> CountUpdate:
        return CountUpdate(
            cameraId=row["camera_id"],
            farmId=row.get("farm_id"),
            zoneId=row.get("zone_id"),
            frameId=int(row["frame_id"]),
            recordedAt=_dt_to_iso_utc(row["recorded_at"]),
            windowStartedAt=_dt_to_iso_utc(row["window_started_at"]),
            entryCount=int(row["entry_count"]),
            exitCount=int(row["exit_count"]),
            netChange=int(row["net_change"]),
            deltaEntry=int(row["delta_entry"]),
            deltaExit=int(row["delta_exit"]),
        )

    def save(self, update: CountUpdate) -> str:
        row_id = str(uuid.uuid4())
        farm_id = update.farmId or self._metadata_resolver.resolve_farm_id(update.cameraId)
        zone_id = update.zoneId or self._metadata_resolver.resolve_zone_id(update.cameraId)
        recorded_at_dt = _parse_iso_to_utc(update.recordedAt)
        window_started_dt = _parse_iso_to_utc(update.windowStartedAt)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ai_count_updates (
                        id, camera_id, farm_id, zone_id, frame_id,
                        entry_count, exit_count, net_change,
                        delta_entry, delta_exit,
                        window_started_at, recorded_at
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s
                    )
                    """,
                    (
                        row_id,
                        update.cameraId,
                        farm_id,
                        zone_id,
                        update.frameId,
                        update.entryCount,
                        update.exitCount,
                        update.netChange,
                        update.deltaEntry,
                        update.deltaExit,
                        window_started_dt,
                        recorded_at_dt,
                    ),
                )
            conn.commit()
        return row_id

    def get_latest_by_camera(self, camera_id: str) -> Optional[CountUpdate]:
        rows = self.list_by_camera(camera_id, limit=1)
        return rows[0] if rows else None

    def list_by_camera(self, camera_id: str, limit: int = 100) -> List[CountUpdate]:
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT
                        id, camera_id, farm_id, zone_id, frame_id,
                        entry_count, exit_count, net_change,
                        delta_entry, delta_exit,
                        window_started_at, recorded_at, created_at
                    FROM ai_count_updates
                    WHERE camera_id = %s
                    ORDER BY recorded_at DESC, created_at DESC, id DESC
                    LIMIT %s
                    """,
                    (camera_id, limit),
                )
                rows = cur.fetchall()
        return [self._row_to_domain(r) for r in rows]

    def list_by_farm(self, farm_id: str, limit: int = 100) -> List[CountUpdate]:
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT
                        id, camera_id, farm_id, zone_id, frame_id,
                        entry_count, exit_count, net_change,
                        delta_entry, delta_exit,
                        window_started_at, recorded_at, created_at
                    FROM ai_count_updates
                    WHERE farm_id = %s
                    ORDER BY recorded_at DESC, created_at DESC, id DESC
                    LIMIT %s
                    """,
                    (farm_id, limit),
                )
                rows = cur.fetchall()
        return [self._row_to_domain(r) for r in rows]

    def list_by_zone(self, zone_id: str, limit: int = 100) -> List[CountUpdate]:
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT
                        id, camera_id, farm_id, zone_id, frame_id,
                        entry_count, exit_count, net_change,
                        delta_entry, delta_exit,
                        window_started_at, recorded_at, created_at
                    FROM ai_count_updates
                    WHERE zone_id = %s
                    ORDER BY recorded_at DESC, created_at DESC, id DESC
                    LIMIT %s
                    """,
                    (zone_id, limit),
                )
                rows = cur.fetchall()
        return [self._row_to_domain(r) for r in rows]

    def list_by_time_range(
        self,
        camera_id: str,
        start_time: datetime | str,
        end_time: datetime | str,
        limit: int = 500,
    ) -> List[CountUpdate]:
        s_dt = _parse_iso_to_utc(start_time)
        e_dt = _parse_iso_to_utc(end_time)
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT
                        id, camera_id, farm_id, zone_id, frame_id,
                        entry_count, exit_count, net_change,
                        delta_entry, delta_exit,
                        window_started_at, recorded_at, created_at
                    FROM ai_count_updates
                    WHERE camera_id = %s
                      AND recorded_at >= %s
                      AND recorded_at <= %s
                    ORDER BY recorded_at DESC, created_at DESC, id DESC
                    LIMIT %s
                    """,
                    (camera_id, s_dt, e_dt, limit),
                )
                rows = cur.fetchall()
        return [self._row_to_domain(r) for r in rows]

    def clear(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM ai_count_updates")
            conn.commit()


default_count_update_repository: CountUpdateRepository = (
    PostgreSQLCountUpdateRepository()
    if settings.ai_database_url
    else InMemoryCountUpdateRepository()
)

__all__ = [
    "CountUpdateRepository",
    "InMemoryCountUpdateRepository",
    "PostgreSQLCountUpdateRepository",
    "default_count_update_repository",
]
