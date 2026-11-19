"""CP8.5 — Unit tests for consumer claim states (CLAIMED / DONE / IN_PROGRESS / store unavailable)."""
from __future__ import annotations

import asyncio
import json
import socket
import uuid
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from aio_pika.abc import AbstractIncomingMessage

from app.dependencies import init_app_state
from app.domain.enums import DevicePlatform
from app.infrastructure.rabbitmq.config import RabbitMQSettings, RedisSettings
from app.infrastructure.rabbitmq.consumer import RabbitMQAlertConsumer
from app.infrastructure.rabbitmq.idempotency import (
    ClaimStatus,
    IdempotencyStore,
    InMemoryIdempotencyStore,
    RedisIdempotencyStore,
)
from app.ports.recipient_resolver import RecipientInfo
from app.repositories.in_memory_alert_repo import InMemoryAlertRepository
from app.repositories.in_memory_notification_repo import InMemoryNotificationRepository
from app.repositories.in_memory_user_device_repo import InMemoryUserDeviceRepository
from app.schemas.canonical import UserDevice
from app.services.in_memory_recipient_resolver import InMemoryRecipientResolver
from app.services.mock_fcm_provider import MockFCMProvider

RETRY_EX = "swiftlet.notification.retry"
DLX_EX = "swiftlet.notification.dlx"


@pytest.fixture
def env():
    alert_repo = InMemoryAlertRepository()
    notif_repo = InMemoryNotificationRepository()
    devices = InMemoryUserDeviceRepository()
    devices.register_device(UserDevice(device_id="d1", user_id="u1", fcm_token="t1", platform=DevicePlatform.ANDROID, is_enabled=True))
    resolver = InMemoryRecipientResolver()
    resolver.register_recipient("FARM-01", RecipientInfo(user_id="u1", email="u1@test.vn", roles=["FARM_OWNER"]))
    service = init_app_state(alert_repo=alert_repo, notification_repo=notif_repo, user_device_repo=devices,
                             recipient_resolver=resolver, fcm_provider=MockFCMProvider())
    return service, alert_repo


def _settings(**kw) -> RabbitMQSettings:
    base = dict(enabled=True, max_retries=3, max_defers=5, nack_backoff_base_ms=500, nack_backoff_max_ms=2000)
    base.update(kw)
    return RabbitMQSettings(**base)


def _event(event_id: Optional[str] = None) -> dict:
    return {
        "eventId": event_id or str(uuid.uuid4()),
        "eventType": "iot.environment.high_temperature.started",
        "eventVersion": "1.0",
        "occurredAt": "2026-11-06T05:00:00.000Z",
        "producer": "iot-service",
        "correlationId": None,
        "payload": {"farmId": "FARM-01", "deviceId": "DEV-01", "metric": "temperature", "value": 35.0, "threshold": 31.0, "unit": "°C"},
    }


def _msg(body: dict, headers: Optional[dict] = None) -> AbstractIncomingMessage:
    m = MagicMock(spec=AbstractIncomingMessage)
    m.body = json.dumps(body).encode()
    m.routing_key = body["eventType"]
    m.headers = headers or {}
    m.ack, m.nack, m.reject = AsyncMock(), AsyncMock(), AsyncMock()
    return m


def _consumer(service, store, **kw) -> RabbitMQAlertConsumer:
    c = RabbitMQAlertConsumer(service=service, idempotency_store=store, settings=_settings(**kw), redis_settings=RedisSettings())
    c._publish_to_exchange = AsyncMock()
    return c


@pytest.mark.anyio
async def test_in_progress_lease_is_deferred_not_acked_as_duplicate(env):
    service, alerts = env
    store = InMemoryIdempotencyStore()
    ev = _event()
    assert store.try_claim(ev["eventId"])  # lease held by another (crashed) delivery
    c = _consumer(service, store)
    m = _msg(ev, {"x-retry-count": 1})

    await c._handle_message(m)

    assert c.duplicate_count == 0 and c.deferred_count == 1
    assert alerts.list_alerts() == []
    kwargs = c._publish_to_exchange.await_args.kwargs
    assert kwargs["exchange_name"] == RETRY_EX
    assert kwargs["body"] == m.body  # envelope unchanged
    assert kwargs["headers"]["x-defer-count"] == 1
    assert kwargs["headers"]["x-retry-count"] == 1  # processing-failure budget untouched
    assert kwargs["headers"]["x-defer-reason"] == "claim_in_progress"
    m.ack.assert_awaited_once()  # ACK only after the deferred copy was confirmed
    m.nack.assert_not_awaited()


@pytest.mark.anyio
async def test_done_is_acked_as_duplicate_without_publish(env):
    service, alerts = env
    store = InMemoryIdempotencyStore()
    ev = _event()
    store.mark_done(ev["eventId"])
    c = _consumer(service, store)
    m = _msg(ev)

    await c._handle_message(m)

    assert c.duplicate_count == 1 and c.deferred_count == 0
    c._publish_to_exchange.assert_not_awaited()
    m.ack.assert_awaited_once()
    assert alerts.list_alerts() == []


@pytest.mark.anyio
async def test_store_unavailable_defers_instead_of_immediate_requeue(env):
    service, _ = env

    class Broken(InMemoryIdempotencyStore):
        def claim(self, event_id, claim_ttl=None):
            raise ConnectionError("redis down")

    c = _consumer(service, Broken())
    m = _msg(_event())

    await c._handle_message(m)

    m.nack.assert_not_awaited()
    assert c._publish_to_exchange.await_args.kwargs["headers"]["x-defer-reason"] == "idempotency_store_unavailable"
    m.ack.assert_awaited_once()


@pytest.mark.anyio
async def test_defer_publish_failure_never_acks_and_nacks_after_capped_backoff(env, monkeypatch):
    service, _ = env
    store = InMemoryIdempotencyStore()
    ev = _event()
    store.try_claim(ev["eventId"])
    c = _consumer(service, store)
    c._publish_to_exchange = AsyncMock(side_effect=ConnectionError("broker gone"))
    delays = []

    async def fake_sleep(s):
        delays.append(s)

    monkeypatch.setattr("app.infrastructure.rabbitmq.consumer.asyncio.sleep", fake_sleep)
    msgs = [_msg(ev) for _ in range(4)]
    for m in msgs:
        await c._handle_message(m)

    for m in msgs:
        m.ack.assert_not_awaited()
        m.nack.assert_awaited_once_with(requeue=True)
    assert delays == [0.5, 1.0, 2.0, 2.0]  # exponential, capped at nack_backoff_max_ms


@pytest.mark.anyio
async def test_defer_exhaustion_dead_letters_with_reason(env):
    service, _ = env
    store = InMemoryIdempotencyStore()
    ev = _event()
    store.try_claim(ev["eventId"])
    c = _consumer(service, store, max_defers=5)
    m = _msg(ev, {"x-defer-count": 5})

    await c._handle_message(m)

    kwargs = c._publish_to_exchange.await_args.kwargs
    assert kwargs["exchange_name"] == DLX_EX
    assert kwargs["headers"]["x-dead-letter-reason"] == "defer_exhausted"
    assert c.dead_lettered_count == 1
    m.ack.assert_awaited_once()


@pytest.mark.anyio
async def test_retry_publish_failure_is_nacked_after_backoff_not_left_unacked(env, monkeypatch):
    service, _ = env
    c = _consumer(service, InMemoryIdempotencyStore())
    c.mapper.process_envelope = MagicMock(side_effect=RuntimeError("db down"))
    c._publish_to_exchange = AsyncMock(side_effect=ConnectionError("broker gone"))
    monkeypatch.setattr("app.infrastructure.rabbitmq.consumer.asyncio.sleep", AsyncMock())
    m = _msg(_event(), {"x-retry-count": 0})

    await c._handle_message(m)

    m.ack.assert_not_awaited()
    m.nack.assert_awaited_once_with(requeue=True)


def test_default_port_claim_never_reports_done_for_refused_claim():
    class LegacyStore(IdempotencyStore):
        def has_processed(self, e): return True
        def mark_processed(self, e, ttl_seconds=None): pass
        def try_claim(self, e, claim_ttl=None): return False
        def mark_done(self, e, ttl_seconds=None): pass
        def release_claim(self, e): pass
        def clear(self): pass

    assert LegacyStore().claim("x") == ClaimStatus.IN_PROGRESS


def test_in_memory_claim_states():
    s = InMemoryIdempotencyStore()
    assert s.claim("e") == ClaimStatus.CLAIMED
    assert s.claim("e") == ClaimStatus.IN_PROGRESS
    s.mark_done("e")
    assert s.claim("e") == ClaimStatus.DONE
    s2 = InMemoryIdempotencyStore()
    s2.claim("f")
    s2.release_claim("f")
    assert s2.claim("f") == ClaimStatus.CLAIMED


def _redis_up() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 6379), timeout=1):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not _redis_up(), reason="Redis 6379 not available")
@pytest.mark.anyio
async def test_redis_claim_states_against_real_redis():
    import redis.asyncio as aioredis

    client = aioredis.Redis(host="127.0.0.1", port=6379, decode_responses=False)
    store = RedisIdempotencyStore(client, processing_claim_ttl_seconds=5, key_prefix=f"swiftlet:test_claim:{uuid.uuid4().hex}:")
    try:
        assert await store.claim_async("e1", claim_ttl=1) == ClaimStatus.CLAIMED
        assert await store.claim_async("e1", claim_ttl=1) == ClaimStatus.IN_PROGRESS
        await asyncio.sleep(1.3)  # lease of a crashed owner expires
        assert await store.claim_async("e1", claim_ttl=5) == ClaimStatus.CLAIMED
        await store.mark_done_async("e1", ttl_seconds=60)
        assert await store.claim_async("e1") == ClaimStatus.DONE
        await store.release_claim_async("e1")  # must not delete DONE
        assert await store.claim_async("e1") == ClaimStatus.DONE
    finally:
        await store.clear_async()
        await client.aclose()


def test_claim_lua_never_writes_without_nx():
    """Every SET in the claim script must be NX so a live lease is never overwritten."""
    import re

    sets = re.findall(r"redis\.call\('SET'[^)]*\)", RedisIdempotencyStore._CLAIM_LUA)
    assert len(sets) == 2
    assert all("'NX'" in s for s in sets), sets


@pytest.mark.skipif(not _redis_up(), reason="Redis 6379 not available")
@pytest.mark.anyio
async def test_redis_claim_does_not_overwrite_or_extend_existing_lease():
    import redis.asyncio as aioredis

    client = aioredis.Redis(host="127.0.0.1", port=6379, decode_responses=False)
    store = RedisIdempotencyStore(client, key_prefix=f"swiftlet:test_claim:{uuid.uuid4().hex}:")
    try:
        key = store._key("e2")
        await client.set(key, "PROCESSING", ex=100)  # lease owned by consumer A
        assert await store.claim_async("e2", claim_ttl=5) == ClaimStatus.IN_PROGRESS
        assert await client.get(key) == b"PROCESSING"
        assert 95 <= await client.ttl(key) <= 100  # not reset to 5 s
    finally:
        await store.clear_async()
        await client.aclose()


def test_in_memory_claim_is_atomic_under_threads():
    import inspect
    import threading

    src = inspect.getsource(InMemoryIdempotencyStore.claim)
    assert "self.claim(" not in src and "self.try_claim(" not in src  # no recursion / re-entry

    store = InMemoryIdempotencyStore()
    results = []
    barrier = threading.Barrier(16)

    def worker():
        barrier.wait()
        results.append(store.claim("race"))

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(ClaimStatus.CLAIMED) == 1
    assert results.count(ClaimStatus.IN_PROGRESS) == 15


@pytest.mark.anyio
async def test_inbox_already_processed_acks_restores_done_and_skips_side_effects(env):
    from app.infrastructure.rabbitmq.inbox import EventInbox, InboxResult

    class SeenInbox(EventInbox):
        def process_once(self, event_id, event_type, producer, handler):
            return InboxResult.ALREADY_PROCESSED

    service, alerts = env
    store = InMemoryIdempotencyStore()
    c = RabbitMQAlertConsumer(service=service, idempotency_store=store, settings=_settings(),
                              redis_settings=RedisSettings(), inbox=SeenInbox())
    c._publish_to_exchange = AsyncMock()
    ev = _event()
    m = _msg(ev)

    await c._handle_message(m)

    m.ack.assert_awaited_once()
    assert c.duplicate_count == 1 and c.processed_count == 0
    assert store.claim(ev["eventId"]) == ClaimStatus.DONE
    assert alerts.list_alerts() == []
