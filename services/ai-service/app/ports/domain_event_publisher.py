"""Domain event publisher port and reference implementations for AI Service."""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List

from app.domain_events.envelope import DomainEvent

logger = logging.getLogger("ai_service.ports.publisher")


class DomainEventPublisher(ABC):
    """Transport-neutral domain event publisher port."""

    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """Asynchronously publishes a canonical DomainEvent to the message exchange."""
        raise NotImplementedError

    def publish_nowait(self, event: DomainEvent) -> None:
        """Synchronous bridge for pipeline callbacks and synchronous callers.

        Schedules the async publish coroutine on the running event loop.
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.publish(event))
        except RuntimeError:
            try:
                asyncio.run(self.publish(event))
            except Exception as exc:
                logger.warning(
                    "[PUBLISHER NOWAIT] Could not run event publish synchronously for '%s': %s",
                    event.event_type,
                    exc,
                )


class NoOpDomainEventPublisher(DomainEventPublisher):
    """No-op publisher for unit testing and RabbitMQ-disabled operation."""

    async def publish(self, event: DomainEvent) -> None:
        logger.debug("[NOOP PUBLISHER] Discarded event '%s' (RabbitMQ disabled)", event.event_type)

    def publish_nowait(self, event: DomainEvent) -> None:
        logger.debug("[NOOP PUBLISHER NOWAIT] Discarded event '%s' (RabbitMQ disabled)", event.event_type)


class InMemoryDomainEventPublisher(DomainEventPublisher):
    """In-memory event publisher that records published events for deterministic testing."""

    def __init__(self) -> None:
        self.published_events: List[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        self.published_events.append(event)
        logger.debug(
            "[IN-MEMORY PUBLISHER] Recorded event '%s' (total=%d)",
            event.event_type,
            len(self.published_events),
        )

    def clear(self) -> None:
        self.published_events.clear()


noop_domain_event_publisher = NoOpDomainEventPublisher()

__all__ = [
    "DomainEventPublisher",
    "InMemoryDomainEventPublisher",
    "NoOpDomainEventPublisher",
    "noop_domain_event_publisher",
]
