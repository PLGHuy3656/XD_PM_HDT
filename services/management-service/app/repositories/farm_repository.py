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
                f.status
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
                "zone_count": row[5],
                "device_count": row[6],
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
            "created_at": row[5].isoformat() if row[5] else None,
            "zone_count": row[6],
            "device_count": row[7],
            "owner_name": row[10],
            "owner_phone": row[11],
            "technician_id": str(row[8]) if row[8] else None,
            "technician_name": row[9] if row[9] else None,
        }


farm_repository = FarmRepository()
