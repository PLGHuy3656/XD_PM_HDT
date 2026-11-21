"""INT03-R1: Management business domain events.

Delivery model (honest limits):
- Business data is committed first by the repository. Only then is the event recorded in
  ``management_event_outbox`` (separate short transaction). A crash between those two commits can
  lose the event; the business change itself is never rolled back or faked.
- A background dispatcher publishes PENDING rows to RabbitMQ (topic exchange
  ``swiftlet.domain.events``, routing key = eventType, persistent messages, publisher confirms) and
  retries with backoff. If RabbitMQ is down the row stays PENDING; nothing claims it was delivered.
- Each event has a unique eventId; Notification stores (event_id, user_id) uniquely, so redelivery
  never creates duplicate notifications.
- Recipients are resolved here from management_db (authoritative) and sent as ``recipientUserIds``.
  Payloads never contain passwords, hashes or tokens.
"""
from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from psycopg.types.json import Jsonb

from app.config import settings
from app.database import get_connection

logger = logging.getLogger(__name__)

PRODUCER = "management-service"
EVENT_VERSION = "1.0"

EVENT_TYPES = {
    "management.user.created",
    "management.farm.approval_requested",
    "management.farm.approved",
    "management.farm.rejected",
    "management.technician.assigned",
    "management.technician.unassigned",
    "management.device.registered",
    "management.inspection_request.created",
    "management.inspection_request.assigned",
    "management.inspection_request.status_changed",
    "management.inspection_request.requeued",
}

_FORBIDDEN_KEYS = {"password", "password_hash", "token", "access_token", "jwt", "secret"}


def _clean(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k.lower() not in _FORBIDDEN_KEYS and v is not None}


def build_envelope(event_type: str, payload: dict[str, Any], recipients: Iterable[str], correlation_id: str | None = None) -> dict:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unknown management event type: {event_type}")
    event_id = str(uuid.uuid4())
    clean = _clean(dict(payload))
    clean["recipientUserIds"] = sorted({str(r) for r in recipients if r})
    return {
        "eventId": event_id,
        "eventType": event_type,
        "eventVersion": EVENT_VERSION,
        "occurredAt": datetime.now(timezone.utc).isoformat(),
        "producer": PRODUCER,
        "correlationId": correlation_id or event_id,
        "payload": clean,
    }


def record_event(event_type: str, payload: dict[str, Any], recipients: Iterable[str], correlation_id: str | None = None) -> str | None:
    """Record an event in the outbox AFTER the business commit. Returns eventId or None.

    Never raises: a failure to record is logged (the business operation already succeeded and is
    not reported as having sent a notification).
    """
    recipient_list = [str(r) for r in recipients if r]
    if not settings.events_enabled or not recipient_list:
        return None
    try:
        envelope = build_envelope(event_type, payload, recipient_list, correlation_id)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO management_event_outbox (id, event_type, envelope)
                    VALUES (%s, %s, %s)
                    """,
                    (envelope["eventId"], event_type, Jsonb(envelope)),
                )
            conn.commit()
        _wake_dispatcher()
        return envelope["eventId"]
    except Exception:
        logger.exception("Failed to record management event %s in outbox", event_type)
        return None


# ---------------------------------------------------------------- recipients (authoritative)

def admin_user_ids(exclude: str | None = None) -> list[str]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT u.id FROM users u
                JOIN user_roles ur ON ur.user_id = u.id
                JOIN roles r ON r.id = ur.role_id
                WHERE r.name = 'ADMIN' AND u.status = 'ACTIVE'
                """
            )
            ids = [str(r[0]) for r in cur.fetchall()]
    return [i for i in ids if i != (str(exclude) if exclude else None)]


def farm_context(farm_id: str) -> dict | None:
    """Owner + active technicians + display names for a farm (canonical UUID)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT f.id, f.farm_code, f.name, f.owner_id, u.full_name FROM farms f "
                "LEFT JOIN users u ON u.id = f.owner_id WHERE f.id = %s",
                (farm_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            cur.execute(
                "SELECT technician_id FROM technician_assignments WHERE farm_id = %s AND is_active = TRUE",
                (farm_id,),
            )
            techs = [str(r[0]) for r in cur.fetchall()]
    return {
        "farm_id": str(row[0]),
        "farm_code": row[1],
        "farm_name": row[2],
        "owner_id": str(row[3]) if row[3] else None,
        "owner_name": row[4],
        "technician_ids": techs,
    }


def user_display_name(user_id: str | None) -> str | None:
    if not user_id:
        return None
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT full_name FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------- dispatcher

_wake = threading.Event()
_stop = threading.Event()
_thread: threading.Thread | None = None


def _wake_dispatcher() -> None:
    _wake.set()


def _claim_batch(limit: int = 20) -> list[tuple[str, dict, int]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, envelope, attempts FROM management_event_outbox
                WHERE status = 'PENDING' AND next_attempt_at <= NOW()
                ORDER BY created_at
                LIMIT %s
                FOR UPDATE SKIP LOCKED
                """,
                (limit,),
            )
            rows = cur.fetchall()
            ids = [r[0] for r in rows]
            if ids:
                # Lease rows for 60s so a concurrent dispatcher does not double-publish.
                cur.execute(
                    "UPDATE management_event_outbox SET next_attempt_at = NOW() + INTERVAL '60 seconds' WHERE id = ANY(%s)",
                    (ids,),
                )
        conn.commit()
    return [(str(r[0]), r[1], int(r[2])) for r in rows]


def _mark(event_id: str, published: bool, attempts: int, error: str | None = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            if published:
                cur.execute(
                    "UPDATE management_event_outbox SET status='PUBLISHED', published_at=NOW(), attempts=%s, last_error=NULL WHERE id=%s",
                    (attempts, event_id),
                )
            else:
                final = attempts >= settings.event_max_attempts
                delay = min(300, 2 ** min(attempts, 8))
                cur.execute(
                    """
                    UPDATE management_event_outbox
                    SET status = %s, attempts = %s, last_error = %s,
                        next_attempt_at = NOW() + make_interval(secs => %s)
                    WHERE id = %s
                    """,
                    ("FAILED" if final else "PENDING", attempts, (error or "")[:500], delay, event_id),
                )
        conn.commit()


class _Publisher:
    def __init__(self) -> None:
        self._conn = None
        self._channel = None

    def _ensure(self):
        import pika

        if self._channel is not None and self._channel.is_open:
            return self._channel
        params = pika.URLParameters(settings.effective_rabbitmq_url)
        params.socket_timeout = 5
        params.blocked_connection_timeout = 5
        params.connection_attempts = 1
        self._conn = pika.BlockingConnection(params)
        self._channel = self._conn.channel()
        self._channel.exchange_declare(exchange=settings.event_exchange, exchange_type="topic", durable=True)
        self._channel.confirm_delivery()
        return self._channel

    def publish(self, envelope: dict) -> None:
        import pika

        channel = self._ensure()
        channel.basic_publish(
            exchange=settings.event_exchange,
            routing_key=envelope["eventType"],
            body=json.dumps(envelope, ensure_ascii=False).encode("utf-8"),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
                message_id=envelope["eventId"],
                type=envelope["eventType"],
            ),
            mandatory=False,
        )

    def close(self) -> None:
        try:
            if self._conn is not None and self._conn.is_open:
                self._conn.close()
        except Exception:
            pass
        self._conn = None
        self._channel = None


def dispatch_once(publisher: _Publisher | None = None) -> int:
    publisher = publisher or _Publisher()
    published = 0
    for event_id, envelope, attempts in _claim_batch():
        if isinstance(envelope, str):
            envelope = json.loads(envelope)
        try:
            publisher.publish(envelope)
            _mark(event_id, True, attempts + 1)
            published += 1
        except Exception as exc:  # RabbitMQ unavailable / nack -> keep PENDING with backoff
            publisher.close()
            logger.warning("Publishing management event %s failed: %s", event_id, exc)
            _mark(event_id, False, attempts + 1, str(exc))
    return published


def _loop() -> None:
    publisher = _Publisher()
    while not _stop.is_set():
        try:
            dispatch_once(publisher)
        except Exception:
            logger.exception("Management event dispatcher iteration failed")
            publisher.close()
        _wake.wait(settings.event_dispatch_interval_seconds)
        _wake.clear()
    publisher.close()


def start_dispatcher() -> bool:
    global _thread
    if not settings.events_enabled or not settings.effective_rabbitmq_url or not settings.database_url:
        logger.warning("Management event dispatcher disabled (events_enabled/RabbitMQ settings/database_url not set)")
        return False
    if _thread and _thread.is_alive():
        return True
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="mgmt-event-dispatcher", daemon=True)
    _thread.start()
    return True


def stop_dispatcher() -> None:
    _stop.set()
    _wake.set()


def outbox_stats() -> dict:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status, COUNT(*) FROM management_event_outbox GROUP BY status")
                return {r[0]: int(r[1]) for r in cur.fetchall()}
    except Exception:
        return {}
