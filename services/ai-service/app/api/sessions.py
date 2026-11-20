"""INT02 interactive camera sessions (internal API - called only by the API Gateway).

The Gateway authenticates the user, verifies camera ownership/assignment with Management and
passes the AUTHORITATIVE farmId/zoneId. This router:

* never accepts a source path or URL from the caller (no SSRF / arbitrary file read);
* requires X-Internal-Service-Key on every operation;
* keeps pushed frames in memory only (bounded queue, latest-wins, nothing written to disk).
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from pathlib import Path as FsPath
from typing import Dict, Literal, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request, status
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


def _purge_stale_uploads(upload_dir: str, max_age_s: float) -> None:
    """Remove leftover temp uploads (e.g. after a crash); only our own generated names."""
    try:
        now = time.time()
        for name in os.listdir(upload_dir):
            if not (name.startswith("upl-") and name.endswith(".mp4")):
                continue
            full = os.path.join(upload_dir, name)
            try:
                if now - os.path.getmtime(full) > max_age_s:
                    os.remove(full)
            except OSError:
                pass
    except FileNotFoundError:
        pass


def _upload_error(code: int, err: str, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"code": err, "message": message})


@router.post(
    "/{cameraId}/uploads",
    response_model=CameraRuntimeStatus,
    summary="Upload a user video (MP4) and start an UPLOADED_VIDEO session on the real pipeline",
)
async def upload_camera_video(
    request: Request,
    cameraId: str = Path(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.\-]+$"),
    farmId: Optional[str] = Query(default=None, max_length=64),
    zoneId: Optional[str] = Query(default=None, max_length=64),
    _: None = Depends(_require_camera_control_auth),
    runtime_manager: AIRuntimeManager = Depends(get_runtime_manager),
) -> CameraRuntimeStatus:
    from app.runtime.session_sources import UploadedVideoError, UploadedVideoSource, probe_uploaded_video

    ctype = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if ctype != "video/mp4":
        raise _upload_error(415, "UNSUPPORTED_VIDEO_TYPE", "Chỉ hỗ trợ video MP4 (video/mp4)")
    limit = int(settings.ai_upload_max_bytes)
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise _upload_error(413, "VIDEO_TOO_LARGE", f"Video vượt giới hạn {limit // (1024 * 1024)} MB")
    if runtime_manager.active_upload_sessions() >= int(settings.ai_upload_max_sessions):
        raise _upload_error(429, "UPLOAD_CONCURRENCY_LIMIT", "Đang có quá nhiều phiên phân tích video, thử lại sau")

    upload_dir = settings.ai_upload_dir
    os.makedirs(upload_dir, mode=0o700, exist_ok=True)
    max_wall = float(settings.ai_upload_max_duration_s) * 3 + 60
    _purge_stale_uploads(upload_dir, max_wall + 60)
    # Server-generated name only: the client never influences the stored path
    path = os.path.join(upload_dir, f"upl-{uuid.uuid4().hex}.mp4")
    written = 0
    keep = False
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            async for chunk in request.stream():
                written += len(chunk)
                if written > limit:
                    raise _upload_error(413, "VIDEO_TOO_LARGE", f"Video vượt giới hạn {limit // (1024 * 1024)} MB")
                fh.write(chunk)
        if written < 16:
            raise _upload_error(400, "VIDEO_UNREADABLE", "File video rỗng hoặc bị cắt")
        with open(path, "rb") as fh:
            head = fh.read(12)
        if head[4:8] != b"ftyp":
            raise _upload_error(415, "UNSUPPORTED_VIDEO_TYPE", "Nội dung file không phải video MP4")
        try:
            meta = probe_uploaded_video(
                path,
                max_duration_s=float(settings.ai_upload_max_duration_s),
                max_width=int(settings.ai_upload_max_width),
                max_height=int(settings.ai_upload_max_height),
            )
        except UploadedVideoError as exc:
            raise _upload_error(400, exc.code, str(exc))
        source = UploadedVideoSource(
            cameraId,
            path,
            native_fps=meta["fps"],
            max_fps=float(settings.ai_upload_max_fps),
            max_wall_s=max_wall,
        )
        result = runtime_manager.start_session(
            camera_id=cameraId,
            mode="UPLOADED_VIDEO",
            demo_video_path=settings.ai_demo_video_path,
            farm_id=farmId,
            zone_id=zoneId,
            uploaded_source=source,
        )
        keep = True  # the source now owns the file and deletes it when done / stopped
        return result
    finally:
        if not keep:
            try:
                os.remove(path)
            except OSError:
                pass
