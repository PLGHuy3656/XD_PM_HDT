"""Canonical domain models for Alert & Notification Service V1 (CP6.2)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator
from pydantic.alias_generators import to_camel

from app.domain.enums import (
    AlertEventType,
    AlertSeverity,
    AlertSource,
    AlertStatus,
    DevicePlatform,
    NotificationChannel,
    NotificationDeliveryStatus,
)


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


class CanonicalModel(BaseModel):
    """Base Pydantic model forbidding unexpected fields and ensuring UTC ISO-8601 formatting."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        validate_assignment=True,
    )


class Alert(CanonicalModel):
    """Persistent, actionable operational condition scoped to farm/zone/device/camera."""

    alert_id: str = Field(..., description="Unique alert identifier (e.g. alt_9f42c1a8b301)")
    event_type: AlertEventType = Field(..., description="Frozen V1 condition type")
    source: AlertSource = Field(..., description="Subsystem category (AI, IOT_ENVIRONMENT, IOT_DEVICE)")
    severity: AlertSeverity = Field(..., description="Canonical severity tier")
    status: AlertStatus = Field(default=AlertStatus.OPEN, description="Lifecycle status")

    farm_id: str = Field(..., description="Target farm identifier")
    zone_id: Optional[str] = Field(default=None, description="Optional zone identifier")

    device_id: Optional[str] = Field(default=None, description="IoT node identifier if IoT source")
    camera_id: Optional[str] = Field(default=None, description="Camera identifier if AI source")

    title: str = Field(..., description="Concise human-readable title")
    message: str = Field(..., description="Detailed operational description")

    snapshot_url: Optional[str] = Field(default=None, description="Snapshot URL for AI predator alert")
    telemetry_snapshot: Optional[Dict[str, Any]] = Field(default=None, description="Telemetry snapshot for IoT alert")

    occurrence_count: int = Field(default=1, ge=1, description="Merged deduplicated occurrence count")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation UTC timestamp")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Latest update UTC timestamp")
    last_occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Latest occurrence UTC timestamp")

    acknowledged_at: Optional[datetime] = Field(default=None, description="UTC timestamp when acknowledged")
    acknowledged_by: Optional[str] = Field(default=None, description="User ID who acknowledged")

    resolved_at: Optional[datetime] = Field(default=None, description="UTC timestamp when resolved")
    resolved_by: Optional[str] = Field(default=None, description="User ID or 'SYSTEM' when resolved")
    resolution_note: Optional[str] = Field(default=None, description="Note on how alert was resolved")

    source_event_id: Optional[str] = Field(default=None, description="Upstream correlation ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Structured contextual metadata")

    @field_validator("created_at", "updated_at", "last_occurred_at", "acknowledged_at", "resolved_at", mode="before")
    @classmethod
    def _validate_datetimes(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if isinstance(v, datetime):
            return _ensure_utc(v)
        return v

    @field_serializer("created_at", "updated_at", "last_occurred_at", "acknowledged_at", "resolved_at")
    def _serialize_datetimes(self, dt: Optional[datetime]) -> Optional[str]:
        return _serialize_utc(dt)


class Notification(CanonicalModel):
    """Delivery record informing an individual user about an Alert via a specific channel."""

    notification_id: str = Field(..., description="Unique notification identifier (e.g. ntf_3b810d4ac912)")
    alert_id: str = Field(..., description="Associated Alert identifier")
    user_id: str = Field(..., description="Recipient user identifier")
    channel: NotificationChannel = Field(..., description="Delivery channel (IN_APP or FCM)")
    delivery_status: NotificationDeliveryStatus = Field(
        default=NotificationDeliveryStatus.PENDING,
        description="Delivery status (PENDING, SENT, DELIVERED, FAILED, SUPPRESSED)",
    )
    title: str = Field(..., description="Notification title")
    body: str = Field(..., description="Notification body")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation UTC timestamp")
    sent_at: Optional[datetime] = Field(default=None, description="Dispatch UTC timestamp")
    read_at: Optional[datetime] = Field(default=None, description="Read UTC timestamp")
    failure_reason: Optional[str] = Field(default=None, description="Error reason if delivery failed")
    data: Dict[str, str] = Field(default_factory=dict, description="Custom payload data")

    @property
    def is_read(self) -> bool:
        """Derived read state strictly determined by presence of read_at timestamp."""
        return self.read_at is not None

    @property
    def isRead(self) -> bool:
        return self.read_at is not None

    @field_validator("created_at", "sent_at", "read_at", mode="before")
    @classmethod
    def _validate_datetimes(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if isinstance(v, datetime):
            return _ensure_utc(v)
        return v

    @field_serializer("created_at", "sent_at", "read_at")
    def _serialize_datetimes(self, dt: Optional[datetime]) -> Optional[str]:
        return _serialize_utc(dt)


class UserDevice(CanonicalModel):
    """Registered push token for a user device (multi-device support)."""

    device_id: str = Field(..., description="Unique registration identifier (e.g. dev_7c14e802a110)")
    user_id: str = Field(..., description="Owner user identifier")
    fcm_token: str = Field(..., description="Globally unique push token string")
    platform: DevicePlatform = Field(..., description="Platform (WEB, ANDROID, IOS)")
    device_name: Optional[str] = Field(default=None, description="Optional user-facing device name")
    is_enabled: bool = Field(default=True, description="Whether push notification delivery is enabled")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Initial registration UTC timestamp")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last token/attribute update UTC timestamp")

    @property
    def enabled(self) -> bool:
        return self.is_enabled

    @enabled.setter
    def enabled(self, val: bool) -> None:
        self.is_enabled = val

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def _validate_datetimes(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if isinstance(v, datetime):
            return _ensure_utc(v)
        return v

    @field_serializer("created_at", "updated_at")
    def _serialize_datetimes(self, dt: Optional[datetime]) -> Optional[str]:
        return _serialize_utc(dt)


__all__ = [
    "Alert",
    "Notification",
    "UserDevice",
    "CanonicalModel",
]
