
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.database import get_connection


router = APIRouter(
    prefix="/api/devices",
    tags=["Environmental Control"],
)


@router.get("/{device_id}/control")
def get_control_state(device_id: UUID):
    query = """
        SELECT
            d.id,
            d.node_id,
            c.mode,
            c.target_temp,
            c.target_hum,
            c.temp_deadband,
            c.hum_deadband,
            c.co2_threshold,
            c.updated_at
        FROM public.devices AS d
        LEFT JOIN public.environment_control_configs AS c
            ON c.device_id = d.id
        WHERE d.id = %s
          AND d.is_active = TRUE
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (device_id,))
            row = cur.fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Active device not found",
        )

    return {
        "deviceId": str(row[0]),
        "nodeId": row[1],
        "config": (
            {
                "mode": row[2],
                "targetTemp": row[3],
                "targetHum": row[4],
                "tempDeadband": row[5],
                "humDeadband": row[6],
                "co2Threshold": row[7],
                "updatedAt": row[8].isoformat() if row[8] else None,
            }
            if row[2] is not None
            else None
        ),
    }


@router.get("/{device_id}/control/commands")
def get_control_commands(
    device_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
):
    query = """
        SELECT
            command_id,
            action,
            status,
            payload,
            response,
            created_at,
            sent_at,
            acknowledged_at
        FROM public.environment_control_commands
        WHERE device_id = %s
        ORDER BY created_at DESC
        LIMIT %s
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM public.devices WHERE id = %s AND is_active = TRUE",
                (device_id,),
            )
            if cur.fetchone() is None:
                raise HTTPException(
                    status_code=404,
                    detail="Active device not found",
                )

            cur.execute(query, (device_id, limit))
            rows = cur.fetchall()

    return {
        "deviceId": str(device_id),
        "items": [
            {
                "commandId": row[0],
                "action": row[1],
                "status": row[2],
                "payload": row[3],
                "response": row[4],
                "createdAt": row[5].isoformat(),
                "sentAt": row[6].isoformat() if row[6] else None,
                "acknowledgedAt": (
                    row[7].isoformat() if row[7] else None
                ),
            }
            for row in rows
        ],
    }
