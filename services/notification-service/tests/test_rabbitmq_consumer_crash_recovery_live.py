"""CP8.5 — Real crash / redelivery tests for the Notification RabbitMQ consumer.

Every scenario runs the production consumer in a separate OS process against
real RabbitMQ, Redis and PostgreSQL, kills it with SIGKILL where relevant, and
verifies the outcome through notification_db and the real broker queues.

Requires: RabbitMQ 5672 (+ management 15672 for queue purge), Redis 6379,
NOTIFICATION_DATABASE_URL, and a `docker` CLI able to stop/start
`swiftletcare-redis` (scenario R2). Destructive scenarios only run when
CP85_DESTRUCTIVE=1.
"""
from __future__ import annotations

import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import List, Optional

import aio_pika
import psycopg
import pytest
import redis

SERVICE_ROOT = Path(__file__).resolve().parents[1]
CHILD = SERVICE_ROOT / "tests" / "helpers" / "consumer_crash_child.py"
AMQP_URL = "amqp://swiftlet:swiftlet123@127.0.0.1:5672/"
EXCHANGE_EVENTS = "swiftlet.domain.events"
Q_MAIN = "notification.alert-events.v1"
Q_RETRY = "notification.alert-events.v1.retry"
Q_DLQ = "notification.alert-events.v1.dlq"
DB_URL = os.getenv("NOTIFICATION_DATABASE_URL", "")


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.0):
            return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.skipif(
        not (_port_open(5672) and _port_open(6379) and DB_URL),
        reason="Requires live RabbitMQ, Redis and NOTIFICATION_DATABASE_URL",
    ),
    pytest.mark.skipif(os.getenv("CP85_DESTRUCTIVE") != "1", reason="Set CP85_DESTRUCTIVE=1 to run crash tests"),
    pytest.mark.skipif(sys.platform == "win32", reason="Uses SIGKILL/POSIX signals; run on Linux, WSL or in the CI container"),
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

class Child:
    def __init__(self, mode: str, prefix: str, claim_ttl: int, marker: Path, farm_id: str, log: Path, env_extra: Optional[dict] = None):
        env = dict(os.environ)
        env.update(env_extra or {})
        self.log = log
        self.proc = subprocess.Popen(
            [sys.executable, str(CHILD), mode, prefix, str(claim_ttl), str(marker), farm_id],
            stdout=open(log, "w"), stderr=subprocess.STDOUT, env=env, start_new_session=True,
        )
        self._wait_ready()

    def _wait_ready(self, timeout: float = 20.0) -> None:
        t0 = time.time()
        while time.time() - t0 < timeout:
            if "CHILD_READY" in self.log.read_text(errors="ignore"):
                return
            if self.proc.poll() is not None:
                raise RuntimeError(f"child exited early:\n{self.log.read_text()}")
            time.sleep(0.1)
        raise TimeoutError(self.log.read_text())

    def kill9(self) -> None:
        os.kill(self.proc.pid, signal.SIGKILL)
        self.proc.wait(timeout=10)

    def stop(self) -> None:
        if self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.kill9()

    def received(self, event_id: str) -> int:
        return sum(1 for ln in self.log.read_text(errors="ignore").splitlines()
                   if "[RABBITMQ CONSUMER RECEIVED]" in ln and event_id in ln)


async def _publish(event: dict, routing_key: str) -> None:
    conn = await aio_pika.connect_robust(AMQP_URL)
    try:
        ch = await conn.channel()
        ex = await ch.get_exchange(EXCHANGE_EVENTS)
        await ex.publish(
            aio_pika.Message(json.dumps(event).encode(), content_type="application/json",
                             delivery_mode=aio_pika.DeliveryMode.PERSISTENT, type=routing_key),
            routing_key=routing_key,
        )
    finally:
        await conn.close()


async def _purge_and_depths(purge: bool = False) -> dict:
    conn = await aio_pika.connect_robust(AMQP_URL)
    try:
        ch = await conn.channel()
        out = {}
        for name in (Q_MAIN, Q_RETRY, Q_DLQ):
            q = await ch.declare_queue(name, passive=True)
            if purge:
                await q.purge()
            out[name] = q.declaration_result.message_count
        return out
    finally:
        await conn.close()


async def _dlq_messages() -> List[aio_pika.abc.AbstractIncomingMessage]:
    conn = await aio_pika.connect_robust(AMQP_URL)
    msgs = []
    try:
        ch = await conn.channel()
        q = await ch.declare_queue(Q_DLQ, passive=True)
        while True:
            m = await q.get(no_ack=True, fail=False)
            if m is None:
                break
            msgs.append(m)
        return msgs
    finally:
        await conn.close()


def _alerts(farm_id: str) -> List[tuple]:
    with psycopg.connect(DB_URL) as c, c.cursor() as cur:
        cur.execute("SELECT alert_id, occurrence_count, status FROM alerts WHERE farm_id = %s", (farm_id,))
        return cur.fetchall()


def _marker(event_id: str) -> bool:
    with psycopg.connect(DB_URL) as c, c.cursor() as cur:
        cur.execute("SELECT 1 FROM processed_events WHERE event_id = %s", (event_id,))
        return cur.fetchone() is not None


def _notifications(farm_alert_ids: List[str]) -> int:
    if not farm_alert_ids:
        return 0
    with psycopg.connect(DB_URL) as c, c.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM notifications WHERE alert_id = ANY(%s)", (farm_alert_ids,))
        return cur.fetchone()[0]


def _new_event(ctx, device_id: str) -> dict:
    ev = _event(ctx["farm"], device_id)
    ctx["events"].append(ev["eventId"])
    return ev


def _event(farm_id: str, device_id: str, event_id: Optional[str] = None) -> dict:
    return {
        "eventId": event_id or str(uuid.uuid4()),
        "eventType": "iot.environment.high_temperature.started",
        "eventVersion": "1.0",
        "occurredAt": "2026-11-06T05:00:00.000Z",
        "producer": "iot-service",
        "correlationId": None,
        "payload": {"farmId": farm_id, "deviceId": device_id, "metric": "temperature",
                    "value": 36.5, "threshold": 32.0, "unit": "°C"},
    }


async def _wait_until(pred, timeout: float, step: float = 0.25) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        await asyncio.sleep(step)
    return pred()


def _wait_sync(pred, timeout: float, step: float = 0.5) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(step)
    return pred()


def _depths() -> dict:
    return asyncio.run(_purge_and_depths())


@pytest.fixture
def ctx(tmp_path):
    uid = uuid.uuid4().hex[:8]
    farm = f"FARM-CRASH-{uid}"
    prefix = f"swiftlet:test_crash:{uid}:"
    r = redis.Redis(host="127.0.0.1", port=6379)
    asyncio.run(_purge_and_depths(purge=True))
    children: List[Child] = []
    ctx_events: List[str] = []
    yield {"uid": uid, "farm": farm, "prefix": prefix, "tmp": tmp_path, "children": children, "redis": r, "events": ctx_events}
    for ch in children:
        ch.stop()
    try:
        for k in r.scan_iter(f"{prefix}*"):
            r.delete(k)
    except Exception:
        pass
    with psycopg.connect(DB_URL) as c, c.cursor() as cur:
        cur.execute("DELETE FROM notifications WHERE alert_id IN (SELECT alert_id FROM alerts WHERE farm_id=%s)", (farm,))
        cur.execute("DELETE FROM alerts WHERE farm_id=%s", (farm,))
        for eid in ctx_events:
            cur.execute("DELETE FROM processed_events WHERE event_id=%s", (eid,))
        c.commit()
    asyncio.run(_purge_and_depths(purge=True))


def _spawn(ctx, mode: str, claim_ttl: int, name: str, env_extra: Optional[dict] = None) -> Child:
    ch = Child(mode, ctx["prefix"], claim_ttl, ctx["tmp"] / f"{name}.marker", ctx["farm"], ctx["tmp"] / f"{name}.log", env_extra)
    ctx["children"].append(ch)
    return ch


# ---------------------------------------------------------------------------
# scenarios
# ---------------------------------------------------------------------------

def test_r1_consumer_killed_mid_processing_event_is_redelivered_and_processed_once(ctx):
    """Consumer A claims the event (PROCESSING) and is SIGKILLed before committing.
    Broker redelivers to consumer B while A's lease is still alive. B must NOT ACK
    it as a duplicate; it must defer and process it once the lease expires."""
    claim_ttl = 8
    a = _spawn(ctx, "hang_before_process", claim_ttl, "a")
    ev = _new_event(ctx, "NODE-R1")
    asyncio.run(_publish(ev, ev["eventType"]))
    assert asyncio.run(_wait_until(lambda: (ctx["tmp"] / "a.marker").exists(), 15)), a.log.read_text()
    assert ctx["redis"].get(ctx["prefix"] + ev["eventId"]) == b"PROCESSING"
    a.kill9()

    b = _spawn(ctx, "normal", claim_ttl, "b")
    ok = asyncio.run(_wait_until(lambda: len(_alerts(ctx["farm"])) == 1, timeout=claim_ttl + 25))
    alerts = _alerts(ctx["farm"])
    assert ok and len(alerts) == 1, f"event lost or duplicated: {alerts}\n{b.log.read_text()[-3000:]}"
    assert alerts[0][1] == 1
    assert _notifications([alerts[0][0]]) >= 1
    assert ctx["redis"].get(ctx["prefix"] + ev["eventId"]) == b"DONE"
    assert _marker(ev["eventId"])
    depths = asyncio.run(_purge_and_depths())
    assert depths == {Q_MAIN: 0, Q_RETRY: 0, Q_DLQ: 0}, depths
    assert b.received(ev["eventId"]) >= 2  # at least one deferral before processing


def test_r2_redis_outage_defers_without_hot_requeue_then_recovers(ctx):
    """Redis stopped while an event arrives: message must not be lost, must not be
    hot-requeued, and must be processed exactly once after Redis comes back."""
    b = _spawn(ctx, "normal", 30, "b")
    subprocess.run(["docker", "stop", "swiftletcare-redis"], check=True, capture_output=True)
    try:
        ev = _new_event(ctx, "NODE-R2")
        asyncio.run(_publish(ev, ev["eventType"]))
        time.sleep(12)
        receives_during_outage = b.received(ev["eventId"])
        assert _alerts(ctx["farm"]) == []
    finally:
        subprocess.run(["docker", "start", "swiftletcare-redis"], check=True, capture_output=True)
    # 12 s outage with 5 s deferral (+ capped backoff) => a handful of deliveries, never hundreds
    assert 1 <= receives_during_outage <= 6, f"hot requeue detected: {receives_during_outage} deliveries"
    ok = asyncio.run(_wait_until(lambda: len(_alerts(ctx["farm"])) == 1, timeout=25))
    assert ok, b.log.read_text()[-3000:]
    assert _alerts(ctx["farm"])[0][1] == 1
    depths = asyncio.run(_purge_and_depths())
    assert depths == {Q_MAIN: 0, Q_RETRY: 0, Q_DLQ: 0}, depths


def test_r3_done_event_redelivered_is_acked_without_side_effects(ctx):
    """Regression: a fully processed (DONE) event published again is ACKed as duplicate."""
    b = _spawn(ctx, "normal", 30, "b")
    ev = _new_event(ctx, "NODE-R3")
    asyncio.run(_publish(ev, ev["eventType"]))
    assert asyncio.run(_wait_until(lambda: len(_alerts(ctx["farm"])) == 1, 15))
    notif_before = _notifications([_alerts(ctx["farm"])[0][0]])
    asyncio.run(_publish(ev, ev["eventType"]))
    assert asyncio.run(_wait_until(lambda: b.received(ev["eventId"]) == 2, 15))
    time.sleep(1)
    alerts = _alerts(ctx["farm"])
    assert len(alerts) == 1 and alerts[0][1] == 1
    assert _notifications([alerts[0][0]]) == notif_before
    assert asyncio.run(_purge_and_depths()) == {Q_MAIN: 0, Q_RETRY: 0, Q_DLQ: 0}


def test_r4_lease_never_released_goes_to_dlq_after_bounded_deferrals(ctx):
    """A PROCESSING lease that never expires (stuck owner) must not loop forever:
    after RABBITMQ_MAX_DEFERS deferrals the event is dead-lettered with a reason."""
    ev = _new_event(ctx, "NODE-R4")
    ctx["redis"].set(ctx["prefix"] + ev["eventId"], "PROCESSING", ex=600)
    b = _spawn(ctx, "normal", 30, "b", env_extra={"RABBITMQ_MAX_DEFERS": "2"})
    asyncio.run(_publish(ev, ev["eventType"]))
    ok = _wait_sync(lambda: _depths()[Q_DLQ] == 1, timeout=30)
    assert ok, b.log.read_text()[-3000:]
    assert b.received(ev["eventId"]) == 3  # original + 2 deferrals
    dlq = asyncio.run(_dlq_messages())
    assert len(dlq) == 1
    assert dlq[0].headers.get("x-dead-letter-reason") == "defer_exhausted"
    assert json.loads(dlq[0].body)["eventId"] == ev["eventId"]  # envelope unchanged
    assert _alerts(ctx["farm"]) == []


def test_r5_crash_after_postgres_commit_before_mark_done_has_no_duplicate_side_effects(ctx):
    """Consumer commits the alert to PostgreSQL, then dies before Redis mark_done.
    After the lease expires the broker redelivery must not re-apply side effects."""
    claim_ttl = 6
    a = _spawn(ctx, "crash_after_commit", claim_ttl, "a")
    ev = _new_event(ctx, "NODE-R5")
    asyncio.run(_publish(ev, ev["eventType"]))
    assert asyncio.run(_wait_until(lambda: a.proc.poll() is not None, 15))
    first = _alerts(ctx["farm"])
    assert len(first) == 1 and first[0][1] == 1
    notif_first = _notifications([first[0][0]])
    b = _spawn(ctx, "normal", claim_ttl, "b")
    assert _wait_sync(lambda: b.received(ev["eventId"]) >= 1 and "result='processed'" in b.log.read_text()
                      or "result='duplicate'" in b.log.read_text(), timeout=claim_ttl + 25)
    time.sleep(1)
    after = _alerts(ctx["farm"])
    assert len(after) == 1
    assert after[0][1] == 1, f"occurrence_count re-applied on redelivery: {after[0][1]}"
    assert _notifications([after[0][0]]) == notif_first
    assert notif_first >= 1  # side effects committed with the marker
    assert _marker(ev["eventId"])
    assert "already_processed_durable" in b.log.read_text()
    assert ctx["redis"].get(ctx["prefix"] + ev["eventId"]) == b"DONE"  # DONE restored
    assert _depths() == {Q_MAIN: 0, Q_RETRY: 0, Q_DLQ: 0}


def test_r2b_fast_failing_idempotency_store_is_not_hot_requeued(ctx):
    """Redis reachable but rejecting every command instantly (NOAUTH). Without a
    delay the consumer would redeliver the event in a tight loop."""
    b = _spawn(ctx, "normal", 30, "b")
    pw = f"cp85-{ctx['uid']}"
    ctx["redis"].config_set("requirepass", pw)
    try:
        ev = _new_event(ctx, "NODE-R2B")
        asyncio.run(_publish(ev, ev["eventType"]))
        time.sleep(8)
        receives = b.received(ev["eventId"])
        assert _alerts(ctx["farm"]) == []
    finally:
        authed = redis.Redis(host="127.0.0.1", port=6379, password=pw)
        authed.config_set("requirepass", "")
    assert 1 <= receives <= 4, f"hot requeue detected: {receives} deliveries in 8 s"
    assert asyncio.run(_wait_until(lambda: len(_alerts(ctx["farm"])) == 1, timeout=20)), b.log.read_text()[-3000:]
    assert _alerts(ctx["farm"])[0][1] == 1
    assert _depths() == {Q_MAIN: 0, Q_RETRY: 0, Q_DLQ: 0}



def test_r6_redis_lost_all_keys_processed_event_is_not_reapplied(ctx):
    """Redis loses every idempotency key (FLUSHDB / new volume). A redelivery of an
    already processed event must be recognised by the PostgreSQL inbox."""
    b = _spawn(ctx, "normal", 30, "b")
    ev = _new_event(ctx, "NODE-R6")
    asyncio.run(_publish(ev, ev["eventType"]))
    assert asyncio.run(_wait_until(lambda: len(_alerts(ctx["farm"])) == 1, 15))
    alert_id = _alerts(ctx["farm"])[0][0]
    notif_before = _notifications([alert_id])
    ctx["redis"].flushdb()
    assert ctx["redis"].get(ctx["prefix"] + ev["eventId"]) is None
    asyncio.run(_publish(ev, ev["eventType"]))
    assert _wait_sync(lambda: "already_processed_durable" in b.log.read_text(), 15), b.log.read_text()[-3000:]
    alerts = _alerts(ctx["farm"])
    assert len(alerts) == 1 and alerts[0][1] == 1
    assert _notifications([alert_id]) == notif_before
    assert ctx["redis"].get(ctx["prefix"] + ev["eventId"]) == b"DONE"
    assert _depths() == {Q_MAIN: 0, Q_RETRY: 0, Q_DLQ: 0}


def test_r7_postgres_rollback_leaves_no_marker_and_retry_applies_all_effects(ctx):
    """The first attempt writes the alert then fails on the notification insert:
    the alert and the marker must both be rolled back. The retry (existing retry
    queue) must then commit alert + notifications + marker together."""
    b = _spawn(ctx, "fail_once_after_alert_write", 30, "b")
    ev = _new_event(ctx, "NODE-R7")
    asyncio.run(_publish(ev, ev["eventType"]))
    assert asyncio.run(_wait_until(lambda: (ctx["tmp"] / "b.marker").exists(), 15)), b.log.read_text()
    assert _wait_sync(lambda: "result='retry_scheduled'" in b.log.read_text(), 10)
    # between attempts: nothing of the failed attempt is visible
    assert _alerts(ctx["farm"]) == []
    assert not _marker(ev["eventId"])
    assert _wait_sync(lambda: len(_alerts(ctx["farm"])) == 1, 20), b.log.read_text()[-3000:]
    alert_id, occ, _ = _alerts(ctx["farm"])[0]
    assert occ == 1
    assert _marker(ev["eventId"])
    assert _notifications([alert_id]) >= 1
    assert _depths() == {Q_MAIN: 0, Q_RETRY: 0, Q_DLQ: 0}
