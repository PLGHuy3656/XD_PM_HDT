"""Internal runtime execution hook for local E2E manual validation (CP5.4).

Mounted with `include_in_schema=False` so public OpenAPI V1 contracts remain unchanged.
"""
from __future__ import annotations

from typing import Optional, Tuple

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.dependencies import get_runtime_manager
from app.runtime.manager import AIRuntimeManager

router = APIRouter(include_in_schema=False)


class RuntimeRunRequest(BaseModel):
    cameraId: str = Field(default="CAM-01", min_length=1)
    source: str = Field(..., min_length=1)
    sourceType: str = Field(default="auto")
    modelPath: Optional[str] = Field(default="models/best.pt")
    repeat: int = Field(default=1, ge=1, le=500)
    fps: float = Field(default=2.0, ge=0.0, le=120.0)
    maxFrames: int = Field(default=0, ge=0)
    farmId: Optional[str] = Field(default=None)
    zoneId: Optional[str] = Field(default=None)
    line: Tuple[Tuple[float, float], Tuple[float, float]] = Field(
        default=((0.10, 0.55), (0.90, 0.55))
    )
    insideSide: str = Field(default="positive")
    background: bool = Field(default=True)


@router.post("/internal/v1/runtime/run")
def run_camera_runtime(
    payload: RuntimeRunRequest,
    request: Request,
    runtime_manager: AIRuntimeManager = Depends(get_runtime_manager),
):
    if payload.background:
        runtime_manager.start_source_in_background(
            camera_id=payload.cameraId,
            source=payload.source,
            source_type=payload.sourceType,
            model_path=payload.modelPath,
            repeat=payload.repeat,
            fps=payload.fps,
            max_frames=payload.maxFrames,
            farm_id=payload.farmId,
            zone_id=payload.zoneId,
            line=payload.line,
            inside_side=payload.insideSide,
        )
        return {
            "started": True,
            "mode": "background",
            "cameraId": payload.cameraId,
            "source": payload.source,
            "modelPath": payload.modelPath,
            "repeat": payload.repeat,
            "fps": payload.fps,
        }

    status = runtime_manager.run_source(
        camera_id=payload.cameraId,
        source=payload.source,
        source_type=payload.sourceType,
        model_path=payload.modelPath,
        repeat=payload.repeat,
        fps=payload.fps,
        max_frames=payload.maxFrames,
        farm_id=payload.farmId,
        zone_id=payload.zoneId,
        line=payload.line,
        inside_side=payload.insideSide,
    )
    ws_manager = getattr(request.app.state, "ws_manager", None)
    if ws_manager is not None:
        ws_manager.flush_sync(timeout=2.0)
    return {
        "started": True,
        "mode": "sync",
        "cameraId": payload.cameraId,
        "status": status.model_dump(by_alias=True),
    }
