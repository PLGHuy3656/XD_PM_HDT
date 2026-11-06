import uuid

from app.database import get_connection


class ZoneRepository:
    def list_zones_by_farm(self, farm_id: str):
        if not farm_id or not str(farm_id).strip():
            return []

        farm_id_str = str(farm_id).strip()
        is_uuid = False
        try:
            uuid.UUID(farm_id_str)
            is_uuid = True
        except (ValueError, AttributeError, TypeError):
            is_uuid = False

        where_clause = "WHERE z.farm_id = %s OR f.farm_code = %s" if is_uuid else "WHERE f.farm_code = %s"
        params = (farm_id_str, farm_id_str) if is_uuid else (farm_id_str,)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
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
                    {where_clause}
                    GROUP BY
                        z.id,
                        z.farm_id,
                        z.zone_code,
                        z.name,
                        z.created_at
                    ORDER BY z.zone_code
                    """,
                    params,
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
        """
        Loads a Zone strictly by its primary key UUID.
        Non-UUID identifiers are safely rejected (returns None) to eliminate cross-tenant IDOR.
        """
        if not zone_id or not str(zone_id).strip():
            return None

        zone_id_str = str(zone_id).strip()
        try:
            uuid.UUID(zone_id_str)
        except (ValueError, AttributeError, TypeError):
            return None

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
                    WHERE z.id = %s
                    GROUP BY
                        z.id,
                        z.farm_id,
                        z.zone_code,
                        z.name,
                        z.created_at
                    """,
                    (zone_id_str,),
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
