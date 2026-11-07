"""Canonical Domain Events package for AI Service."""
from app.domain_events.constants import (
    CANONICAL_EVENT_VERSION,
    CANONICAL_EXCHANGE,
    EVENT_AI_PREDATOR_DETECTED,
    PRODUCER_AI_SERVICE,
    SUPPORTED_PREDATOR_CLASSES,
)
from app.domain_events.envelope import DomainEvent
from app.domain_events.models import BBoxPayload, PredatorDetectedPayload

__all__ = [
    "BBoxPayload",
    "CANONICAL_EVENT_VERSION",
    "CANONICAL_EXCHANGE",
    "DomainEvent",
    "EVENT_AI_PREDATOR_DETECTED",
    "PRODUCER_AI_SERVICE",
    "PredatorDetectedPayload",
    "SUPPORTED_PREDATOR_CLASSES",
]
