"""Canonical Domain Event Envelope V1 for SwiftletCare IoT Service (CP7.2).

Frozen CP7 canonical envelope structure:
- eventId: UUID string
- eventType: Canonical routing key (e.g. iot.environment.high_temperature.started)
- eventVersion: Constant "1.0"
- occurredAt: ISO-8601 UTC timestamp
- producer: Constant "iot-service"
- correlationId: UUID string or null
- payload: Dict containing business context (farmId, zoneId, deviceId) + metric/event details
"""

from datetime import datetime
from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, Field


class DomainEventPayload(BaseModel):
    """Business payload for IoT domain events."""
    model_config = ConfigDict(extra="allow")

    farmId: str = Field(..., description="Farm identifier code or UUID")
    zoneId: str = Field(..., description="Zone identifier code or UUID")
    deviceId: str = Field(..., description="Device identity code")
    metric: str | None = Field(default=None, description="Metric name: temperature, humidity, audio, etc.")
    value: float | int | str | None = Field(default=None, description="Current measured value")
    threshold: float | int | None = Field(default=None, description="Triggered threshold value")
    unit: str | None = Field(default=None, description="Measurement unit: C, %, ppm, lux, etc.")
    status: str | None = Field(default=None, description="Status string: ONLINE, OFFLINE, etc.")
    reason: str | None = Field(default=None, description="Reason or diagnostic explanation")


class CanonicalDomainEvent(BaseModel):
    """Canonical V1 Domain Event Envelope published to swiftlet.domain.events."""
    model_config = ConfigDict(extra="forbid")

    eventId: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique UUIDv4 string identifying this event",
    )
    eventType: str = Field(..., description="Canonical routing key string")
    eventVersion: str = Field(default="1.0", description="Schema version: constant '1.0'")
    occurredAt: str = Field(..., description="ISO-8601 UTC timestamp string")
    producer: str = Field(default="iot-service", description="Originating service: 'iot-service'")
    correlationId: str | None = Field(default=None, description="Command or trace correlation UUID")
    payload: dict[str, Any] = Field(..., description="Structured domain payload dictionary")
