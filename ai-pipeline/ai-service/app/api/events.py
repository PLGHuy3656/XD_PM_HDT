"""AI-originated events REST routes `/api/v1/ai/events` (CP5.3 Task 7)."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Path, Query

from app.dependencies import get_state_store
from app.errors import EVENT_NOT_FOUND, ErrorResponse, raise_ai_error
from app.runtime.camera_pipeline import CameraPipeline
from app.runtime.state_store import InMemoryAIRuntimeStateStore
from app.schemas.canonical import AIEvent

router = APIRouter(prefix="/api/v1/ai/events", tags=["AI Events"])


def _sanitize_event_snapshot(event: AIEvent) -> AIEvent:
    """Ensure public API responses never expose raw filesystem paths in `snapshot`."""
    if not event.snapshot:
        return event
    safe_ref = CameraPipeline.normalize_snapshot_ref(event.snapshot)
    if safe_ref == event.snapshot:
        return event
    return event.model_copy(update={"snapshot": safe_ref})


@router.get(
    "",
    response_model=List[AIEvent],
    response_model_by_alias=True,
    summary="List recent canonical AIEvent records",
)
def list_events(
    cameraId: Optional[str] = Query(
        default=None,
        description="Optional cameraId filter",
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
        description="Maximum number of recent events to return",
    ),
    state_store: InMemoryAIRuntimeStateStore = Depends(get_state_store),
) -> List[AIEvent]:
    events = state_store.list_events(camera_id=cameraId, limit=limit)
    return [_sanitize_event_snapshot(e) for e in events]


@router.get(
    "/{eventId}",
    response_model=AIEvent,
    response_model_by_alias=True,
    responses={404: {"model": ErrorResponse}},
    summary="Get a single AIEvent by eventId",
)
def get_event_by_id(
    eventId: str = Path(..., description="Unique AI event identifier"),
    state_store: InMemoryAIRuntimeStateStore = Depends(get_state_store),
) -> AIEvent:
    event = state_store.get_event(eventId)
    if event is None:
        raise_ai_error(
            404,
            EVENT_NOT_FOUND,
            f"AI event '{eventId}' was not found.",
        )
    return _sanitize_event_snapshot(event)
