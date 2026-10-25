from app.database import get_connection


class TechnicianRepository:
    def list_technicians(self):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        full_name,
                        email,
                        phone,
                        status
                    FROM public.technicians
                    ORDER BY full_name
                    """
                )
                rows = cur.fetchall()

        return [
            {
                "technician_id": str(row[0]),
                "full_name": row[1],
                "email": row[2],
                "phone": row[3],
                "status": row[4],
            }
            for row in rows
        ]

    def get_profile(self, technician_id: str):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        full_name,
                        email,
                        phone,
                        status
                    FROM public.technicians
                    WHERE id = %s
                    """,
                    (technician_id,),
                )

                row = cur.fetchone()

        if row is None:
            return None

        return {
            "technician_id": str(row[0]),
            "full_name": row[1],
            "email": row[2],
            "phone": row[3],
            "status": row[4],
        }

    def get_assigned_farms(self, technician_id: str):
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
                    FROM public.technician_house_assignments tha
                    JOIN public.houses h
                        ON h.id = tha.house_id
                    LEFT JOIN public.zones z
                        ON z.house_id = h.id
                    LEFT JOIN public.devices d
                        ON d.house_id = h.id
                       AND d.is_active = TRUE
                    WHERE tha.technician_id = %s
                      AND tha.is_active = TRUE
                    GROUP BY
                        h.id,
                        h.house_code,
                        h.name
                    ORDER BY h.name
                    """,
                    (technician_id,),
                )

                rows = cur.fetchall()

        return [
            {
                "farm_id": str(row[0]),
                "farm_code": row[1],
                "farm_name": row[2],
                "address": None,
                "status": None,
                "zone_count": row[3],
                "device_count": row[4],
            }
            for row in rows
        ]

    def get_assigned_farm_detail(
        self,
        technician_id: str,
        farm_id: str,
    ):
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
                    FROM public.technician_house_assignments tha
                    JOIN public.houses h
                        ON h.id = tha.house_id
                    LEFT JOIN public.zones z
                        ON z.house_id = h.id
                    LEFT JOIN public.devices d
                        ON d.house_id = h.id
                       AND d.is_active = TRUE
                    WHERE tha.technician_id = %s
                      AND (tha.house_id = %s OR h.house_code = %s)
                      AND tha.is_active = TRUE
                    GROUP BY
                        h.id,
                        h.house_code,
                        h.name
                    """,
                    (technician_id, farm_id, farm_id),
                )

                row = cur.fetchone()

        if row is None:
            return None

        return {
            "farm_id": str(row[0]),
            "farm_code": row[1],
            "farm_name": row[2],
            "address": None,
            "status": None,
            "zone_count": row[3],
            "device_count": row[4],
            "owner_name": None,
            "owner_phone": None,
        }

    def get_assigned_farm_devices(
        self,
        technician_id: str,
        farm_id: str,
    ):
        # TODO(MICROSERVICE-BOUNDARY):
        # - Boundary Crossover: Reading public.device_latest_state (recorded_at, device_state JSONB).
        # - Future Service Owner: IoT Service owns runtime state, telemetry, and device online/offline status.
        # - Eventual Replacement: Replace with IoT Service REST API call or local read model updated via RabbitMQ telemetry events.
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        d.id,
                        d.node_id,
                        d.name,
                        d.device_type,
                        d.house_id,
                        d.zone_id,
                        z.name,
                        d.ip_address,
                        d.firmware_version,
                        dls.recorded_at,
                        dls.device_state
                    FROM public.technician_house_assignments tha
                    JOIN public.devices d
                        ON d.house_id = tha.house_id
                    JOIN public.houses h
                        ON h.id = tha.house_id
                    LEFT JOIN public.zones z
                        ON z.id = d.zone_id
                    LEFT JOIN public.device_latest_state dls
                        ON dls.device_id = d.id
                    WHERE tha.technician_id = %s
                      AND (tha.house_id = %s OR h.house_code = %s)
                      AND tha.is_active = TRUE
                      AND d.is_active = TRUE
                    ORDER BY d.node_id
                    """,
                    (technician_id, farm_id, farm_id),
                )

                rows = cur.fetchall()

        devices = []

        for row in rows:
            device_state = row[10] or {}
            rssi = device_state.get("networkRssi")

            devices.append(
                {
                    "device_id": str(row[0]),
                    "node_id": row[1],
                    "name": row[2],
                    "device_type": row[3],
                    "type_label": row[3],
                    "farm_id": str(row[4]),
                    "zone_id": (
                        str(row[5])
                        if row[5] is not None
                        else None
                    ),
                    "zone_name": row[6],
                    "status": (
                        "ONLINE"
                        if row[9] is not None
                        else "OFFLINE"
                    ),
                    "rssi": rssi,
                    "mqtt_status": (
                        "Connected"
                        if row[9] is not None
                        else "Disconnected"
                    ),
                    "ip_address": row[7],
                    "firmware_version": row[8],
                    "last_seen": (
                        row[9].isoformat()
                        if row[9] is not None
                        else None
                    ),
                }
            )

        return devices

    def get_assigned_farm_device_detail(
        self,
        technician_id: str,
        farm_id: str,
        device_id: str,
    ):
        devices = self.get_assigned_farm_devices(
            technician_id,
            farm_id,
        )

        for device in devices:
            if (
                device["device_id"] == device_id
                or device["node_id"] == device_id
            ):
                return device

        return None

    def get_dashboard_summary(
        self,
        technician_id: str,
    ):
        # TODO(MICROSERVICE-BOUNDARY):
        # - Boundary Crossover: Reading public.device_latest_state to compute online/offline device counts.
        # - Future Service Owner: IoT Service owns device presence and telemetry state.
        # - Eventual Replacement: Query IoT Service metrics endpoint or read cached state projection.
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(DISTINCT tha.house_id)
                            AS assigned_farm_count,

                        COUNT(DISTINCT z.id)
                            AS zone_count,

                        COUNT(DISTINCT d.id)
                            AS device_count,

                        COUNT(
                            DISTINCT CASE
                                WHEN dls.device_id IS NOT NULL
                                THEN d.id
                            END
                        ) AS online_device_count,

                        COUNT(
                            DISTINCT CASE
                                WHEN d.id IS NOT NULL
                                AND dls.device_id IS NULL
                                THEN d.id
                            END
                        ) AS offline_device_count

                    FROM public.technician_house_assignments tha

                    LEFT JOIN public.zones z
                        ON z.house_id = tha.house_id

                    LEFT JOIN public.devices d
                        ON d.house_id = tha.house_id
                    AND d.is_active = TRUE

                    LEFT JOIN public.device_latest_state dls
                        ON dls.device_id = d.id

                    WHERE tha.technician_id = %s
                    AND tha.is_active = TRUE
                    """,
                    (technician_id,),
                )

                row = cur.fetchone()

        return {
            "technician_id": technician_id,
            "assigned_farm_count": row[0] or 0,
            "zone_count": row[1] or 0,
            "device_count": row[2] or 0,
            "online_device_count": row[3] or 0,
            "offline_device_count": row[4] or 0,
        }

    def assign_technician(self, technician_id: str, farm_id: str, is_primary: bool = True):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.technician_house_assignments (
                        technician_id, house_id, is_primary, is_active
                    )
                    VALUES (%s, %s, %s, TRUE)
                    ON CONFLICT (technician_id, house_id)
                    DO UPDATE SET
                        is_primary = EXCLUDED.is_primary,
                        is_active = TRUE,
                        assigned_at = NOW()
                    RETURNING id;
                    """,
                    (technician_id, farm_id, is_primary),
                )
                assigned_id = cur.fetchone()[0]
                conn.commit()

        return str(assigned_id)


technician_repository = TechnicianRepository()
