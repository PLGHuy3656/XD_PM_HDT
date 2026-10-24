
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from app.database import get_connection


def create_command(
    *,
    command_id: str,
    device_id: UUID,
    action: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Create a pending command record."""
    query = """
        INSERT INTO public.environment_control_commands (
            command_id,
            device_id,
            action,
            payload,
            status
        )
        VALUES (%s, %s, %s, %s, 'PENDING')
        RETURNING command_id, device_id, action, status, created_at
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (command_id, device_id, action, Jsonb(payload)),
            )
            row = cur.fetchone()

    return {
        "command_id": row[0],
        "device_id": str(row[1]),
        "action": row[2],
        "status": row[3],
        "created_at": row[4].isoformat(),
    }


def mark_command_sent(command_id: str) -> bool:
    """Mark a pending command as sent."""
    query = """
        UPDATE public.environment_control_commands
        SET sent_at = NOW()
        WHERE command_id = %s
          AND status = 'PENDING'
          AND sent_at IS NULL
        RETURNING command_id
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (command_id,))
            return cur.fetchone() is not None

def get_active_device_id_by_node_id(node_id: str) -> UUID | None:
    """Return the UUID of an active device matching its MQTT node ID."""
    query = """
        SELECT id
        FROM public.devices
        WHERE node_id = %s
          AND is_active = TRUE
        LIMIT 1
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (node_id,))
            row = cur.fetchone()

    return row[0] if row else None


def get_active_device_node_id(device_id: UUID) -> str | None:
    """Return the MQTT node ID of an active device."""
    query = """
        SELECT node_id
        FROM public.devices
        WHERE id = %s
          AND is_active = TRUE
        LIMIT 1
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (device_id,))
            row = cur.fetchone()

    return row[0] if row else None


def record_command_ack(
    *,
    command_id: str,
    expected_device_id: UUID,
    status: str,
    response: dict[str, Any],
) -> bool:
    """Record an ACK only for the expected device and a pending command."""
    if status not in {"SUCCESS", "FAILED", "ERROR"}:
        raise ValueError("Unsupported ACK status")

    final_status = "SUCCESS" if status == "SUCCESS" else "FAILED"

    query = """
        UPDATE public.environment_control_commands
        SET status = %s,
            response = %s,
            acknowledged_at = NOW()
        WHERE command_id = %s
          AND device_id = %s
          AND status = 'PENDING'
        RETURNING command_id
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    final_status,
                    Jsonb(response),
                    command_id,
                    expected_device_id,
                ),
            )
            return cur.fetchone() is not None


def mark_command_failed(command_id: str, reason: str) -> bool:
    """Mark a pending command as failed when publishing fails."""
    query = """
        UPDATE public.environment_control_commands
        SET status = 'FAILED',
            response = %s,
            acknowledged_at = NOW()
        WHERE command_id = %s
          AND status = 'PENDING'
        RETURNING command_id
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    Jsonb({"error": reason}),
                    command_id,
                ),
            )
            return cur.fetchone() is not None
