"""INT02 interactive camera sessions (internal API - called only by the API Gateway).

The Gateway authenticates the user, verifies camera ownership/assignment with Management and
passes the AUTHORITATIVE farmId/zoneId. This router:

* never accepts a source path or URL from the caller (no SSRF / arbitrary file read);
* requires X-Internal-Service-Key on every operation;
* keeps pushed frames in memory only (bounded queue, latest-wins, nothing written to disk).
"""
from __future__ import annotations

import threading
import time
from pathlib import Path as FsPath
from typing import Dict, Literal, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.cameras import _require_camera_control_auth
from app.config import settings
from app.dependencies import get_runtime_manager
from app.errors import IMAGE_TOO_LARGE, INVALID_IMAGE_PAYLOAD, UNSUPPORTED_MEDIA_TYPE, raise_ai_error
from app.runtime.manager import AIRuntimeManager
from app.schemas.canonical import CameraRuntimeStatus

router = APIRouter(prefix="/api/v1/ai/cameras", tags=["AI Camera Sessions (INT02, internal)"])

_last_frame_at: Dict[str, float] = {}
_rate_lock = threading.Lock()


class CameraSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["DEMO_VIDEO", "LOCAL_CAMERA"]
    farmId: Optional[str] = Field(default=None, max_length=64)
    zoneId: Optional[str] = Field(default=None, max_length=64)


@router.post(
    "/{cameraId}/sessions",
    response_model=CameraRuntimeStatus,
    summary="Start a DEMO_VIDEO or LOCAL_CAMERA session on the real AI pipeline",
)
def start_camera_session(
    cameraId: str = Path(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.\-]+$"),
    payload: CameraSessionRequest = Body(...),
    _: None = Depends(_require_camera_control_auth),
    runtime_manager: AIRuntimeManager = Depends(get_runtime_manager),
) -> CameraRuntimeStatus:
    if payload.mode == "DEMO_VIDEO" and not FsPath(settings.ai_demo_video_path).is_file():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "DEMO_VIDEO_UNAVAILABLE", "message": "Demo video is not provisioned on the AI Service"},
        )
    with _rate_lock:
        _last_frame_at.pop(cameraId, None)
    return runtime_manager.start_session(
        camera_id=cameraId,
        mode=payload.mode,
        demo_video_path=settings.ai_demo_video_path,
        farm_id=payload.farmId,
        zone_id=payload.zoneId,
        idle_timeout_s=settings.ai_local_session_idle_timeout_s,
    )


@router.post(
    "/{cameraId}/frames",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Push one JPEG/PNG frame into an active LOCAL_CAMERA session",
)
async def push_camera_frame(
    request: Request,
    cameraId: str = Path(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.\-]+$"),
    _: None = Depends(_require_camera_control_auth),
    runtime_manager: AIRuntimeManager = Depends(get_runtime_manager),
) -> dict:
    ctype = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if ctype not in ("image/jpeg", "image/png"):
        raise_ai_error(415, UNSUPPORTED_MEDIA_TYPE, "Frames must be image/jpeg or image/png")
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > settings.ai_local_frame_max_bytes:
        raise_ai_error(413, IMAGE_TOO_LARGE, "Frame exceeds the configured size limit")
    body = await request.body()
    if len(body) > settings.ai_local_frame_max_bytes:
        raise_ai_error(413, IMAGE_TOO_LARGE, "Frame exceeds the configured size limit")
    if not body:
        raise_ai_error(400, INVALID_IMAGE_PAYLOAD, "Empty frame")

    now = time.monotonic()
    with _rate_lock:
        last = _last_frame_at.get(cameraId)
        if last is not None and now - last < settings.ai_local_frame_min_interval_s:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": "FRAME_RATE_LIMITED", "message": "Frame rate limit exceeded"},
            )
        _last_frame_at[cameraId] = now

    try:
        ok = runtime_manager.push_frame(cameraId, body)
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "NO_ACTIVE_LOCAL_SESSION", "message": "No active LOCAL_CAMERA session for this camera"},
        )
    if not ok:
        raise_ai_error(400, INVALID_IMAGE_PAYLOAD, "Frame could not be decoded or exceeds 1280x960")
    return {"accepted": True, "cameraId": cameraId}
