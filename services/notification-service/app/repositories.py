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
            if row is not None:
                cur.execute(
                    """
                    INSERT INTO notification_deliveries (notification_id, channel)
                    VALUES (%s, 'email'), (%s, 'web_push'), (%s, 'fcm')
                    ON CONFLICT (notification_id, channel) DO NOTHING
                    """,
                    (row[0], row[0], row[0]),
                )

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
        action = data.get("action") or data.get("command_id") or "lệnh điều khiển"
        return (
            title,
            f"{node_id}: {action} — {status_value}.",
            "info" if succeeded else "danger",
        )

    if event_type == "environment.threshold_exceeded":
        metric = data.get("metric") or "Thông số môi trường"
        value = data.get("value")
        unit = data.get("unit") or ""
        threshold = data.get("threshold")
        farm_name = data.get("farm_name") or "nhà yến"
        location = data.get("zone_name") or data.get("node_id")
        location_text = f" tại {location}" if location else ""
        value_text = f" ({value}{unit})" if value is not None else ""
        threshold_text = (
            f"; ngưỡng cho phép {threshold}{unit}"
            if threshold is not None
            else ""
        )
        return (
            "Thông số môi trường vượt ngưỡng",
            f"{metric}{value_text}{threshold_text} tại {farm_name}{location_text}.",
            "danger",
        )

    if event_type in {
        "device.offline",
        "device.sensor.timeout",
        "device.actuator.failed",
    }:
        node_id = data.get("node_id") or "Thiết bị"
        farm_name = data.get("farm_name") or "nhà yến"
        zone_name = data.get("zone_name")
        location = f", {zone_name}" if zone_name else ""
        if event_type == "device.offline":
            return (
                "Thiết bị mất kết nối",
                f"{node_id} tại {farm_name}{location} đã mất kết nối.",
                "danger",
            )
        if event_type == "device.sensor.timeout":
            sensor = data.get("sensor_name") or data.get("sensor_type")
            sensor_text = f" {sensor}" if sensor else ""
            return (
                "Cảm biến không phản hồi",
                f"Cảm biến{sensor_text} trên {node_id} tại {farm_name}"
                f"{location} không phản hồi.",
                "danger",
            )
        return (
            "Thiết bị chấp hành gặp lỗi",
            f"{data.get('actuator_name') or node_id} tại {farm_name}{location} "
            f"gặp lỗi: {data.get('error') or data.get('message') or 'cần kiểm tra'}.",
            "danger",
        )

    if event_type == "ai.threat.detected":
        threat = data.get("threat_type") or data.get("label") or "mối đe dọa"
        farm_name = data.get("farm_name") or "nhà yến"
        confidence = data.get("confidence")
        confidence_text = (
            f" (độ tin cậy {float(confidence):.0%})"
            if isinstance(confidence, (int, float))
            and 0 <= confidence <= 1
            else ""
        )
        return (
            "AI phát hiện mối đe dọa",
            f"Phát hiện {threat} tại {farm_name}{confidence_text}.",
            "danger",
        )

    if event_type == "management.work_request.created":
        request_id = data.get("work_request_id") or ""
        farm_name = data.get("farm_name") or "nhà yến"
        priority = data.get("priority")
        priority_text = f", mức ưu tiên {priority}" if priority else ""
        return (
            "Có yêu cầu công việc mới",
            f"Yêu cầu {request_id} tại {farm_name}{priority_text} cần được xử lý.",
            "warning",
        )

    if event_type == "management.work_request.status_changed":
        request_id = data.get("work_request_id") or ""
        new_status = data.get("status") or "được cập nhật"
        return (
            "Cập nhật yêu cầu công việc",
            f"Yêu cầu {request_id} đã chuyển sang trạng thái {new_status}.",
            "info",
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


def save_fcm_token(user_id: str, token: str, platform: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO notification_fcm_tokens (user_id, token, platform)
                VALUES (%s, %s, %s)
                ON CONFLICT (token)
                DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    platform = EXCLUDED.platform,
                    updated_at = NOW()
                """,
                (UUID(user_id), token, platform),
            )


def delete_fcm_token(user_id: str, token: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM notification_fcm_tokens
                WHERE user_id = %s AND token = %s
                """,
                (UUID(user_id), token),
            )


def get_fcm_tokens(user_id: str) -> list[str]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT token
                FROM notification_fcm_tokens
                WHERE user_id = %s
                """,
                (UUID(user_id),),
            )
            rows = cur.fetchall()
    return [row[0] for row in rows]


def claim_pending_delivery() -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE notification_deliveries
                SET status = 'failed',
                    last_error = 'Delivery worker lease expired after maximum attempts',
                    updated_at = NOW()
                WHERE status = 'processing'
                  AND attempts >= 5
                  AND updated_at < NOW() - INTERVAL '5 minutes'
                """
            )
            cur.execute(
                """
                WITH due AS (
                    SELECT id
                    FROM notification_deliveries
                    WHERE (
                        status IN ('pending', 'failed')
                        AND attempts < 5
                        AND next_attempt_at <= NOW()
                    ) OR (
                        status = 'processing'
                        AND attempts < 5
                        AND updated_at < NOW() - INTERVAL '5 minutes'
                    )
                    ORDER BY next_attempt_at, created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE notification_deliveries AS deliveries
                SET status = 'processing',
                    attempts = deliveries.attempts + 1,
                    updated_at = NOW()
                FROM due, notifications AS n
                WHERE deliveries.id = due.id
                  AND n.id = deliveries.notification_id
                RETURNING deliveries.id,
                          deliveries.channel,
                          deliveries.attempts,
                          n.id,
                          n.user_id,
                          n.event_type,
                          n.title,
                          n.message,
                          n.category,
                          n.data,
                          n.created_at,
                          n.read_at
                """
            )
            row = cur.fetchone()

    if row is None:
        return None
    return {
        "delivery_id": str(row[0]),
        "channel": row[1],
        "attempts": row[2],
        "notification": {
            "id": str(row[3]),
            "user_id": str(row[4]),
            "event_type": row[5],
            "title": row[6],
            "message": row[7],
            "category": row[8],
            "data": row[9],
            "created_at": row[10].isoformat(),
            "read_at": row[11].isoformat() if row[11] else None,
        },
    }


def finish_delivery(
    delivery_id: str,
    *,
    status: str,
    error: str | None = None,
    retry_delay_seconds: int = 0,
) -> None:
    if status not in {"delivered", "skipped", "failed"}:
        raise ValueError(f"Unsupported delivery status: {status}")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE notification_deliveries
                SET status = %s,
                    last_error = %s,
                    next_attempt_at = NOW() + (%s * INTERVAL '1 second'),
                    delivered_at = CASE
                        WHEN %s = 'delivered' THEN NOW()
                        ELSE delivered_at
                    END,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (status, error, retry_delay_seconds, status, UUID(delivery_id)),
            )
