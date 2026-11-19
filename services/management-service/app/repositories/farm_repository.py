from app.database import get_connection


class FarmRepository:
    def list_farms(self, current_user: dict | None = None):
        if not current_user or not isinstance(current_user, dict) or not current_user.get("id"):
            return []

        roles = current_user.get("roles") or []
        user_id = str(current_user["id"])

        if "ADMIN" in roles:
            where_clause = ""
            params = ()
        else:
            conditions = []
            params_list = []

            if "FARM_OWNER" in roles:
                conditions.append("f.owner_id IS NOT NULL AND f.owner_id::text = %s")
                params_list.append(user_id)

            if "TECHNICIAN" in roles:
                conditions.append(
                    "f.id IN (SELECT ta.farm_id FROM technician_assignments ta WHERE ta.technician_id::text = %s AND ta.is_active = TRUE)"
                )
                params_list.append(user_id)

            if not conditions:
                return []

            where_clause = f"WHERE ({' OR '.join(conditions)})"
            params = tuple(params_list)

        query = f"""
            SELECT
                f.id,
                f.farm_code,
                f.name,
                f.address,
                f.status,
                f.approval_status,
                f.rejection_reason,
                COUNT(DISTINCT z.id) AS zone_count,
                COUNT(DISTINCT d.id) AS device_count
            FROM farms f
            LEFT JOIN zones z
                ON z.farm_id = f.id
            LEFT JOIN devices d
                ON d.farm_id = f.id
               AND d.is_active = TRUE
            {where_clause}
            GROUP BY
                f.id,
                f.farm_code,
                f.name,
                f.address,
                f.status,
                f.approval_status,
                f.rejection_reason
            ORDER BY f.name
        """

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()

        return [
            {
                "farm_id": str(row[0]),
                "farm_code": row[1],
                "farm_name": row[2],
                "address": row[3],
                "status": row[4] or "ACTIVE",
                "approval_status": row[5] or "APPROVED",
                "rejection_reason": row[6],
                "zone_count": row[7],
                "device_count": row[8],
            }
            for row in rows
        ]

    def get_farm_by_id(self, farm_id: str):
        if not farm_id or not str(farm_id).strip():
            return None

        import uuid
        farm_id_str = str(farm_id).strip()
        is_uuid = False
        try:
            uuid.UUID(farm_id_str)
            is_uuid = True
        except (ValueError, AttributeError, TypeError):
            is_uuid = False

        with get_connection() as conn:
            with conn.cursor() as cur:
                where_clause = "WHERE f.id = %s OR f.farm_code = %s" if is_uuid else "WHERE f.farm_code = %s"
                params = (farm_id_str, farm_id_str) if is_uuid else (farm_id_str,)
                cur.execute(
                    f"""
                    SELECT
                        f.id,
                        f.farm_code,
                        f.name,
                        f.address,
                        f.status,
                        f.approval_status,
                        f.approved_by,
                        f.approved_at,
                        f.rejection_reason,
                        f.created_at,
                        COUNT(DISTINCT z.id) AS zone_count,
                        COUNT(DISTINCT d.id) AS device_count,
                        t.id AS technician_id,
                        t.full_name AS technician_name,
                        u.full_name AS owner_name,
                        u.phone AS owner_phone
                    FROM farms f
                    LEFT JOIN zones z
                        ON z.farm_id = f.id
                    LEFT JOIN devices d
                        ON d.farm_id = f.id
                       AND d.is_active = TRUE
                    LEFT JOIN technician_assignments ta
                        ON ta.farm_id = f.id
                       AND ta.is_active = TRUE
                    LEFT JOIN technicians t
                        ON t.id = ta.technician_id
                    LEFT JOIN users u
                        ON u.id = f.owner_id
                    {where_clause}
                    GROUP BY
                        f.id,
                        f.farm_code,
                        f.name,
                        f.address,
                        f.status,
                        f.approval_status,
                        f.approved_by,
                        f.approved_at,
                        f.rejection_reason,
                        f.created_at,
                        t.id,
                        t.full_name,
                        u.full_name,
                        u.phone
                    """,
                    params,
                )
                row = cur.fetchone()

        if row is None:
            return None

        return {
            "farm_id": str(row[0]),
            "farm_code": row[1],
            "farm_name": row[2],
            "address": row[3],
            "status": row[4] or "ACTIVE",
            "approval_status": row[5] or "APPROVED",
            "approved_by": str(row[6]) if row[6] else None,
            "approved_at": row[7].isoformat() if row[7] else None,
            "rejection_reason": row[8],
            "created_at": row[9].isoformat() if row[9] else None,
            "zone_count": row[10],
            "device_count": row[11],
            "owner_name": row[14],
            "owner_phone": row[15],
            "technician_id": str(row[12]) if row[12] else None,
            "technician_name": row[13] if row[13] else None,
        }

    def create_farm(
        self,
        farm_code: str | None = None,
        farm_name: str = "",
        address: str | None = None,
        status: str = "ACTIVE",
        owner_id: str | None = None,
        approval_status: str = "APPROVED",
        approved_by: str | None = None,
    ) -> dict:
        import secrets
        import psycopg

        auto_generate = not (isinstance(farm_code, str) and farm_code.strip())
        max_attempts = 8 if auto_generate else 1

        with get_connection() as conn:
            with conn.cursor() as cur:
                for _ in range(max_attempts):
                    candidate_code = (
                        f"FARM-{secrets.token_hex(3).upper()}"
                        if auto_generate
                        else farm_code.strip()
                    )
                    try:
                        cur.execute(
                            """
                            INSERT INTO farms (
                                farm_code, name, address, status, owner_id,
                                approval_status, approved_by, approved_at
                            )
                            VALUES (
                                %s, %s, %s, %s, %s,
                                %s, %s, CASE WHEN %s = 'APPROVED' THEN NOW() ELSE NULL END
                            )
                            RETURNING id;
                            """,
                            (
                                candidate_code,
                                farm_name.strip(),
                                address,
                                status,
                                owner_id,
                                approval_status,
                                approved_by,
                                approval_status,
                            ),
                        )
                        new_id = str(cur.fetchone()[0])
                        conn.commit()
                        return self.get_farm_by_id(new_id)
                    except psycopg.errors.UniqueViolation as exc:
                        conn.rollback()
                        if not auto_generate:
                            raise ValueError(f"Farm code '{farm_code}' already exists") from exc
                    except psycopg.errors.ForeignKeyViolation as exc:
                        conn.rollback()
                        raise ValueError("Invalid owner_id reference") from exc
        raise ValueError("Failed to generate unique farm_code")

    def approve_farm(self, farm_id: str, admin_user_id: str) -> dict | None:
        existing = self.get_farm_by_id(farm_id)
        if not existing:
            return None
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE farms
                    SET approval_status = 'APPROVED',
                        approved_by = %s,
                        approved_at = NOW(),
                        rejection_reason = NULL,
                        updated_at = NOW()
                    WHERE id = %s;
                    """,
                    (admin_user_id, existing["farm_id"]),
                )
                conn.commit()
        return self.get_farm_by_id(existing["farm_id"])

    def reject_farm(self, farm_id: str, admin_user_id: str, rejection_reason: str) -> dict | None:
        existing = self.get_farm_by_id(farm_id)
        if not existing:
            return None
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE farms
                    SET approval_status = 'REJECTED',
                        approved_by = %s,
                        approved_at = NOW(),
                        rejection_reason = %s,
                        updated_at = NOW()
                    WHERE id = %s;
                    """,
                    (admin_user_id, rejection_reason.strip(), existing["farm_id"]),
                )
                conn.commit()
        return self.get_farm_by_id(existing["farm_id"])

    def update_farm(
        self,
        farm_id: str,
        farm_name: str | None = None,
        address: str | None = None,
        status: str | None = None,
        owner_id: str | None = None,
    ) -> dict | None:
        import psycopg
        existing = self.get_farm_by_id(farm_id)
        if not existing:
            return None
        updates = []
        params = []
        if farm_name is not None:
            updates.append("name = %s")
            params.append(farm_name.strip())
        if address is not None:
            updates.append("address = %s")
            params.append(address)
        if status is not None:
            updates.append("status = %s")
            params.append(status)
        if owner_id is not None:
            updates.append("owner_id = %s")
            params.append(owner_id)
        if updates:
            updates.append("updated_at = NOW()")
            params.append(existing["farm_id"])
            with get_connection() as conn:
                with conn.cursor() as cur:
                    try:
                        cur.execute(
                            f"UPDATE farms SET {', '.join(updates)} WHERE id = %s;",
                            tuple(params),
                        )
                        conn.commit()
                    except psycopg.errors.ForeignKeyViolation as exc:
                        conn.rollback()
                        raise ValueError("Invalid owner_id reference") from exc
        return self.get_farm_by_id(existing["farm_id"])

    def delete_farm(self, farm_id: str) -> bool:
        existing = self.get_farm_by_id(farm_id)
        if not existing:
            return False
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM farms WHERE id = %s;", (existing["farm_id"],))
                deleted = cur.rowcount > 0
                conn.commit()
        return deleted

    def get_farm_recipients(self, farm_id: str) -> dict | None:
        farm = self.get_farm_by_id(farm_id)
        if not farm:
            return None
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT owner_id FROM farms WHERE id = %s;", (farm["farm_id"],))
                owner_row = cur.fetchone()
                owner_id = str(owner_row[0]) if owner_row and owner_row[0] else None
                cur.execute(
                    """
                    SELECT technician_id
                    FROM technician_assignments
                    WHERE farm_id = %s AND is_active = TRUE
                    ORDER BY is_primary DESC, assigned_at ASC;
                    """,
                    (farm["farm_id"],),
                )
                tech_ids = [str(r[0]) for r in cur.fetchall()]
        return {
            "farm_id": farm["farm_id"],
            "farm_code": farm["farm_code"],
            "owner_id": owner_id,
            "technician_ids": tech_ids,
        }


farm_repository = FarmRepository()
