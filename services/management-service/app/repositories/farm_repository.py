from app.database import get_connection


class FarmRepository:
    def list_farms(self, user_id: str, is_admin: bool, is_owner: bool, is_technician: bool):
        access_conditions = []
        params = []

        if not is_admin:
            if is_owner:
                access_conditions.append("f.owner_id::text = %s")
                params.append(user_id)
            if is_technician:
                access_conditions.append(
                    """
                    EXISTS (
                        SELECT 1
                        FROM technician_assignments ta
                        WHERE ta.farm_id = f.id
                          AND ta.technician_id::text = %s
                          AND ta.is_active = TRUE
                    )
                    """
                )
                params.append(user_id)

        with get_connection() as conn:
            with conn.cursor() as cur:
                query = """
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
                """
                if not is_admin:
                    if access_conditions:
                        query += " WHERE (" + " OR ".join(access_conditions) + ")"
                    else:
                        query += " WHERE FALSE"

                query += """
                    GROUP BY
                        f.id,
                        f.farm_code,
                        f.name,
                        f.address,
                        f.status
                    ORDER BY f.name
                """
                cur.execute(query, tuple(params))
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
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
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
                    LEFT JOIN LATERAL (
                        SELECT
                            tech.id,
                             tech.full_name
                        FROM technician_assignments ta
                        JOIN technicians tech
                            ON tech.id = ta.technician_id
                        WHERE ta.farm_id = f.id
                            AND ta.is_active = TRUE
                        ORDER BY
                            ta.is_primary DESC,
                            ta.assigned_at DESC,
                            ta.technician_id ASC
                        LIMIT 1
                    ) AS t ON TRUE
                    LEFT JOIN users u
                        ON u.id = f.owner_id
                    WHERE f.id::text = %s OR f.farm_code = %s
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
                    (farm_id, farm_id),
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
