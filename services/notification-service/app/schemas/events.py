"""Transport-neutral input event DTOs for Alert & Notification Service V1 (CP6.2)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator
from pydantic.alias_generators import to_camel

from app.domain.enums import AlertEventType


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _serialize_utc(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    utc_dt = _ensure_utc(dt)
    return utc_dt.isoformat().replace("+00:00", "Z")


class EventInputModel(BaseModel):
    """Base transport-neutral input event model."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        validate_assignment=True,
    )


class AIAlertInputEvent(EventInputModel):
    """Adapts canonical AIEvent(eventType='PREDATOR_DETECTED') from AI Service."""

    event_id: str = Field(
        default_factory=lambda: f"evt_ai_{uuid.uuid4().hex[:10]}",
        description="Upstream AI event identifier",
    )
    event_type: AlertEventType = Field(
        default=AlertEventType.PREDATOR_DETECTED,
        description="Condition type",
    )
    camera_id: str = Field(..., description="Camera identifier")
    farm_id: str = Field(..., description="Farm identifier")
    zone_id: Optional[str] = Field(default=None, description="Optional zone identifier")
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Detection UTC timestamp",
    )
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Optional alias for detected_at",
    )
    predator_type: Optional[str] = Field(
        default=None,
        description="Detected predator class (e.g. rat, snake)",
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score",
    )
    bbox: Optional[Dict[str, float]] = Field(default=None, description="Bounding box pixel coordinates")
    snapshot_url: Optional[str] = Field(default=None, description="Snapshot evidence URL or path")

    @model_validator(mode="before")
    @classmethod
    def _sync_timestamps(cls, data: Any) -> Any:
        if isinstance(data, dict):
            ts = data.get("timestamp") or data.get("detected_at") or data.get("detectedAt")
            if ts:
                data.setdefault("detected_at", ts)
                data.setdefault("timestamp", ts)
        return data

    @property
    def snapshot(self) -> Optional[str]:
        return self.snapshot_url

    @property
    def predatorClass(self) -> Optional[str]:
        return self.predator_type

    @field_validator("detected_at", "timestamp", mode="before")
    @classmethod
    def _validate_dt(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if isinstance(v, datetime):
            return _ensure_utc(v)
        return v

    @field_serializer("detected_at")
    def _serialize_dt(self, dt: datetime) -> str:
        return _serialize_utc(dt) or ""


class IoTTelemetryAlertInputEvent(EventInputModel):
    """Adapts CanonicalTelemetry from IoT Service."""

    device_id: str = Field(..., description="IoT device code")
    farm_id: str = Field(..., description="Farm identifier")
    zone_id: Optional[str] = Field(default=None, description="Optional zone identifier")
    recorded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Telemetry sample UTC timestamp",
    )
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Optional alias for recorded_at",
    )
    temperature: Optional[float] = Field(default=None, description="Temperature in degrees Celsius")
    humidity: Optional[float] = Field(default=None, description="Relative humidity percentage")
    lux: Optional[float] = Field(default=None, description="Ambient light in lux")
    co2: Optional[float] = Field(default=None, description="CO2 concentration in ppm")
    audio_rms: Optional[float] = Field(default=None, description="Audio RMS metric")
    audio_healthy: Optional[bool] = Field(default=None, description="Audio sensor health indicator")

    @model_validator(mode="before")
    @classmethod
    def _sync_timestamps(cls, data: Any) -> Any:
        if isinstance(data, dict):
            ts = data.get("timestamp") or data.get("recorded_at") or data.get("recordedAt")
            if ts:
                data.setdefault("recorded_at", ts)
                data.setdefault("timestamp", ts)
        return data

    @field_validator("recorded_at", "timestamp", mode="before")
    @classmethod
    def _validate_dt(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if isinstance(v, datetime):
            return _ensure_utc(v)
        return v

    @field_serializer("recorded_at")
    def _serialize_dt(self, dt: datetime) -> str:
        return _serialize_utc(dt) or ""


class IoTPresenceAlertInputEvent(EventInputModel):
    """Adapts DevicePresence state from IoT Service."""

    device_id: str = Field(..., description="IoT device code")
    farm_id: str = Field(..., description="Farm identifier")
    zone_id: Optional[str] = Field(default=None, description="Optional zone identifier")
    status: str = Field(..., description="Presence status (ONLINE, OFFLINE)")
    status_reason: Optional[str] = Field(default=None, description="Status transition reason")
    last_seen: Optional[datetime] = Field(default=None, description="Last seen UTC timestamp")
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Event UTC timestamp",
    )
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Optional alias for updated_at",
    )

    @model_validator(mode="before")
    @classmethod
    def _sync_timestamps(cls, data: Any) -> Any:
        if isinstance(data, dict):
            ts = data.get("timestamp") or data.get("updated_at") or data.get("updatedAt")
            if ts:
                data.setdefault("updated_at", ts)
                data.setdefault("timestamp", ts)
        return data

    @field_validator("last_seen", "updated_at", "timestamp", mode="before")
    @classmethod
    def _validate_dt(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if isinstance(v, datetime):
            return _ensure_utc(v)
        return v

    @field_serializer("last_seen", "updated_at")
    def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        return _serialize_utc(dt)


class IoTCommandAlertInputEvent(EventInputModel):
    """Adapts DeviceCommand terminal state from IoT Service."""

    command_id: str = Field(..., description="Command correlation identifier")
    device_id: str = Field(..., description="Target IoT device code")
    farm_id: str = Field(..., description="Farm identifier")
    zone_id: Optional[str] = Field(default=None, description="Optional zone identifier")
    command_type: str = Field(..., description="Command type (e.g. SET_RELAY, UPDATE_THRESHOLDS)")
    status: str = Field(..., description="Command status")
    failure_reason: Optional[str] = Field(default=None, description="Failure reason")
    ack_message: Optional[str] = Field(default=None, description="ACK status/error message")
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Command update UTC timestamp",
    )
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Optional alias for updated_at",
    )

    @model_validator(mode="before")
    @classmethod
    def _sync_timestamps(cls, data: Any) -> Any:
        if isinstance(data, dict):
            ts = data.get("timestamp") or data.get("updated_at") or data.get("updatedAt")
            if ts:
                data.setdefault("updated_at", ts)
                data.setdefault("timestamp", ts)
        return data

    @field_validator("updated_at", "timestamp", mode="before")
    @classmethod
    def _validate_dt(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if isinstance(v, datetime):
            return _ensure_utc(v)
        return v

    @field_serializer("updated_at")
    def _serialize_dt(self, dt: datetime) -> str:
        return _serialize_utc(dt) or ""


__all__ = [
    "AIAlertInputEvent",
    "IoTTelemetryAlertInputEvent",
    "IoTPresenceAlertInputEvent",
    "IoTCommandAlertInputEvent",
    "EventInputModel",
]
