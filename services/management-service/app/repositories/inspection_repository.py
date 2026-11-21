"""INT03-R1: Inspection Request persistence (management_db is the source of truth).

State machine:  NEW --accept--> ACCEPTED --start--> IN_PROGRESS --complete--> COMPLETED
                NEW|ACCEPTED --cancel (owner)--> CANCELLED
Every transition is a single conditional UPDATE (WHERE status = expected [AND assignee = actor]);
0 rows => conflict, so concurrent transitions cannot both succeed. History is written in the
same transaction.
"""
from __future__ import annotations

import secrets
import uuid

from app.database import get_connection

_SELECT = """
    SELECT ir.id, ir.request_code, ir.farm_id, f.name, ir.zone_id, z.name, ir.device_id,
           COALESCE(d.name, d.node_id), ir.title, ir.description, ir.priority, ir.status,
           ir.requested_by, ru.full_name, ir.assigned_technician_id, t.full_name, ir.result_note,
           ir.created_at, ir.updated_at, ir.accepted_at, ir.started_at, ir.completed_at, ir.cancelled_at
    FROM inspection_requests ir
    JOIN farms f ON f.id = ir.farm_id
    LEFT JOIN zones z ON z.id = ir.zone_id
    LEFT JOIN devices d ON d.id = ir.device_id
    LEFT JOIN users ru ON ru.id = ir.requested_by
    LEFT JOIN technicians t ON t.id = ir.assigned_technician_id
"""


def _iso(v):
    return v.isoformat() if v else None


def _row(r) -> dict:
    return {
        "id": str(r[0]), "request_code": r[1], "farm_id": str(r[2]), "farm_name": r[3],
        "zone_id": str(r[4]) if r[4] else None, "zone_name": r[5],
        "device_id": str(r[6]) if r[6] else None, "device_name": r[7],
        "title": r[8], "description": r[9], "priority": r[10], "status": r[11],
        "requested_by": str(r[12]), "requested_by_name": r[13],
        "assigned_technician_id": str(r[14]) if r[14] else None, "assigned_technician_name": r[15],
        "result_note": r[16], "created_at": _iso(r[17]), "updated_at": _iso(r[18]),
        "accepted_at": _iso(r[19]), "started_at": _iso(r[20]), "completed_at": _iso(r[21]),
        "cancelled_at": _iso(r[22]),
    }


def is_uuid(value: str | None) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


class InspectionRepository:
    # ------------------------------------------------------------ reads
    def get(self, request_id: str, with_history: bool = False) -> dict | None:
        if not is_uuid(request_id):
            return None
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(_SELECT + " WHERE ir.id = %s", (request_id,))
                row = cur.fetchone()
                if not row:
                    return None
                item = _row(row)
                if with_history:
                    cur.execute(
                        """
                        SELECT h.from_status, h.to_status, h.action, h.actor_id, u.full_name, h.note, h.created_at
                        FROM inspection_request_history h LEFT JOIN users u ON u.id = h.actor_id
                        WHERE h.request_id = %s ORDER BY h.created_at, h.id
                        """,
                        (request_id,),
                    )
                    item["history"] = [
                        {"from_status": h[0], "to_status": h[1], "action": h[2],
                         "actor_id": str(h[3]) if h[3] else None, "actor_name": h[4],
                         "note": h[5], "created_at": _iso(h[6])}
                        for h in cur.fetchall()
                    ]
        return item

    def list_for_user(self, user: dict, status: str | None = None, farm_id: str | None = None,
                      unassigned: bool = False, limit: int = 100) -> list[dict]:
        roles = user.get("roles") or []
        uid = str(user["id"])
        where, params = [], []
        if "ADMIN" in roles:
            pass
        elif "FARM_OWNER" in roles and "TECHNICIAN" not in roles:
            where.append("f.owner_id = %s"); params.append(uid)
        elif "TECHNICIAN" in roles:
            where.append(
                "EXISTS (SELECT 1 FROM technician_assignments ta WHERE ta.farm_id = ir.farm_id "
                "AND ta.technician_id = %s AND ta.is_active = TRUE)"
            ); params.append(uid)
        else:
            return []
        if status:
            where.append("ir.status = %s"); params.append(status)
        if farm_id:
            where.append("ir.farm_id = %s"); params.append(farm_id)
        if unassigned:
            where.append("ir.assigned_technician_id IS NULL")
        sql = _SELECT + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY ir.created_at DESC LIMIT %s"
        params.append(max(1, min(int(limit), 200)))
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return [_row(r) for r in cur.fetchall()]

    def pick_default_technician(self, farm_id: str) -> str | None:
        """Primary active technician, else the only active technician, else None (Admin queue)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT technician_id, is_primary FROM technician_assignments "
                    "WHERE farm_id = %s AND is_active = TRUE ORDER BY is_primary DESC, assigned_at ASC",
                    (farm_id,),
                )
                rows = cur.fetchall()
        primaries = [r for r in rows if r[1]]
        if len(primaries) == 1:
            return str(primaries[0][0])
        if len(rows) == 1:
            return str(rows[0][0])
        return None

    # ------------------------------------------------------------ writes
    def create(self, *, farm_id: str, title: str, description: str | None, priority: str,
               zone_id: str | None, device_id: str | None, requested_by: str,
               assigned_technician_id: str | None) -> dict:
        new_id = str(uuid.uuid4())
        with get_connection() as conn:
            with conn.cursor() as cur:
                code = f"IR-{secrets.token_hex(4).upper()}"
                cur.execute(
                    """
                    INSERT INTO inspection_requests (id, request_code, farm_id, zone_id, device_id, title,
                        description, priority, status, requested_by, assigned_technician_id, updated_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'NEW', %s, %s, %s)
                    """,
                    (new_id, code, farm_id, zone_id, device_id, title.strip(), description,
                     priority, requested_by, assigned_technician_id, requested_by),
                )
                cur.execute(
                    "INSERT INTO inspection_request_history (request_id, from_status, to_status, action, actor_id, note) "
                    "VALUES (%s, NULL, 'NEW', 'CREATE', %s, %s)",
                    (new_id, requested_by,
                     "Tự động liên kết kỹ thuật viên phụ trách" if assigned_technician_id else "Chờ Admin phân công"),
                )
            conn.commit()
        return self.get(new_id, with_history=True)

    def _transition(self, request_id: str, *, expected: tuple[str, ...], to_status: str, action: str,
                    actor_id: str, set_sql: str = "", set_params: tuple = (), assignee: str | None = None,
                    note: str | None = None) -> dict | None:
        """Atomic conditional transition. Returns the updated row or None on conflict."""
        cond = "id = %s AND status = ANY(%s)"
        params: list = [request_id, list(expected)]
        if assignee is not None:
            cond += " AND assigned_technician_id = %s"
            params.append(assignee)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    WITH prev AS (SELECT status FROM inspection_requests WHERE {cond} FOR UPDATE)
                    UPDATE inspection_requests ir
                    SET status = %s, updated_at = NOW(), updated_by = %s {set_sql}
                    FROM prev WHERE ir.id = %s
                    RETURNING prev.status
                    """,
                    (*params, to_status, actor_id, *set_params, request_id),
                )
                row = cur.fetchone()
                if not row:
                    conn.rollback()
                    return None
                cur.execute(
                    "INSERT INTO inspection_request_history (request_id, from_status, to_status, action, actor_id, note) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (request_id, row[0], to_status, action, actor_id, note),
                )
            conn.commit()
        return self.get(request_id, with_history=True)

    def accept(self, request_id: str, technician_id: str):
        return self._transition(request_id, expected=("NEW",), to_status="ACCEPTED", action="ACCEPT",
                                actor_id=technician_id, assignee=technician_id,
                                set_sql=", accepted_at = NOW()")

    def start(self, request_id: str, technician_id: str):
        return self._transition(request_id, expected=("ACCEPTED",), to_status="IN_PROGRESS", action="START",
                                actor_id=technician_id, assignee=technician_id,
                                set_sql=", started_at = NOW()")

    def complete(self, request_id: str, technician_id: str, result_note: str):
        return self._transition(request_id, expected=("IN_PROGRESS",), to_status="COMPLETED", action="COMPLETE",
                                actor_id=technician_id, assignee=technician_id,
                                set_sql=", completed_at = NOW(), result_note = %s",
                                set_params=(result_note.strip(),), note=result_note.strip())

    def cancel(self, request_id: str, owner_id: str, note: str | None):
        return self._transition(request_id, expected=("NEW", "ACCEPTED"), to_status="CANCELLED", action="CANCEL",
                                actor_id=owner_id, set_sql=", cancelled_at = NOW()", note=note)

    def assign(self, request_id: str, technician_id: str, admin_id: str):
        """Admin assigns/reassigns while the request is still NEW (status unchanged)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE inspection_requests SET assigned_technician_id = %s, updated_at = NOW(), updated_by = %s
                    WHERE id = %s AND status = 'NEW'
                      AND assigned_technician_id IS DISTINCT FROM %s
                    RETURNING id
                    """,
                    (technician_id, admin_id, request_id, technician_id),
                )
                if not cur.fetchone():
                    conn.rollback()
                    return None
                cur.execute(
                    "INSERT INTO inspection_request_history (request_id, from_status, to_status, action, actor_id, note) "
                    "VALUES (%s, 'NEW', 'NEW', 'ASSIGN', %s, %s)",
                    (request_id, admin_id, f"Phân công kỹ thuật viên {technician_id}"),
                )
            conn.commit()
        return self.get(request_id, with_history=True)

    def requeue_for_unassigned_technician(self, farm_id: str, technician_id: str, actor_id: str) -> list[str]:
        """Assignment revoked: that technician's open requests on the farm return to NEW/unassigned."""
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        WITH moved AS (
                            SELECT id, status FROM inspection_requests
                            WHERE farm_id::text = %s AND assigned_technician_id = %s
                              AND status IN ('NEW', 'ACCEPTED', 'IN_PROGRESS')
                            FOR UPDATE
                        )
                        UPDATE inspection_requests ir
                        SET status = 'NEW', assigned_technician_id = NULL, accepted_at = NULL,
                            started_at = NULL, updated_at = NOW(), updated_by = %s
                        FROM moved WHERE ir.id = moved.id
                        RETURNING ir.id, moved.status
                        """,
                        (farm_id, technician_id, actor_id),
                    )
                    moved = cur.fetchall()
                    for rid, prev in moved:
                        cur.execute(
                            "INSERT INTO inspection_request_history (request_id, from_status, to_status, action, actor_id, note) "
                            "VALUES (%s, %s, 'NEW', 'REQUEUE', %s, %s)",
                            (rid, prev, actor_id, "Kỹ thuật viên bị thu hồi phân công; chờ Admin phân công lại"),
                        )
                conn.commit()
        except Exception:
            # inspection tables may be absent if the additive migration failed; never block unassign
            import logging
            logging.getLogger(__name__).exception("Requeue of inspection requests failed")
            return []
        ids = [str(r[0]) for r in moved]
        if ids:
            from app import inspection_events
            for rid in ids:
                inspection_events.requeued(rid, actor_id)
        return ids


inspection_repository = InspectionRepository()
