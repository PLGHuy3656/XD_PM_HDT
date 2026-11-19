"""Canonical domain event constants for AI Service (CP7.3)."""
from __future__ import annotations

EVENT_AI_PREDATOR_DETECTED = "ai.predator.detected"
PRODUCER_AI_SERVICE = "ai-service"
CANONICAL_EVENT_VERSION = "1.0"
CANONICAL_EXCHANGE = "swiftlet.domain.events"

SUPPORTED_PREDATOR_CLASSES = ("rat", "snake")

__all__ = [
    "CANONICAL_EVENT_VERSION",
    "CANONICAL_EXCHANGE",
    "EVENT_AI_PREDATOR_DETECTED",
    "PRODUCER_AI_SERVICE",
    "SUPPORTED_PREDATOR_CLASSES",
]
