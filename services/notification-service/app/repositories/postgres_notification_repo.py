"""PostgreSQL durable repository for Notification delivery records (CP8.3)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

import psycopg
from psycopg.types.json import Jsonb

from app.database import get_connection
from app.domain.enums import NotificationChannel, NotificationDeliveryStatus
from app.ports.notification_repository import NotificationRepository
from app.schemas.canonical import Notification

logger = logging.getLogger("notification_service.repositories.notification")


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _row_to_notification(row: tuple[Any, ...]) -> Notification:
    raw_data = row[7] if row[7] is not None else {}
    str_data = {str(k): str(v) for k, v in raw_data.items() if v is not None}
    return Notification(
        notification_id=row[0],
        alert_id=row[1],
        user_id=row[2],
        channel=NotificationChannel(row[3]),
        delivery_status=NotificationDeliveryStatus(row[4]),
        title=row[5],
        body=row[6],
        data=str_data,
        failure_reason=row[8],
        created_at=_ensure_utc(row[9]),
        sent_at=_ensure_utc(row[10]),
        read_at=_ensure_utc(row[11]),
    )


_SELECT_COLUMNS = """
    notification_id,
    alert_id,
    user_id,
    channel,
    delivery_status,
    title,
    body,
    data,
    failure_reason,
    created_at,
    sent_at,
    read_at
"""


class PostgreSQLNotificationRepository(NotificationRepository):
    """Durable PostgreSQL implementation of NotificationRepository backed by `notification_db.notifications`."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        self._database_url = database_url

    def _connect(self) -> psycopg.Connection:
        return get_connection(self._database_url)

    def save(self, notification: Notification) -> Notification:
        created_at = _ensure_utc(notification.created_at) or datetime.now(timezone.utc)
        sent_at = _ensure_utc(notification.sent_at)
        read_at = _ensure_utc(notification.read_at)
        data_json = Jsonb(notification.data or {})

        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        INSERT INTO notifications (
                            notification_id,
                            alert_id,
                            user_id,
                            channel,
                            delivery_status,
                            title,
                            body,
                            data,
                            failure_reason,
                            created_at,
                            sent_at,
                            read_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (notification_id) DO UPDATE SET
                            alert_id = EXCLUDED.alert_id,
                            user_id = EXCLUDED.user_id,
                            channel = EXCLUDED.channel,
                            delivery_status = EXCLUDED.delivery_status,
                            title = EXCLUDED.title,
                            body = EXCLUDED.body,
                            data = EXCLUDED.data,
                            failure_reason = EXCLUDED.failure_reason,
                            sent_at = EXCLUDED.sent_at,
                            read_at = EXCLUDED.read_at
                        RETURNING {_SELECT_COLUMNS}
                        """,
                        (
                            notification.notification_id,
                            notification.alert_id,
                            notification.user_id,
                            notification.channel.value,
                            notification.delivery_status.value,
                            notification.title,
                            notification.body,
                            data_json,
                            notification.failure_reason,
                            created_at,
                            sent_at,
                            read_at,
                        ),
                    )
                    row = cur.fetchone()
                conn.commit()
            assert row is not None
            return _row_to_notification(row)
        except Exception as exc:
            logger.error(
                "[NOTIFICATION DELIVERY PERSISTENCE FAILED] Failed to save Notification notificationId='%s' userId='%s': %s",
                notification.notification_id,
                notification.user_id,
                exc,
            )
            raise

    def get_by_id(self, notification_id: str) -> Optional[Notification]:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT {_SELECT_COLUMNS} FROM notifications WHERE notification_id = %s",
                        (notification_id,),
                    )
                    row = cur.fetchone()
                    return _row_to_notification(row) if row is not None else None
        except Exception as exc:
            logger.error(
                "[NOTIFICATION QUERY FAILED] Failed to query Notification notificationId='%s': %s",
                notification_id,
                exc,
            )
            raise

    def list_by_user(
        self,
        user_id: str,
        is_read: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Notification]:
        clauses = ["user_id = %s"]
        params: list[Any] = [user_id]

        if is_read is True:
            clauses.append("read_at IS NOT NULL")
        elif is_read is False:
            clauses.append("read_at IS NULL")

        where_sql = " AND ".join(clauses)
        params.extend([limit, offset])

        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT {_SELECT_COLUMNS}
                        FROM notifications
                        WHERE {where_sql}
                        ORDER BY created_at DESC, notification_id DESC
                        LIMIT %s OFFSET %s
                        """,
                        tuple(params),
                    )
                    rows = cur.fetchall()
                    return [_row_to_notification(r) for r in rows]
        except Exception as exc:
            logger.error(
                "[NOTIFICATION LIST FAILED] Failed to list Notifications for userId='%s': %s",
                user_id,
                exc,
            )
            raise

    def list_by_alert(
        self,
        alert_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Notification]:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT {_SELECT_COLUMNS}
                        FROM notifications
                        WHERE alert_id = %s
                        ORDER BY created_at DESC, notification_id DESC
                        LIMIT %s OFFSET %s
                        """,
                        (alert_id, limit, offset),
                    )
                    rows = cur.fetchall()
                    return [_row_to_notification(r) for r in rows]
        except Exception as exc:
            logger.error(
                "[NOTIFICATION LIST BY ALERT FAILED] Failed to list Notifications for alertId='%s': %s",
                alert_id,
                exc,
            )
            raise

    def list_recent(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Notification]:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT {_SELECT_COLUMNS}
                        FROM notifications
                        ORDER BY created_at DESC, notification_id DESC
                        LIMIT %s OFFSET %s
                        """,
                        (limit, offset),
                    )
                    rows = cur.fetchall()
                    return [_row_to_notification(r) for r in rows]
        except Exception as exc:
            logger.error("[NOTIFICATION LIST RECENT FAILED] Failed to list recent Notifications: %s", exc)
            raise

    def count_by_user(
        self,
        user_id: str,
        is_read: Optional[bool] = None,
    ) -> int:
        clauses = ["user_id = %s"]
        params: list[Any] = [user_id]

        if is_read is True:
            clauses.append("read_at IS NOT NULL")
        elif is_read is False:
            clauses.append("read_at IS NULL")

        where_sql = " AND ".join(clauses)

        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT COUNT(*) FROM notifications WHERE {where_sql}",
                        tuple(params),
                    )
                    row = cur.fetchone()
                    return int(row[0]) if row else 0
        except Exception as exc:
            logger.error(
                "[NOTIFICATION COUNT FAILED] Failed to count Notifications for userId='%s': %s",
                user_id,
                exc,
            )
            raise

    def mark_as_read(
        self,
        notification_id: str,
        user_id: str,
        read_at: Optional[datetime] = None,
    ) -> Optional[Notification]:
        now = _ensure_utc(read_at) or datetime.now(timezone.utc)
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        UPDATE notifications
                        SET read_at = COALESCE(read_at, %s)
                        WHERE notification_id = %s
                          AND user_id = %s
                        RETURNING {_SELECT_COLUMNS}
                        """,
                        (now, notification_id, user_id),
                    )
                    row = cur.fetchone()
                conn.commit()
            return _row_to_notification(row) if row is not None else None
        except Exception as exc:
            logger.error(
                "[NOTIFICATION MARK READ FAILED] Failed to mark Notification notificationId='%s' read: %s",
                notification_id,
                exc,
            )
            raise

    def mark_all_as_read(
        self,
        user_id: str,
        read_at: Optional[datetime] = None,
    ) -> int:
        now = _ensure_utc(read_at) or datetime.now(timezone.utc)
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE notifications
                        SET read_at = %s
                        WHERE user_id = %s
                          AND read_at IS NULL
                        """,
                        (now, user_id),
                    )
                    modified = cur.rowcount
                conn.commit()
            return int(modified or 0)
        except Exception as exc:
            logger.error(
                "[NOTIFICATION MARK ALL READ FAILED] Failed to mark all Notifications read for userId='%s': %s",
                user_id,
                exc,
            )
            raise

    def update_delivery_status(
        self,
        notification_id: str,
        status: NotificationDeliveryStatus,
        failure_reason: Optional[str] = None,
    ) -> Optional[Notification]:
        now = datetime.now(timezone.utc)
        sent_at_val = now if status == NotificationDeliveryStatus.SENT else None
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        UPDATE notifications
                        SET delivery_status = %s,
                            failure_reason = COALESCE(%s, failure_reason),
                            sent_at = COALESCE(sent_at, %s)
                        WHERE notification_id = %s
                        RETURNING {_SELECT_COLUMNS}
                        """,
                        (status.value, failure_reason, sent_at_val, notification_id),
                    )
                    row = cur.fetchone()
                conn.commit()
            return _row_to_notification(row) if row is not None else None
        except Exception as exc:
            logger.error(
                "[NOTIFICATION DELIVERY STATUS UPDATE FAILED] Failed to update status for notificationId='%s': %s",
                notification_id,
                exc,
            )
            raise


__all__ = ["PostgreSQLNotificationRepository"]
