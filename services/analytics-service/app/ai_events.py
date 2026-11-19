import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.repository import (
    get_ai_event_by_id,
    get_ai_events,
    save_ai_event,
)
from app.services import PERIODS


EVENT_TYPES = {
    ("vision", "PREDATOR_DETECTED"): "ai.threat.detected",
    ("vision", "FLOCK_ANOMALY"): "ai.flock.anomaly_detected",
    ("audio", "AUDIO_ANOMALY"): "audio.anomaly.detected",
}


def event_fingerprint(
    source_type: str,
    source_event_id: UUID | None,
    payload: dict[str, Any],
) -> str:
    identity = (
        f"{source_type}:{source_event_id}"
        if source_event_id is not None
        else json.dumps(
            {"source_type": source_type, "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def store_ai_event(
    source_type: Literal["vision", "audio"],
    event: Any,
    context: dict[str, Any],
) -> UUID | None:
    payload = event.model_dump(
        mode="json",
        by_alias=True,
        exclude_none=True,
    )
    notification_event_type = EVENT_TYPES[(source_type, event.event_type)]
    notification_event_id = uuid4()
    observed_at = datetime.fromtimestamp(event.timestamp, tz=timezone.utc)

    if source_type == "vision":
        label = event.object_class
        data = {
            "node_id": context["node_id"],
            "camera_id": event.camera_id,
            "farm_id": context["farm_id"],
            "farm_code": context["farm_code"],
            "farm_name": context["farm_name"],
            "zone_id": context.get("zone_id"),
            "zone_code": context.get("zone_code"),
            "zone_name": context.get("zone_name"),
            "threat_type": label,
            "label": label,
            "confidence": event.confidence,
            "timestamp": observed_at.isoformat(),
            "snapshot": event.snapshot,
            "bbox": list(event.bbox) if event.bbox else None,
            "track_id": event.track_id,
            "detail": event.detail,
        }
    else:
        label = event.label
        data = {
            "node_id": context["node_id"],
            "camera_id": event.camera_id,
            "farm_id": context["farm_id"],
            "farm_code": context["farm_code"],
            "farm_name": context["farm_name"],
            "zone_id": context.get("zone_id"),
            "zone_code": context.get("zone_code"),
            "zone_name": context.get("zone_name"),
            "label": label,
            "confidence": event.confidence,
            "audio_rms": event.audio_rms,
            "threshold": event.threshold,
            "timestamp": observed_at.isoformat(),
            "detail": event.detail,
        }

    notification_event = {
        "event_id": str(notification_event_id),
        "event_type": notification_event_type,
        "recipient_user_ids": context["recipient_user_ids"],
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "data": {
            key: value
            for key, value in data.items()
            if value is not None
        },
    }

    return save_ai_event(
        event_key=event_fingerprint(source_type, event.event_id, payload),
        source_event_id=event.event_id,
        source_type=source_type,
        camera_id=event.camera_id,
        event_type=event.event_type,
        label=label,
        confidence=event.confidence,
        observed_at=observed_at,
        context=context,
        payload=payload,
        notification_event=notification_event,
    )


def ensure_event_timestamp_is_not_future(timestamp: int) -> None:
    event_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    if event_time > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="AI event timestamp cannot be more than five minutes "
            "in the future",
        )


def get_ai_events_data(
    node_ids: list[str],
    period: str,
    source_type: str | None,
    now: datetime | None = None,
    *,
    event_type: str | None = None,
    camera_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[dict[str, Any]]:
    if start is None or end is None:
        duration, _ = PERIODS[period]
        end = now or datetime.now(timezone.utc)
        start = end - duration

    rows = get_ai_events(
        node_ids,
        start,
        end,
        source_type,
        event_type,
        camera_id,
        limit,
        offset,
    )
    return [_serialize_ai_event(row) for row in rows]


def get_ai_event_detail_data(
    node_ids: list[str],
    event_id: UUID,
) -> dict[str, Any] | None:
    row = get_ai_event_by_id(node_ids, event_id)
    return _serialize_ai_event(row) if row is not None else None


def _serialize_ai_event(row: tuple) -> dict[str, Any]:
    return {
        "id": str(row[0]),
        "source_type": row[1],
        "camera_id": row[2],
        "event_type": row[3],
        "label": row[4],
        "confidence": float(row[5]),
        "observed_at": row[6].isoformat(),
        "farm_id": str(row[7]),
        "farm_code": row[8],
        "farm_name": row[9],
        "zone_id": str(row[10]) if row[10] else None,
        "zone_code": row[11],
        "zone_name": row[12],
        "payload": row[13],
    }
