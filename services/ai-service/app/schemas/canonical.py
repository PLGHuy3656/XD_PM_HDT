"""Canonical AI Contract V1 domain models (CP5.2).

Strict rules enforced by these models:
1. Single ISO-8601 UTC timestamp per domain object (`capturedAt`, `recordedAt`,
   `detectedAt`, `updatedAt` / `lastFrameAt`). No duplicate Unix epoch `timestamp`.
2. Pixel-coordinate `BoundingBox` (`x1`, `y1`, `x2`, `y2`) + `FrameInfo` (`width`, `height`).
   No `bboxNormalized` or CSS percentages.
3. `CountUpdate.netChange` strictly equals `entryCount - exitCount` (movement balance
   within the current counting window). No `occupancy`, `currentBirdCount`, or
   `totalBirdPopulation` fields exist.
4. `AIEvent` V1 supports only `PREDATOR_DETECTED` (`rat` | `snake`). No `FLOCK_ANOMALY`,
   `AUDIO`, or per-bird `ENTRY`/`EXIT` event records.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, List, Literal, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CameraLifecycleState = Literal["STARTING", "ONLINE", "DEGRADED", "OFFLINE", "ERROR"]
InferenceLifecycleState = Literal["IDLE", "STARTING", "RUNNING", "DEGRADED", "STOPPED", "ERROR"]
PredatorClass = Literal["rat", "snake"]
AIEventTypeV1 = Literal["PREDATOR_DETECTED"]


def epoch_to_iso8601_utc(epoch_seconds: Optional[float] = None) -> str:
    """Convert Unix epoch seconds (or current UTC time) into canonical ISO-8601 UTC string."""
    if epoch_seconds is None:
        dt = datetime.now(timezone.utc)
    else:
        if not math.isfinite(epoch_seconds):
            raise ValueError("epoch_seconds must be finite")
        dt = datetime.fromtimestamp(float(epoch_seconds), tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def validate_iso8601_utc(value: str, field_name: str = "timestamp") -> str:
    """Validate that a string is a valid timezone-aware ISO-8601 timestamp and normalize to UTC Z."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty ISO-8601 UTC string")
    raw = value.strip()
    candidate = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        dt = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid ISO-8601 timestamp: {value!r}") from exc
    if dt.tzinfo is None:
        raise ValueError(f"{field_name} must include UTC timezone offset or 'Z': {value!r}")
    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class CanonicalModel(BaseModel):
    """Base model enforcing strict V1 contract rules and alias-aware serialization."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        validate_assignment=True,
    )

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("by_alias", True)
        return super().model_dump(*args, **kwargs)

    def model_dump_json(self, *args: Any, **kwargs: Any) -> str:
        kwargs.setdefault("by_alias", True)
        return super().model_dump_json(*args, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


class BoundingBox(CanonicalModel):
    """Canonical pixel bounding box `{x1, y1, x2, y2}` in source frame coordinates."""

    x1: float
    y1: float
    x2: float
    y2: float

    @field_validator("x1", "y1", "x2", "y2")
    @classmethod
    def _validate_finite_non_negative(cls, v: float) -> float:
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
            raise ValueError("BoundingBox coordinates must be finite numbers")
        val = round(float(v), 1)
        if val < 0.0:
            raise ValueError("BoundingBox coordinates must be >= 0.0")
        return val

    @model_validator(mode="after")
    def _validate_ordering(self) -> "BoundingBox":
        if self.x2 < self.x1:
            raise ValueError(f"BoundingBox x2 ({self.x2}) must be >= x1 ({self.x1})")
        if self.y2 < self.y1:
            raise ValueError(f"BoundingBox y2 ({self.y2}) must be >= y1 ({self.y1})")
        return self

    @classmethod
    def from_xyxy(cls, coords: Sequence[float]) -> "BoundingBox":
        if len(coords) != 4:
            raise ValueError(f"Expected 4 bbox coordinates [x1, y1, x2, y2], got {len(coords)}")
        return cls(
            x1=max(0.0, float(coords[0])),
            y1=max(0.0, float(coords[1])),
            x2=max(0.0, float(coords[2])),
            y2=max(0.0, float(coords[3])),
        )


class FrameInfo(CanonicalModel):
    """Source frame dimensions in pixels."""

    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)


class Detection(CanonicalModel):
    """Single object detection within a frame."""

    cls: str = Field(..., alias="class", min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    bbox: BoundingBox
    trackId: Optional[int] = Field(default=None, ge=0)

    @field_validator("cls")
    @classmethod
    def _strip_cls(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("class must not be empty")
        return s

    @field_validator("confidence")
    @classmethod
    def _round_confidence(cls, v: float) -> float:
        if isinstance(v, bool) or not math.isfinite(float(v)):
            raise ValueError("confidence must be a finite float in [0.0, 1.0]")
        return round(float(v), 4)


class DetectionResult(CanonicalModel):
    """Canonical V1 per-frame detection result."""

    cameraId: str = Field(..., min_length=1)
    farmId: Optional[str] = None
    zoneId: Optional[str] = None
    frameId: int = Field(..., ge=0)
    capturedAt: str
    frame: FrameInfo
    detections: List[Detection] = Field(default_factory=list)

    @field_validator("cameraId")
    @classmethod
    def _validate_camera_id(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("cameraId must not be empty")
        return s

    @field_validator("capturedAt")
    @classmethod
    def _validate_captured_at(cls, v: str) -> str:
        return validate_iso8601_utc(v, "capturedAt")


class CountUpdate(CanonicalModel):
    """Canonical V1 line-crossing count update.

    `netChange` strictly equals `entryCount - exitCount` and represents
    movement balance within the current counting window started at `windowStartedAt`.
    It is NOT absolute bird population or occupancy.
    """

    cameraId: str = Field(..., min_length=1)
    farmId: Optional[str] = None
    zoneId: Optional[str] = None
    frameId: int = Field(..., ge=0)
    recordedAt: str
    windowStartedAt: str
    entryCount: int = Field(..., ge=0)
    exitCount: int = Field(..., ge=0)
    netChange: int
    deltaEntry: int = Field(..., ge=0)
    deltaExit: int = Field(..., ge=0)

    @field_validator("cameraId")
    @classmethod
    def _validate_camera_id(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("cameraId must not be empty")
        return s

    @field_validator("recordedAt")
    @classmethod
    def _validate_recorded_at(cls, v: str) -> str:
        return validate_iso8601_utc(v, "recordedAt")

    @field_validator("windowStartedAt")
    @classmethod
    def _validate_window_started_at(cls, v: str) -> str:
        return validate_iso8601_utc(v, "windowStartedAt")

    @model_validator(mode="after")
    def _validate_net_change(self) -> "CountUpdate":
        expected = self.entryCount - self.exitCount
        if self.netChange != expected:
            raise ValueError(
                f"netChange ({self.netChange}) must equal entryCount ({self.entryCount}) "
                f"- exitCount ({self.exitCount}) = {expected}"
            )
        return self


class AIEvent(CanonicalModel):
    """Canonical V1 immediate AI-originated event (`PREDATOR_DETECTED`)."""

    eventId: str = Field(..., min_length=1)
    eventType: AIEventTypeV1 = "PREDATOR_DETECTED"
    cameraId: str = Field(..., min_length=1)
    farmId: Optional[str] = None
    zoneId: Optional[str] = None
    frameId: int = Field(..., ge=0)
    detectedAt: str
    cls: PredatorClass = Field(..., alias="class")
    confidence: float = Field(..., ge=0.0, le=1.0)
    bbox: BoundingBox
    snapshot: Optional[str] = None

    @field_validator("eventId", "cameraId")
    @classmethod
    def _validate_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Identifier must not be empty")
        return s

    @field_validator("detectedAt")
    @classmethod
    def _validate_detected_at(cls, v: str) -> str:
        return validate_iso8601_utc(v, "detectedAt")

    @field_validator("confidence")
    @classmethod
    def _round_confidence(cls, v: float) -> float:
        if isinstance(v, bool) or not math.isfinite(float(v)):
            raise ValueError("confidence must be a finite float in [0.0, 1.0]")
        return round(float(v), 4)


class CameraRuntimeStatus(CanonicalModel):
    """Canonical V1 technical runtime status for an AI camera pipeline."""

    cameraId: str = Field(..., min_length=1)
    farmId: Optional[str] = None
    zoneId: Optional[str] = None
    status: CameraLifecycleState
    sourceConnected: bool
    inferenceStatus: InferenceLifecycleState
    fps: float = Field(..., ge=0.0)
    width: Optional[int] = Field(default=None, gt=0)
    height: Optional[int] = Field(default=None, gt=0)
    modelVersion: str = Field(..., min_length=1)
    trackerType: str = Field(..., min_length=1)
    processedFrames: int = Field(..., ge=0)
    lastFrameAt: Optional[str] = None
    updatedAt: str
    errorCode: Optional[str] = None
    errorMessage: Optional[str] = None

    @field_validator("cameraId", "modelVersion", "trackerType")
    @classmethod
    def _validate_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field must not be empty")
        return s

    @field_validator("fps")
    @classmethod
    def _round_fps(cls, v: float) -> float:
        if isinstance(v, bool) or not math.isfinite(float(v)) or float(v) < 0.0:
            raise ValueError("fps must be a finite float >= 0.0")
        return round(float(v), 2)

    @field_validator("lastFrameAt")
    @classmethod
    def _validate_last_frame_at(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return validate_iso8601_utc(v, "lastFrameAt")

    @field_validator("updatedAt")
    @classmethod
    def _validate_updated_at(cls, v: str) -> str:
        return validate_iso8601_utc(v, "updatedAt")


__all__ = [
    "AIEvent",
    "AIEventTypeV1",
    "BoundingBox",
    "CameraLifecycleState",
    "CameraRuntimeStatus",
    "CanonicalModel",
    "CountUpdate",
    "Detection",
    "DetectionResult",
    "FrameInfo",
    "InferenceLifecycleState",
    "PredatorClass",
    "epoch_to_iso8601_utc",
    "validate_iso8601_utc",
]
