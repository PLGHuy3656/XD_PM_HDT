"""CP8.5 — PostgreSQL inbox + shared transaction integration tests (real notification_db).

Verifies that the processed_events marker and every repository change caused by an
event are committed in ONE transaction, and that nothing is committed on failure.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from typing import List

import psycopg
import pytest

from app.database import get_connection, in_transaction_scope, transaction_scope
from app.dependencies import init_app_state
from app.domain.enums import DevicePlatform
from app.infrastructure.rabbitmq.envelope import CanonicalEnvelope
from app.infrastructure.rabbitmq.inbox import InboxResult, PostgresEventInbox
from app.infrastructure.rabbitmq.mapper import EventMapper
from app.ports.recipient_resolver import RecipientInfo
from app.repositories.postgres_alert_repo import PostgreSQLAlertRepository
from app.repositories.postgres_notification_repo import PostgreSQLNotificationRepository
from app.repositories.postgres_user_device_repo import PostgreSQLUserDeviceRepository
from app.schemas.canonical import UserDevice
from app.services.in_memory_recipient_resolver import InMemoryRecipientResolver
from app.services.mock_fcm_provider import MockFCMProvider

DB_URL = os.getenv("NOTIFICATION_DATABASE_URL", "")


def _db_ready() -> bool:
    if not DB_URL:
        return False
    try:
        with psycopg.connect(DB_URL, connect_timeout=2) as c:
            return c.execute("SELECT to_regclass('public.processed_events')").fetchone()[0] is not None
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="notification_db with migration 002 not available")


@pytest.fixture
def env():
    uid = uuid.uuid4().hex[:8]
    farm = f"FARM-INBOX-{uid}"
    user = f"user-inbox-{uid}"
    resolver = InMemoryRecipientResolver()
    resolver.register_recipient(farm, RecipientInfo(user_id=user, email=f"{user}@test.vn", roles=["FARM_OWNER"]))
    devices = PostgreSQLUserDeviceRepository(DB_URL)
    devices.register_device(UserDevice(device_id=f"dev-{uid}", user_id=user, fcm_token=f"tok-{uid}",
                                       platform=DevicePlatform.ANDROID, is_enabled=True))
    fcm = MockFCMProvider()
    service = init_app_state(
        alert_repo=PostgreSQLAlertRepository(DB_URL),
        notification_repo=PostgreSQLNotificationRepository(DB_URL),
        user_device_repo=devices,
        recipient_resolver=resolver,
        fcm_provider=fcm,
    )
    events: List[str] = []
    yield {"farm": farm, "user": user, "uid": uid, "service": service, "fcm": fcm,
           "mapper": EventMapper(service), "inbox": PostgresEventInbox(DB_URL), "events": events}
    with psycopg.connect(DB_URL) as c:
        c.execute("DELETE FROM notifications WHERE user_id=%s", (user,))
        c.execute("DELETE FROM alerts WHERE farm_id=%s", (farm,))
        c.execute("DELETE FROM user_devices WHERE user_id=%s", (user,))
        c.execute("DELETE FROM processed_events WHERE event_id = ANY(%s)", (events,))
        c.commit()


def _envelope(env, device: str = "NODE-1", event_id: str | None = None) -> CanonicalEnvelope:
    eid = event_id or str(uuid.uuid4())
    env["events"].append(eid)
    body = {
        "eventId": eid, "eventType": "iot.environment.high_temperature.started", "eventVersion": "1.0",
        "occurredAt": "2026-11-06T05:00:00.000Z", "producer": "iot-service", "correlationId": None,
        "payload": {"farmId": env["farm"], "deviceId": device, "metric": "temperature",
                    "value": 36.0, "threshold": 32.0, "unit": "°C"},
    }
    return CanonicalEnvelope.parse_raw_json(json.dumps(body).encode())


def _state(env, event_id: str):
    """Reads committed state through an independent connection."""
    with psycopg.connect(DB_URL) as c:
        alerts = c.execute("SELECT alert_id, occurrence_count FROM alerts WHERE farm_id=%s", (env["farm"],)).fetchall()
        notifs = c.execute("SELECT channel, delivery_status FROM notifications WHERE user_id=%s", (env["user"],)).fetchall()
        marker = c.execute("SELECT 1 FROM processed_events WHERE event_id=%s", (event_id,)).fetchone() is not None
    return alerts, notifs, marker


def _run(env, envl: CanonicalEnvelope, handler=None) -> InboxResult:
    return env["inbox"].process_once(envl.event_id, envl.event_type, envl.producer,
                                     handler or (lambda: env["mapper"].process_envelope(envl)))


def test_marker_alert_and_notifications_commit_together(env):
    envl = _envelope(env)
    assert _run(env, envl) == InboxResult.PROCESSED
    alerts, notifs, marker = _state(env, envl.event_id)
    assert marker and len(alerts) == 1 and alerts[0][1] == 1
    assert sorted(n[0] for n in notifs) == ["FCM", "IN_APP"]  # side effects present with the marker
    assert ("FCM", "SENT") in notifs
    assert len(env["fcm"].sent_messages) == 1


def test_uncommitted_effects_are_invisible_to_other_connections(env):
    envl = _envelope(env)
    seen = {}

    def handler():
        env["mapper"].process_envelope(envl)
        assert in_transaction_scope()
        seen["inside"] = _state(env, envl.event_id)  # independent connection, before COMMIT

    assert _run(env, envl, handler) == InboxResult.PROCESSED
    assert seen["inside"] == ([], [], False)  # one transaction, not per-repository autocommit
    alerts, notifs, marker = _state(env, envl.event_id)
    assert marker and len(alerts) == 1 and len(notifs) == 2


def test_failure_after_alert_write_rolls_back_everything_including_marker(env):
    envl = _envelope(env)
    repo = env["service"].notification_repo
    original = repo.save

    def failing_save(n):
        raise RuntimeError("injected failure after alert insert")

    repo.save = failing_save
    with pytest.raises(RuntimeError):
        _run(env, envl)
    assert _state(env, envl.event_id) == ([], [], False)  # no alert, no notification, no marker

    repo.save = original
    assert _run(env, envl) == InboxResult.PROCESSED  # redelivery applies all effects
    alerts, notifs, marker = _state(env, envl.event_id)
    assert marker and len(alerts) == 1 and alerts[0][1] == 1 and len(notifs) == 2


def test_already_processed_event_skips_handler(env):
    envl = _envelope(env)
    assert _run(env, envl) == InboxResult.PROCESSED
    calls = []
    assert _run(env, envl, lambda: calls.append(1)) == InboxResult.ALREADY_PROCESSED
    assert calls == []
    alerts, notifs, _ = _state(env, envl.event_id)
    assert alerts[0][1] == 1 and len(notifs) == 2


def test_concurrent_deliveries_of_same_event_apply_once(env):
    envl = _envelope(env)
    results, errors = [], []
    barrier = threading.Barrier(2)

    def worker():
        try:
            barrier.wait()
            results.append(_run(env, envl))
        except Exception as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(20)
    assert errors == []
    assert sorted(r.value for r in results) == ["ALREADY_PROCESSED", "PROCESSED"]
    alerts, notifs, marker = _state(env, envl.event_id)
    assert marker and len(alerts) == 1 and alerts[0][1] == 1 and len(notifs) == 2


def test_different_events_same_dedup_key_merge_inside_transactions(env):
    a, b = _envelope(env, "NODE-X"), _envelope(env, "NODE-X")
    assert _run(env, a) == InboxResult.PROCESSED
    assert _run(env, b) == InboxResult.PROCESSED
    alerts, notifs, _ = _state(env, b.event_id)
    assert len(alerts) == 1 and alerts[0][1] == 2  # business dedup unchanged
    assert len(notifs) == 2  # notifications only for the new alert


def test_repository_calls_outside_scope_are_unchanged(env):
    assert not in_transaction_scope()
    conn = get_connection(DB_URL)
    try:
        assert isinstance(conn, psycopg.Connection)
    finally:
        conn.close()


def test_nested_scope_rejected():
    with transaction_scope(DB_URL):
        with pytest.raises(RuntimeError):
            with transaction_scope(DB_URL):
                pass
