from app.database import get_connection


class FarmRepository:
    def list_farms(self):
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
                        COUNT(DISTINCT z.id) AS zone_count,
                        COUNT(DISTINCT d.id) AS device_count
                    FROM farms f
                    LEFT JOIN zones z
                        ON z.farm_id = f.id
                    LEFT JOIN devices d
                        ON d.farm_id = f.id
                       AND d.is_active = TRUE
                    GROUP BY
                        f.id,
                        f.farm_code,
                        f.name,
                        f.address,
                        f.status
                    ORDER BY f.name
                    """
                )
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
                    LEFT JOIN technician_assignments ta
                        ON ta.farm_id = f.id
                       AND ta.is_active = TRUE
                    LEFT JOIN technicians t
                        ON t.id = ta.technician_id
                    LEFT JOIN users u
                        ON u.id = f.owner_id
                    WHERE f.id = %s OR f.farm_code = %s
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
