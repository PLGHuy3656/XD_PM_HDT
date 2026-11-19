"""Durable consumer inbox for exactly-once application of domain events (CP8.5).

The inbox marker (notification_db.processed_events) is written in the SAME PostgreSQL
transaction as every repository change the event causes (see app.database.transaction_scope):
- marker present  <=> the event's database effects are committed;
- a crash or error before COMMIT rolls back both, so a redelivery processes the event again;
- a redelivery after COMMIT finds the marker and is discarded, even if the Redis DONE key
  was never written or Redis lost its data.

Redis (RedisIdempotencyStore) remains the fast-path lease that prevents concurrent work;
PostgreSQL is the source of truth for "processed".

External side effects issued during processing (FCM push, WebSocket broadcast) are not
transactional: they happen before COMMIT, so a rollback followed by redelivery can repeat
them (at-least-once), but they are never skipped for an event that is marked processed.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable, Optional

from app.database import transaction_scope

logger = logging.getLogger("notification_service.infrastructure.rabbitmq.inbox")


class InboxResult(str, Enum):
    PROCESSED = "PROCESSED"
    ALREADY_PROCESSED = "ALREADY_PROCESSED"


class EventInbox(ABC):
    @abstractmethod
    def process_once(self, event_id: str, event_type: str, producer: str, handler: Callable[[], None]) -> InboxResult:
        """Runs handler at most once per committed event_id."""
        raise NotImplementedError


class NullEventInbox(EventInbox):
    """No durable inbox (in-memory repositories / unit tests): always runs the handler."""

    def process_once(self, event_id: str, event_type: str, producer: str, handler: Callable[[], None]) -> InboxResult:
        handler()
        return InboxResult.PROCESSED


class PostgresEventInbox(EventInbox):
    """PostgreSQL inbox backed by notification_db.processed_events (migration 002)."""

    _INSERT_MARKER = (
        "INSERT INTO processed_events (event_id, event_type, producer) VALUES (%s, %s, %s) "
        "ON CONFLICT (event_id) DO NOTHING RETURNING event_id"
    )

    def __init__(self, database_url: Optional[str] = None, lock_timeout_ms: int = 5000) -> None:
        self._database_url = database_url
        self._lock_timeout_ms = lock_timeout_ms

    def process_once(self, event_id: str, event_type: str, producer: str, handler: Callable[[], None]) -> InboxResult:
        with transaction_scope(self._database_url, lock_timeout_ms=self._lock_timeout_ms) as scope:
            # A concurrent uncommitted marker for the same event blocks here until that
            # transaction ends (bounded by lock_timeout), serialising duplicate deliveries.
            row = scope.connection.execute(self._INSERT_MARKER, (event_id, event_type, producer)).fetchone()
            if row is None:
                logger.info("[INBOX] eventId='%s' already committed as processed; skipping side effects.", event_id)
                return InboxResult.ALREADY_PROCESSED
            handler()
            return InboxResult.PROCESSED

    def is_processed(self, event_id: str) -> bool:
        from app.database import get_connection

        with get_connection(self._database_url) as conn:
            return conn.execute("SELECT 1 FROM processed_events WHERE event_id = %s", (event_id,)).fetchone() is not None


__all__ = ["EventInbox", "InboxResult", "NullEventInbox", "PostgresEventInbox"]
