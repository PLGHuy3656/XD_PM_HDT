"""Canonical domain enums for Alert & Notification Service V1 (CP6.2)."""
from __future__ import annotations

from enum import Enum


class AlertStatus(str, Enum):
    """Lifecycle status of an operational Alert."""
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class AlertSeverity(str, Enum):
    """Canonical severity level of an Alert."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AlertSource(str, Enum):
    """Subsystem source generating the condition."""
    AI = "AI"
    IOT_ENVIRONMENT = "IOT_ENVIRONMENT"
    IOT_DEVICE = "IOT_DEVICE"


class AlertEventType(str, Enum):
    """Frozen set of condition types supported in V1."""
    PREDATOR_DETECTED = "PREDATOR_DETECTED"
    HIGH_TEMPERATURE = "HIGH_TEMPERATURE"
    LOW_TEMPERATURE = "LOW_TEMPERATURE"
    HIGH_HUMIDITY = "HIGH_HUMIDITY"
    LOW_HUMIDITY = "LOW_HUMIDITY"
    AUDIO_FAULT = "AUDIO_FAULT"
    DEVICE_OFFLINE = "DEVICE_OFFLINE"
    COMMAND_FAILED = "COMMAND_FAILED"


class NotificationChannel(str, Enum):
    """Delivery channel for notifications."""
    IN_APP = "IN_APP"
    FCM = "FCM"


class NotificationDeliveryStatus(str, Enum):
    """Delivery lifecycle status of a notification record.

    Note: Read state is strictly represented by `readAt: datetime | None`,
    NOT as a delivery status value.
    """
    PENDING = "PENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    SUPPRESSED = "SUPPRESSED"


class DevicePlatform(str, Enum):
    """Client platform registering a push notification token."""
    WEB = "WEB"
    ANDROID = "ANDROID"
    IOS = "IOS"


__all__ = [
    "AlertStatus",
    "AlertSeverity",
    "AlertSource",
    "AlertEventType",
    "NotificationChannel",
    "NotificationDeliveryStatus",
    "DevicePlatform",
]
