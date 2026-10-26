from app.database import get_connection


class ZoneRepository:
    def list_zones_by_farm(self, farm_id: str):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        z.id,
                        z.farm_id,
                        z.zone_code,
                        z.name,
                        z.created_at,
                        COUNT(DISTINCT d.id) AS device_count
                    FROM zones z
                    JOIN farms f
                        ON f.id = z.farm_id
                    LEFT JOIN devices d
                        ON d.zone_id = z.id
                       AND d.is_active = TRUE
                    WHERE z.farm_id = %s OR f.farm_code = %s
                    GROUP BY
                        z.id,
                        z.farm_id,
                        z.zone_code,
                        z.name,
                        z.created_at
                    ORDER BY z.zone_code
                    """,
                    (farm_id, farm_id),
                )
                rows = cur.fetchall()

        return [
            {
                "zone_id": str(row[0]),
                "farm_id": str(row[1]),
                "zone_code": row[2],
                "name": row[3],
                "created_at": row[4].isoformat() if row[4] else None,
                "device_count": row[5],
            }
            for row in rows
        ]

    def get_zone_by_id(self, zone_id: str):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        z.id,
                        z.farm_id,
                        z.zone_code,
                        z.name,
                        z.created_at,
                        COUNT(DISTINCT d.id) AS device_count
                    FROM zones z
                    LEFT JOIN devices d
                        ON d.zone_id = z.id
                       AND d.is_active = TRUE
                    WHERE z.id = %s OR z.zone_code = %s
                    GROUP BY
                        z.id,
                        z.farm_id,
                        z.zone_code,
                        z.name,
                        z.created_at
                    """,
                    (zone_id, zone_id),
                )
                row = cur.fetchone()

        if row is None:
            return None

        return {
            "zone_id": str(row[0]),
            "farm_id": str(row[1]),
            "zone_code": row[2],
            "name": row[3],
            "created_at": row[4].isoformat() if row[4] else None,
            "device_count": row[5],
        }


zone_repository = ZoneRepository()
