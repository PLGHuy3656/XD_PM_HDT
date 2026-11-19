"""Canonical domain event envelope validation and error classifications (CP7.4)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PermanentEnvelopeError(Exception):
    """Permanent message failure; message should NOT be requeued (routes to DLQ)."""


class UnsupportedVersionError(PermanentEnvelopeError):
    """Unsupported eventVersion; contract V1 supports only '1.0'."""


class ProducerMismatchError(PermanentEnvelopeError):
    """Producer and eventType combination is not authorized or is contradictory."""


VALID_PRODUCER_EVENT_MAPPINGS: Dict[str, Set[str]] = {
    "iot-service": {
        "iot.environment.high_temperature.started",
        "iot.environment.high_temperature.recovered",
        "iot.environment.low_temperature.started",
        "iot.environment.low_temperature.recovered",
        "iot.environment.high_humidity.started",
        "iot.environment.high_humidity.recovered",
        "iot.environment.low_humidity.started",
        "iot.environment.low_humidity.recovered",
        "iot.audio.fault.started",
        "iot.audio.fault.recovered",
        "iot.device.offline",
        "iot.device.online",
        "iot.command.failed",
    },
    "ai-service": {
        "ai.predator.detected",
    },
}


class CanonicalEnvelope(BaseModel):
    """Canonical V1 Domain Event Envelope parser & strict validator."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
    )

    event_id: str = Field(..., alias="eventId", min_length=1)
    event_type: str = Field(..., alias="eventType", min_length=1)
    event_version: str = Field(..., alias="eventVersion")
    occurred_at: str = Field(..., alias="occurredAt")
    producer: str = Field(..., alias="producer", min_length=1)
    correlation_id: Optional[str] = Field(default=None, alias="correlationId")
    payload: Dict[str, Any] = Field(..., alias="payload")

    @field_validator("event_id")
    @classmethod
    def _validate_event_id(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("eventId must not be empty")
        # Validate that event_id is a valid UUID string
        try:
            uuid.UUID(s)
        except ValueError as exc:
            raise ValueError(f"eventId '{s}' is not a valid UUID") from exc
        return s

    @field_validator("event_version")
    @classmethod
    def _validate_version(cls, v: str) -> str:
        if v.strip() != "1.0":
            raise UnsupportedVersionError(f"Unsupported eventVersion '{v}'. V1 supports only '1.0'.")
        return v.strip()

    @field_validator("occurred_at")
    @classmethod
    def _validate_occurred_at(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("occurredAt must not be empty")
        try:
            datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"Invalid occurredAt ISO-8601 timestamp: '{s}'") from exc
        return s

    @model_validator(mode="after")
    def _validate_producer_and_event(self) -> "CanonicalEnvelope":
        allowed_events = VALID_PRODUCER_EVENT_MAPPINGS.get(self.producer)
        if allowed_events is None:
            raise ProducerMismatchError(f"Unknown or unauthorized producer '{self.producer}'.")
        if self.event_type not in allowed_events:
            raise ProducerMismatchError(
                f"Producer '{self.producer}' is not authorized to emit eventType '{self.event_type}'."
            )
        return self

    @classmethod
    def parse_raw_json(cls, raw_bytes: bytes) -> "CanonicalEnvelope":
        """Parses raw message bytes with permanent error classification on JSON decode errors."""
        try:
            data = json.loads(raw_bytes.decode("utf-8"))
        except Exception as exc:
            raise PermanentEnvelopeError(f"Malformed JSON body: {exc}") from exc

        if not isinstance(data, dict):
            raise PermanentEnvelopeError("Message body must be a JSON object")

        try:
            return cls.model_validate(data)
        except (UnsupportedVersionError, ProducerMismatchError):
            raise
        except Exception as exc:
            raise PermanentEnvelopeError(f"Invalid canonical envelope structure: {exc}") from exc


__all__ = [
    "CanonicalEnvelope",
    "PermanentEnvelopeError",
    "ProducerMismatchError",
    "UnsupportedVersionError",
    "VALID_PRODUCER_EVENT_MAPPINGS",
]
