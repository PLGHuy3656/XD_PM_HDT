"""Payload schemas for AI domain events published to RabbitMQ (CP7.3)."""
from __future__ import annotations

import math
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BBoxPayload(BaseModel):
    """Canonical pixel bounding box {x, y, width, height}."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
    )

    x: float
    y: float
    width: float
    height: float

    @field_validator("x", "y", "width", "height")
    @classmethod
    def _validate_coords(cls, v: float) -> float:
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
            raise ValueError("Bounding box coordinates must be finite numbers")
        val = round(float(v), 1)
        if val < 0.0:
            raise ValueError("Bounding box coordinates must be non-negative")
        return val


class PredatorDetectedPayload(BaseModel):
    """Payload for `ai.predator.detected` canonical domain event."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
    )

    farm_id: str = Field(..., alias="farmId", min_length=1)
    zone_id: str = Field(..., alias="zoneId", min_length=1)
    camera_id: str = Field(..., alias="cameraId", min_length=1)
    predator_class: Literal["rat", "snake"] = Field(..., alias="predatorClass")
    confidence: float = Field(..., ge=0.0, le=1.0)
    snapshot_ref: Optional[str] = Field(default=None, alias="snapshotRef")
    frame_width: int = Field(..., alias="frameWidth", gt=0)
    frame_height: int = Field(..., alias="frameHeight", gt=0)
    bbox: BBoxPayload = Field(...)

    @field_validator("farm_id", "zone_id", "camera_id")
    @classmethod
    def _validate_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Identifier must not be empty")
        return s

    @field_validator("confidence")
    @classmethod
    def _round_confidence(cls, v: float) -> float:
        if isinstance(v, bool) or not math.isfinite(float(v)):
            raise ValueError("confidence must be a finite float")
        return round(float(v), 4)

    def to_dict(self) -> dict:
        return self.model_dump(by_alias=True, mode="json")


__all__ = [
    "BBoxPayload",
    "PredatorDetectedPayload",
]
