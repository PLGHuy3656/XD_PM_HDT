"""Repository abstractions and PostgreSQL implementation for durable AIEvent records (CP8.2)."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional, Protocol

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.config import settings
from app.database import get_connection
from app.ports.metadata_resolver import (
    CameraMetadataResolver,
    default_camera_metadata_resolver,
)
from app.schemas.canonical import AIEvent, BoundingBox, epoch_to_iso8601_utc

logger = logging.getLogger("ai_service.repository.ai_event")


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


def _normalize_snapshot_ref(raw_ref: Optional[str]) -> Optional[str]:
    if not raw_ref:
        return None
    cleaned = raw_ref.strip()
    if not cleaned:
        return None
    if cleaned.startswith(("/", "http://", "https://")):
        return cleaned
    filename = cleaned.replace("\\", "/").rsplit("/", 1)[-1]
    return f"/api/v1/ai/snapshots/{filename}"


class AIEventRepository(Protocol):
    """Abstract protocol for durable AIEvent persistence."""

    def save(self, event: AIEvent) -> bool:
        """Idempotently persists an AIEvent by eventId.

        Returns True if a new row was inserted, False if eventId already existed.
        """
        ...

    def get(self, event_id: str) -> Optional[AIEvent]:
        """Retrieves an AIEvent by its unique eventId."""
        ...

    def list_recent(
        self,
        camera_id: Optional[str] = None,
        farm_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AIEvent]:
        """Lists recent AIEvent records ordered newest first."""
        ...

    def list_by_camera(self, camera_id: str, limit: int = 100) -> List[AIEvent]:
        """Lists recent AIEvent records for a camera, newest first."""
        ...

    def list_by_farm(self, farm_id: str, limit: int = 100) -> List[AIEvent]:
        """Lists recent AIEvent records for a farm, newest first."""
        ...

    def list_by_time_range(
        self,
        start_time: datetime | str,
        end_time: datetime | str,
        camera_id: Optional[str] = None,
        limit: int = 500,
    ) -> List[AIEvent]:
        """Lists AIEvent records within [start_time, end_time], newest first."""
        ...

    def clear(self) -> None:
        """Clears all AIEvent records (for test isolation)."""
        ...


class InMemoryAIEventRepository:
    """In-memory implementation of AIEventRepository for isolated unit tests."""

    def __init__(self) -> None:
        self._events_by_id: Dict[str, AIEvent] = {}
        self._order: List[str] = []

    def save(self, event: AIEvent) -> bool:
        if event.eventId in self._events_by_id:
            return False
        sanitized = event.model_copy(
            update={"snapshot": _normalize_snapshot_ref(event.snapshot)}
        )
        self._events_by_id[event.eventId] = sanitized
        self._order.append(event.eventId)
        return True

    def get(self, event_id: str) -> Optional[AIEvent]:
        return self._events_by_id.get(event_id)

    def list_recent(
        self,
        camera_id: Optional[str] = None,
        farm_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AIEvent]:
        items = [self._events_by_id[eid] for eid in reversed(self._order) if eid in self._events_by_id]
        if camera_id is not None:
            items = [e for e in items if e.cameraId == camera_id]
        if farm_id is not None:
            items = [e for e in items if e.farmId == farm_id]
        items.sort(key=lambda e: _parse_iso_to_utc(e.detectedAt), reverse=True)
        return items[:limit]

    def list_by_camera(self, camera_id: str, limit: int = 100) -> List[AIEvent]:
        return self.list_recent(camera_id=camera_id, limit=limit)

    def list_by_farm(self, farm_id: str, limit: int = 100) -> List[AIEvent]:
        return self.list_recent(farm_id=farm_id, limit=limit)

    def list_by_time_range(
        self,
        start_time: datetime | str,
        end_time: datetime | str,
        camera_id: Optional[str] = None,
        limit: int = 500,
    ) -> List[AIEvent]:
        s_dt = _parse_iso_to_utc(start_time)
        e_dt = _parse_iso_to_utc(end_time)
        items = [
            e
            for e in self._events_by_id.values()
            if s_dt <= _parse_iso_to_utc(e.detectedAt) <= e_dt
            and (camera_id is None or e.cameraId == camera_id)
        ]
        items.sort(key=lambda e: _parse_iso_to_utc(e.detectedAt), reverse=True)
        return items[:limit]

    def clear(self) -> None:
        self._events_by_id.clear()
        self._order.clear()


class PostgreSQLAIEventRepository:
    """Durable PostgreSQL repository for AIEvent records in ai_db.ai_events (CP8.2)."""

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
    def _row_to_domain(row: dict[str, Any]) -> AIEvent:
        raw_bbox = row.get("bbox")
        if isinstance(raw_bbox, str):
            raw_bbox = json.loads(raw_bbox)
        if isinstance(raw_bbox, dict) and {"x1", "y1", "x2", "y2"}.issubset(raw_bbox.keys()):
            bbox = BoundingBox(
                x1=float(raw_bbox["x1"]),
                y1=float(raw_bbox["y1"]),
                x2=float(raw_bbox["x2"]),
                y2=float(raw_bbox["y2"]),
            )
        else:
            bbox = BoundingBox(
                x1=float(row["bbox_x1"]),
                y1=float(row["bbox_y1"]),
                x2=float(row["bbox_x2"]),
                y2=float(row["bbox_y2"]),
            )

        return AIEvent(
            **{
                "eventId": str(row["event_id"]),
                "eventType": row["event_type"],
                "cameraId": row["camera_id"],
                "farmId": row.get("farm_id"),
                "zoneId": row.get("zone_id"),
                "frameId": int(row["frame_id"]),
                "detectedAt": _dt_to_iso_utc(row["detected_at"]),
                "class": row["predator_class"],
                "confidence": float(row["confidence"]),
                "bbox": bbox,
                "snapshot": _normalize_snapshot_ref(row.get("snapshot_ref")),
            }
        )

    def save(self, event: AIEvent) -> bool:
        farm_id = event.farmId or self._metadata_resolver.resolve_farm_id(event.cameraId)
        zone_id = event.zoneId or self._metadata_resolver.resolve_zone_id(event.cameraId)
        detected_at_dt = _parse_iso_to_utc(event.detectedAt)
        snapshot_ref = _normalize_snapshot_ref(event.snapshot)
        bbox_dict = {
            "x1": event.bbox.x1,
            "y1": event.bbox.y1,
            "x2": event.bbox.x2,
            "y2": event.bbox.y2,
        }

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ai_events (
                        event_id, event_type, camera_id, farm_id, zone_id,
                        frame_id, predator_class, confidence,
                        bbox, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
                        snapshot_ref, detected_at
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s
                    )
                    ON CONFLICT (event_id) DO NOTHING
                    RETURNING event_id
                    """,
                    (
                        event.eventId,
                        event.eventType,
                        event.cameraId,
                        farm_id,
                        zone_id,
                        event.frameId,
                        event.cls,
                        event.confidence,
                        Jsonb(bbox_dict),
                        event.bbox.x1,
                        event.bbox.y1,
                        event.bbox.x2,
                        event.bbox.y2,
                        snapshot_ref,
                        detected_at_dt,
                    ),
                )
                inserted = cur.fetchone() is not None
            conn.commit()
        return inserted

    def get(self, event_id: str) -> Optional[AIEvent]:
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT
                        event_id, event_type, camera_id, farm_id, zone_id,
                        frame_id, predator_class, confidence,
                        bbox, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
                        snapshot_ref, detected_at, created_at
                    FROM ai_events
                    WHERE event_id = %s
                    """,
                    (event_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_domain(row)

    def list_recent(
        self,
        camera_id: Optional[str] = None,
        farm_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AIEvent]:
        query = """
            SELECT
                event_id, event_type, camera_id, farm_id, zone_id,
                frame_id, predator_class, confidence,
                bbox, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
                snapshot_ref, detected_at, created_at
            FROM ai_events
            WHERE 1=1
        """
        params: list[Any] = []
        if camera_id is not None:
            query += " AND camera_id = %s"
            params.append(camera_id)
        if farm_id is not None:
            query += " AND farm_id = %s"
            params.append(farm_id)
        query += " ORDER BY detected_at DESC, created_at DESC, event_id DESC LIMIT %s"
        params.append(limit)

        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, tuple(params))
                rows = cur.fetchall()
        return [self._row_to_domain(r) for r in rows]

    def list_by_camera(self, camera_id: str, limit: int = 100) -> List[AIEvent]:
        return self.list_recent(camera_id=camera_id, limit=limit)

    def list_by_farm(self, farm_id: str, limit: int = 100) -> List[AIEvent]:
        return self.list_recent(farm_id=farm_id, limit=limit)

    def list_by_time_range(
        self,
        start_time: datetime | str,
        end_time: datetime | str,
        camera_id: Optional[str] = None,
        limit: int = 500,
    ) -> List[AIEvent]:
        s_dt = _parse_iso_to_utc(start_time)
        e_dt = _parse_iso_to_utc(end_time)
        query = """
            SELECT
                event_id, event_type, camera_id, farm_id, zone_id,
                frame_id, predator_class, confidence,
                bbox, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
                snapshot_ref, detected_at, created_at
            FROM ai_events
            WHERE detected_at >= %s
              AND detected_at <= %s
        """
        params: list[Any] = [s_dt, e_dt]
        if camera_id is not None:
            query += " AND camera_id = %s"
            params.append(camera_id)
        query += " ORDER BY detected_at DESC, created_at DESC, event_id DESC LIMIT %s"
        params.append(limit)

        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, tuple(params))
                rows = cur.fetchall()
        return [self._row_to_domain(r) for r in rows]

    def clear(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM ai_events")
            conn.commit()


default_ai_event_repository: AIEventRepository = (
    PostgreSQLAIEventRepository()
    if settings.ai_database_url
    else InMemoryAIEventRepository()
)

__all__ = [
    "AIEventRepository",
    "InMemoryAIEventRepository",
    "PostgreSQLAIEventRepository",
    "default_ai_event_repository",
]
