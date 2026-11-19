"""Camera runtime status, latest detection, and latest count REST routes (CP5.3 Task 3, 4, 5, 6)."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Path, Query

from app.dependencies import (
    get_runtime_manager,
    get_state_store,
    is_camera_registered,
)
from app.errors import (
    CAMERA_NOT_FOUND,
    COUNT_NOT_AVAILABLE,
    DETECTION_NOT_AVAILABLE,
    ErrorResponse,
    raise_ai_error,
)
from app.runtime.manager import AIRuntimeManager
from app.runtime.state_store import InMemoryAIRuntimeStateStore
from app.schemas.canonical import (
    CameraRuntimeStatus,
    CountUpdate,
    DetectionResult,
)

router = APIRouter(prefix="/api/v1/ai/cameras", tags=["AI Cameras"])


@router.get(
    "",
    response_model=List[CameraRuntimeStatus],
    summary="List registered AI cameras and their current runtime status",
)
def list_cameras(
    runtime_manager: AIRuntimeManager = Depends(get_runtime_manager),
    state_store: InMemoryAIRuntimeStateStore = Depends(get_state_store),
) -> List[CameraRuntimeStatus]:
    """Return runtime status for all cameras registered in AIRuntimeManager / runtime state."""
    statuses_by_id = {s.cameraId: s for s in state_store.list_camera_statuses()}
    if not state_store.redis_enabled:
        for cam_id in runtime_manager.list_camera_ids():
            if cam_id not in statuses_by_id:
                pipeline = runtime_manager.get_pipeline(cam_id)
                if pipeline is not None:
                    statuses_by_id[cam_id] = pipeline.status
    return [statuses_by_id[k] for k in sorted(statuses_by_id.keys())]


@router.get(
    "/{cameraId}/status",
    response_model=CameraRuntimeStatus,
    responses={404: {"model": ErrorResponse}},
    summary="Get technical runtime status for a registered AI camera",
)
def get_camera_status(
    cameraId: str = Path(..., description="Canonical camera identifier"),
    runtime_manager: AIRuntimeManager = Depends(get_runtime_manager),
    state_store: InMemoryAIRuntimeStateStore = Depends(get_state_store),
) -> CameraRuntimeStatus:
    status = state_store.get_camera_status(cameraId)
    if status is not None:
        return status

    if not state_store.redis_enabled:
        pipeline = runtime_manager.get_pipeline(cameraId)
        if pipeline is not None:
            return pipeline.status

    raise_ai_error(
        404,
        CAMERA_NOT_FOUND,
        f"Camera '{cameraId}' is not registered in AI runtime.",
    )


@router.get(
    "/{cameraId}/detections/latest",
    response_model=DetectionResult,
    response_model_by_alias=True,
    responses={404: {"model": ErrorResponse}},
    summary="Get latest canonical DetectionResult for a camera",
)
def get_latest_detection(
    cameraId: str = Path(..., description="Canonical camera identifier"),
    runtime_manager: AIRuntimeManager = Depends(get_runtime_manager),
    state_store: InMemoryAIRuntimeStateStore = Depends(get_state_store),
) -> DetectionResult:
    if not is_camera_registered(cameraId, runtime_manager, state_store):
        raise_ai_error(
            404,
            CAMERA_NOT_FOUND,
            f"Camera '{cameraId}' is not registered in AI runtime.",
        )

    latest = state_store.get_latest_detection(cameraId)
    if latest is None:
        raise_ai_error(
            404,
            DETECTION_NOT_AVAILABLE,
            f"No detection result has been produced yet for camera '{cameraId}'.",
        )
    return latest


@router.get(
    "/{cameraId}/counts/latest",
    response_model=CountUpdate,
    responses={404: {"model": ErrorResponse}},
    summary="Get latest canonical CountUpdate for a camera",
)
def get_latest_count(
    cameraId: str = Path(..., description="Canonical camera identifier"),
    runtime_manager: AIRuntimeManager = Depends(get_runtime_manager),
    state_store: InMemoryAIRuntimeStateStore = Depends(get_state_store),
) -> CountUpdate:
    latest = state_store.get_latest_count(cameraId)
    if latest is not None:
        return latest

    if not is_camera_registered(cameraId, runtime_manager, state_store):
        raise_ai_error(
            404,
            CAMERA_NOT_FOUND,
            f"Camera '{cameraId}' is not registered in AI runtime.",
        )

    raise_ai_error(
        404,
        COUNT_NOT_AVAILABLE,
        f"No count update has been produced yet for camera '{cameraId}'.",
    )


@router.get(
    "/{cameraId}/counts",
    response_model=List[CountUpdate],
    responses={404: {"model": ErrorResponse}},
    summary="List recent durable CountUpdate history for a camera (CP8.2)",
)
def list_camera_counts(
    cameraId: str = Path(..., description="Canonical camera identifier"),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
        description="Maximum number of count records to return",
    ),
    startTime: Optional[str] = Query(
        default=None,
        description="Optional ISO-8601 UTC start time filter",
    ),
    endTime: Optional[str] = Query(
        default=None,
        description="Optional ISO-8601 UTC end time filter",
    ),
    runtime_manager: AIRuntimeManager = Depends(get_runtime_manager),
    state_store: InMemoryAIRuntimeStateStore = Depends(get_state_store),
) -> List[CountUpdate]:
    if not is_camera_registered(cameraId, runtime_manager, state_store):
        # Also allow querying historical counts if durable records exist for cameraId
        history = state_store.list_count_updates(
            camera_id=cameraId,
            limit=limit,
            start_time=startTime,
            end_time=endTime,
        )
        if not history:
            raise_ai_error(
                404,
                CAMERA_NOT_FOUND,
                f"Camera '{cameraId}' is not registered in AI runtime.",
            )
        return history

    return state_store.list_count_updates(
        camera_id=cameraId,
        limit=limit,
        start_time=startTime,
        end_time=endTime,
    )
