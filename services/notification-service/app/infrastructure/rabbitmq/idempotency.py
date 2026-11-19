"""Message idempotency ports and implementations (CP7.4 / CP7.5).

Provides:
- IdempotencyStore: Abstract Port for message idempotency and atomic lease claims.
- InMemoryIdempotencyStore: Reference in-memory store for unit tests.
- RedisIdempotencyStore: Production-grade Redis store with atomic SET NX EX claims,
  PROCESSING -> DONE lifecycle, and durable crash-resilient protection across restarts.
"""
from __future__ import annotations

import collections
import inspect
import logging
import threading
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Deque, Dict, Optional, Set

logger = logging.getLogger("notification_service.infrastructure.rabbitmq.idempotency")


class ClaimStatus(str, Enum):
    """Outcome of an idempotency claim attempt (CP8.5 consumer refactor).

    CLAIMED      -> this delivery owns the PROCESSING lease and must process the event.
    DONE         -> the event was fully processed earlier; safe to ACK as duplicate.
    IN_PROGRESS  -> another (possibly crashed) delivery holds the lease; the event is NOT
                    confirmed processed and must not be ACKed as a duplicate.
    """

    CLAIMED = "CLAIMED"
    DONE = "DONE"
    IN_PROGRESS = "IN_PROGRESS"


class IdempotencyStore(ABC):
    """Abstract port for message idempotency detection to prevent duplicate delivery side effects."""

    @abstractmethod
    def has_processed(self, event_id: str) -> bool:
        """Returns True if the eventId has already been claimed or processed."""
        raise NotImplementedError

    @abstractmethod
    def mark_processed(self, event_id: str, ttl_seconds: Optional[int] = None) -> None:
        """Records the eventId as DONE."""
        raise NotImplementedError

    @abstractmethod
    def try_claim(self, event_id: str, claim_ttl: Optional[int] = None) -> bool:
        """Atomically attempts to acquire a PROCESSING lease on event_id.

        Returns True if acquired exclusively (new event), False if already claimed or DONE.
        """
        raise NotImplementedError

    def claim(self, event_id: str, claim_ttl: Optional[int] = None) -> ClaimStatus:
        """Atomically claims event_id and reports why a claim was refused.

        Default implementation for stores that cannot distinguish states: a refused
        claim is reported as IN_PROGRESS (never as DONE), so the caller defers
        instead of discarding an event that may not have been processed.
        """
        return ClaimStatus.CLAIMED if self.try_claim(event_id, claim_ttl) else ClaimStatus.IN_PROGRESS

    @abstractmethod
    def mark_done(self, event_id: str, ttl_seconds: Optional[int] = None) -> None:
        """Transitions state from PROCESSING to DONE with long-term retention TTL."""
        raise NotImplementedError

    @abstractmethod
    def release_claim(self, event_id: str) -> None:
        """Releases a temporary PROCESSING lease upon failure so retries can re-claim."""
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        """Clears all idempotency entries (for testing)."""
        raise NotImplementedError


class InMemoryIdempotencyStore(IdempotencyStore):
    """Thread-safe, bounded in-memory idempotency store for unit tests.

    Supports atomic lease claims and transitions (PROCESSING -> DONE).
    """

    def __init__(self, capacity: int = 10000, default_ttl: int = 86400) -> None:
        self._capacity = max(100, int(capacity))
        self._default_ttl = default_ttl
        self._states: Dict[str, str] = {}  # event_id -> "PROCESSING" | "DONE"
        self._queue: Deque[str] = collections.deque()
        self._lock = threading.Lock()

    def has_processed(self, event_id: str) -> bool:
        with self._lock:
            return event_id in self._states

    def mark_processed(self, event_id: str, ttl_seconds: Optional[int] = None) -> None:
        self.mark_done(event_id, ttl_seconds)

    def try_claim(self, event_id: str, claim_ttl: Optional[int] = None) -> bool:
        with self._lock:
            if event_id in self._states:
                return False
            if len(self._states) >= self._capacity:
                oldest = self._queue.popleft()
                self._states.pop(oldest, None)
            self._states[event_id] = "PROCESSING"
            self._queue.append(event_id)
            return True

    def claim(self, event_id: str, claim_ttl: Optional[int] = None) -> ClaimStatus:
        """Checks state and acquires the lease under a single lock (no re-entry)."""
        with self._lock:
            state = self._states.get(event_id)
            if state == "DONE":
                return ClaimStatus.DONE
            if state == "PROCESSING":
                return ClaimStatus.IN_PROGRESS
            if len(self._states) >= self._capacity:
                oldest = self._queue.popleft()
                self._states.pop(oldest, None)
            self._states[event_id] = "PROCESSING"
            self._queue.append(event_id)
            return ClaimStatus.CLAIMED

    def mark_done(self, event_id: str, ttl_seconds: Optional[int] = None) -> None:
        with self._lock:
            self._states[event_id] = "DONE"
            if event_id not in self._queue:
                self._queue.append(event_id)

    def release_claim(self, event_id: str) -> None:
        with self._lock:
            if self._states.get(event_id) == "PROCESSING":
                self._states.pop(event_id, None)
                try:
                    self._queue.remove(event_id)
                except ValueError:
                    pass

    def clear(self) -> None:
        with self._lock:
            self._states.clear()
            self._queue.clear()


class RedisIdempotencyStore(IdempotencyStore):
    """Durable Redis-backed idempotency store implementing atomic claims (CP7.5).

    Atomic claim guarantees:
    1. try_claim: Executes atomic 'SET key PROCESSING NX EX claim_ttl'.
       - Multiple concurrent deliveries race on this atomic operation; exactly one succeeds.
    2. mark_done: Executes 'SET key DONE EX idempotency_ttl'.
       - Preserves duplicate protection across consumer process restarts and horizontal replicas.
    3. release_claim: Deletes key if state is PROCESSING, permitting delayed retries to re-acquire.
    """

    def __init__(
        self,
        redis_client: Any,
        idempotency_ttl_seconds: int = 86400,
        processing_claim_ttl_seconds: int = 60,
        key_prefix: str = "swiftlet:idempotency:",
    ) -> None:
        self.redis = redis_client
        self.idempotency_ttl_seconds = max(60, idempotency_ttl_seconds)
        self.processing_claim_ttl_seconds = max(5, processing_claim_ttl_seconds)
        self.key_prefix = key_prefix

    def _key(self, event_id: str) -> str:
        return f"{self.key_prefix}{event_id}"

    async def try_claim_async(self, event_id: str, claim_ttl: Optional[int] = None) -> bool:
        """Atomic reservation via Redis SET NX EX."""
        key = self._key(event_id)
        ttl = claim_ttl or self.processing_claim_ttl_seconds
        try:
            res = await self.redis.set(key, "PROCESSING", nx=True, ex=ttl)
            return bool(res)
        except Exception as exc:
            logger.error("[REDIS IDEMPOTENCY ERROR] try_claim failed for eventId='%s': %s", event_id, exc)
            raise

    # Never overwrites an existing key: every write is SET ... NX. If the key is absent
    # on the GET (defensive; Redis scripts run atomically), the claim is retried with NX
    # and anything other than a successful NX is reported as IN_PROGRESS.
    _CLAIM_LUA = """
    if redis.call('SET', KEYS[1], 'PROCESSING', 'NX', 'EX', ARGV[1]) then
        return 'CLAIMED'
    end
    local v = redis.call('GET', KEYS[1])
    if v == false then
        if redis.call('SET', KEYS[1], 'PROCESSING', 'NX', 'EX', ARGV[1]) then
            return 'CLAIMED'
        end
        return 'PROCESSING'
    end
    return v
    """

    async def claim_async(self, event_id: str, claim_ttl: Optional[int] = None) -> ClaimStatus:
        """Atomic claim that distinguishes CLAIMED, DONE and IN_PROGRESS in one round trip.

        Raises on Redis errors so the caller can treat the store as unavailable.
        """
        key = self._key(event_id)
        ttl = int(claim_ttl or self.processing_claim_ttl_seconds)
        try:
            res = await self.redis.eval(self._CLAIM_LUA, 1, key, str(ttl))
        except Exception as exc:
            logger.error("[REDIS IDEMPOTENCY ERROR] claim failed for eventId='%s': %s", event_id, exc)
            raise
        if isinstance(res, bytes):
            res = res.decode("utf-8", errors="replace")
        if res == "CLAIMED":
            return ClaimStatus.CLAIMED
        if res == "DONE":
            return ClaimStatus.DONE
        return ClaimStatus.IN_PROGRESS

    async def mark_done_async(self, event_id: str, ttl_seconds: Optional[int] = None) -> None:
        """Mark as DONE with long-term retention TTL."""
        key = self._key(event_id)
        ttl = ttl_seconds or self.idempotency_ttl_seconds
        try:
            await self.redis.set(key, "DONE", ex=ttl)
        except Exception as exc:
            logger.error("[REDIS IDEMPOTENCY ERROR] mark_done failed for eventId='%s': %s", event_id, exc)
            raise

    async def release_claim_async(self, event_id: str) -> None:
        """Releases PROCESSING lease only if still in PROCESSING state."""
        key = self._key(event_id)
        lua = """
        if redis.call('get', KEYS[1]) == 'PROCESSING' then
            return redis.call('del', KEYS[1])
        else
            return 0
        end
        """
        try:
            await self.redis.eval(lua, 1, key)
        except Exception as exc:
            logger.error("[REDIS IDEMPOTENCY ERROR] release_claim failed for eventId='%s': %s", event_id, exc)
            # Do not crash caller on failed release

    async def has_processed_async(self, event_id: str) -> bool:
        key = self._key(event_id)
        try:
            val = await self.redis.get(key)
            return val is not None
        except Exception as exc:
            logger.error("[REDIS IDEMPOTENCY ERROR] has_processed failed for eventId='%s': %s", event_id, exc)
            raise

    async def clear_async(self) -> None:
        try:
            keys = await self.redis.keys(f"{self.key_prefix}*")
            if keys:
                await self.redis.delete(*keys)
        except Exception as exc:
            logger.error("[REDIS IDEMPOTENCY ERROR] clear failed: %s", exc)

    # Sync interface compatibility
    def try_claim(self, event_id: str, claim_ttl: Optional[int] = None) -> bool:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            return loop.create_task(self.try_claim_async(event_id, claim_ttl))  # type: ignore
        except RuntimeError:
            return asyncio.run(self.try_claim_async(event_id, claim_ttl))

    def mark_done(self, event_id: str, ttl_seconds: Optional[int] = None) -> None:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.mark_done_async(event_id, ttl_seconds))
        except RuntimeError:
            asyncio.run(self.mark_done_async(event_id, ttl_seconds))

    def release_claim(self, event_id: str) -> None:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.release_claim_async(event_id))
        except RuntimeError:
            asyncio.run(self.release_claim_async(event_id))

    def has_processed(self, event_id: str) -> bool:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            # If in loop, must use has_processed_async
            return asyncio.run(self.has_processed_async(event_id))
        except RuntimeError:
            return asyncio.run(self.has_processed_async(event_id))

    def mark_processed(self, event_id: str, ttl_seconds: Optional[int] = None) -> None:
        self.mark_done(event_id, ttl_seconds)

    def clear(self) -> None:
        import asyncio
        try:
            asyncio.run(self.clear_async())
        except Exception:
            pass


default_idempotency_store = InMemoryIdempotencyStore()

__all__ = [
    "ClaimStatus",
    "IdempotencyStore",
    "InMemoryIdempotencyStore",
    "RedisIdempotencyStore",
    "default_idempotency_store",
]
