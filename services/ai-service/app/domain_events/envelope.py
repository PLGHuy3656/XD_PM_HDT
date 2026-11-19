"""Canonical CP7 domain event envelope model for AI Service."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.domain_events.constants import CANONICAL_EVENT_VERSION, PRODUCER_AI_SERVICE


def default_event_id() -> str:
    """Generates standard UUIDv4 event identifier."""
    return str(uuid.uuid4())


def default_occurred_at() -> str:
    """Generates UTC ISO-8601 timestamp with trailing Z."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class DomainEvent(BaseModel):
    """Canonical V1 Domain Event Envelope.

    Guarantees strict CP7 envelope structure:
    eventId, eventType, eventVersion, occurredAt, producer, correlationId, payload.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
    )

    event_id: str = Field(default_factory=default_event_id, alias="eventId")
    event_type: str = Field(..., alias="eventType")
    event_version: str = Field(default=CANONICAL_EVENT_VERSION, alias="eventVersion")
    occurred_at: str = Field(default_factory=default_occurred_at, alias="occurredAt")
    producer: str = Field(default=PRODUCER_AI_SERVICE, alias="producer")
    correlation_id: Optional[str] = Field(default=None, alias="correlationId")
    payload: dict[str, Any] = Field(default_factory=dict, alias="payload")

    def to_dict(self) -> dict[str, Any]:
        """Serializes envelope to canonical JSON-compatible dictionary with camelCase keys."""
        return self.model_dump(by_alias=True, mode="json")


__all__ = [
    "DomainEvent",
    "default_event_id",
    "default_occurred_at",
]
