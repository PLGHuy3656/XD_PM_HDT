from app.database import get_connection


class FarmRepository:
    def list_farms(self):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        h.id,
                        h.house_code,
                        h.name,
                        COUNT(DISTINCT z.id) AS zone_count,
                        COUNT(DISTINCT d.id) AS device_count
                    FROM public.houses h
                    LEFT JOIN public.zones z
                        ON z.house_id = h.id
                    LEFT JOIN public.devices d
                        ON d.house_id = h.id
                       AND d.is_active = TRUE
                    GROUP BY
                        h.id,
                        h.house_code,
                        h.name
                    ORDER BY h.name
                    """
                )
                rows = cur.fetchall()

        return [
            {
                "farm_id": str(row[0]),
                "farm_code": row[1],
                "farm_name": row[2],
                "address": None,
                "status": "ACTIVE",
                "zone_count": row[3],
                "device_count": row[4],
            }
            for row in rows
        ]

    def get_farm_by_id(self, farm_id: str):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        h.id,
                        h.house_code,
                        h.name,
                        h.created_at,
                        COUNT(DISTINCT z.id) AS zone_count,
                        COUNT(DISTINCT d.id) AS device_count,
                        t.id AS technician_id,
                        t.full_name AS technician_name
                    FROM public.houses h
                    LEFT JOIN public.zones z
                        ON z.house_id = h.id
                    LEFT JOIN public.devices d
                        ON d.house_id = h.id
                       AND d.is_active = TRUE
                    LEFT JOIN public.technician_house_assignments tha
                        ON tha.house_id = h.id
                       AND tha.is_active = TRUE
                    LEFT JOIN public.technicians t
                        ON t.id = tha.technician_id
                    WHERE h.id = %s OR h.house_code = %s
                    GROUP BY
                        h.id,
                        h.house_code,
                        h.name,
                        h.created_at,
                        t.id,
                        t.full_name
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
            "address": None,
            "status": "ACTIVE",
            "created_at": row[3].isoformat() if row[3] else None,
            "zone_count": row[4],
            "device_count": row[5],
            "owner_name": None,
            "owner_phone": None,
            "technician_id": str(row[6]) if row[6] else None,
            "technician_name": row[7] if row[7] else None,
        }


farm_repository = FarmRepository()
