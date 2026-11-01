from uuid import UUID

from psycopg.types.json import Jsonb

from app.database import get_connection


def create_notification(event: dict, user_id: str) -> dict | None:
    data = event.get("data") or {}
    title, message, category = notification_content(
        event.get("event_type", ""),
        data,
        user_id,
    )

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO notifications (
                    event_id,
                    user_id,
                    event_type,
                    title,
                    message,
                    category,
                    data
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id, user_id) DO NOTHING
                RETURNING id, created_at
                """,
                (
                    event["event_id"],
                    UUID(user_id),
                    event["event_type"],
                    title,
                    message,
                    category,
                    Jsonb(data),
                ),
            )
            row = cur.fetchone()

    if row is None:
        return None
    notification = {
        "id": str(row[0]),
        "event_id": event["event_id"],
        "user_id": user_id,
        "event_type": event["event_type"],
        "title": title,
        "message": message,
        "category": category,
        "data": data,
        "created_at": row[1].isoformat(),
        "read_at": None,
    }
    return notification


def notification_content(
    event_type: str,
    data: dict,
    user_id: str,
) -> tuple[str, str, str]:
    if event_type == "management.technician_assigned":
        farm_name = data.get("farm_name") or "nhà yến"
        if str(data.get("technician_id")) == user_id:
            return (
                "Phân công nhà yến mới",
                f"Bạn được phân công phụ trách {farm_name}.",
                "info",
            )
        technician_name = data.get("technician_name") or "Kỹ thuật viên"
        return (
            "Cập nhật kỹ thuật viên",
            f"{technician_name} được phân công phụ trách {farm_name}.",
            "info",
        )

    if event_type == "device.command.acknowledged":
        status_value = str(data.get("status", "UNKNOWN")).upper()
        succeeded = status_value == "SUCCESS"
        title = "Thiết bị đã thực hiện lệnh" if succeeded else "Lệnh thiết bị thất bại"
        node_id = data.get("node_id") or "Thiết bị"
        action = data.get("action") or "lệnh điều khiển"
        return (
            title,
            f"{node_id}: {action} — {status_value}.",
            "info" if succeeded else "danger",
        )

    raise ValueError(f"Unsupported notification event type: {event_type}")


def list_notifications(
    user_id: str,
    limit: int,
    unread_only: bool,
) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, event_id, event_type, title, message,
                       category, data, created_at, read_at
                FROM notifications
                WHERE user_id = %s
                  AND (%s = FALSE OR read_at IS NULL)
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (UUID(user_id), unread_only, limit),
            )
            rows = cur.fetchall()

    return [
        {
            "id": str(row[0]),
            "event_id": str(row[1]),
            "event_type": row[2],
            "title": row[3],
            "message": row[4],
            "category": row[5],
            "data": row[6],
            "created_at": row[7].isoformat(),
            "read_at": row[8].isoformat() if row[8] else None,
        }
        for row in rows
    ]


def mark_notification_read(notification_id: str, user_id: str) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE notifications
                SET read_at = COALESCE(read_at, NOW())
                WHERE id = %s AND user_id = %s
                RETURNING id
                """,
                (UUID(notification_id), UUID(user_id)),
            )
            return cur.fetchone() is not None


def mark_all_notifications_read(user_id: str) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE notifications
                SET read_at = NOW()
                WHERE user_id = %s AND read_at IS NULL
                """,
                (UUID(user_id),),
            )
            return cur.rowcount


def save_push_subscription(
    user_id: str,
    endpoint: str,
    p256dh: str,
    auth: str,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO notification_push_subscriptions (
                    user_id, endpoint, p256dh, auth
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, endpoint)
                DO UPDATE SET
                    p256dh = EXCLUDED.p256dh,
                    auth = EXCLUDED.auth,
                    updated_at = NOW()
                """,
                (UUID(user_id), endpoint, p256dh, auth),
            )


def delete_push_subscription(user_id: str, endpoint: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM notification_push_subscriptions
                WHERE user_id = %s AND endpoint = %s
                """,
                (UUID(user_id), endpoint),
            )


def get_user_email(user_id: str) -> tuple[str, str] | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT email, full_name FROM users WHERE id = %s",
                (UUID(user_id),),
            )
            row = cur.fetchone()

    return (row[0], row[1]) if row else None


def get_push_subscriptions(user_id: str) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT endpoint, p256dh, auth
                FROM notification_push_subscriptions
                WHERE user_id = %s
                """,
                (UUID(user_id),),
            )
            rows = cur.fetchall()

    return [
        {"endpoint": row[0], "keys": {"p256dh": row[1], "auth": row[2]}}
        for row in rows
    ]
