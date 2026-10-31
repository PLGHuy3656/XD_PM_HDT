from app.adapters.legacy_iot_adapter import legacy_iot_adapter
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
                    FROM technicians
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
                    FROM technicians
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
                        f.id,
                        f.farm_code,
                        f.name,
                        COUNT(DISTINCT z.id) AS zone_count,
                        COUNT(DISTINCT d.id) AS device_count
                    FROM technician_assignments ta
                    JOIN farms f
                        ON f.id = ta.farm_id
                    LEFT JOIN zones z
                        ON z.farm_id = f.id
                    LEFT JOIN devices d
                        ON d.farm_id = f.id
                       AND d.is_active = TRUE
                    WHERE ta.technician_id = %s
                      AND ta.is_active = TRUE
                    GROUP BY
                        f.id,
                        f.farm_code,
                        f.name
                    ORDER BY f.name
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
                        f.id,
                        f.farm_code,
                        f.name,
                        COUNT(DISTINCT z.id) AS zone_count,
                        COUNT(DISTINCT d.id) AS device_count
                    FROM technician_assignments ta
                    JOIN farms f
                        ON f.id = ta.farm_id
                    LEFT JOIN zones z
                        ON z.farm_id = f.id
                    LEFT JOIN devices d
                        ON d.farm_id = f.id
                       AND d.is_active = TRUE
                    WHERE ta.technician_id = %s
                      AND (ta.farm_id = %s OR f.farm_code = %s)
                      AND ta.is_active = TRUE
                    GROUP BY
                        f.id,
                        f.farm_code,
                        f.name
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
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        d.id,
                        d.node_id,
                        d.name,
                        d.device_type,
                        d.farm_id,
                        d.zone_id,
                        z.name AS zone_name,
                        d.ip_address,
                        d.firmware_version
                    FROM technician_assignments ta
                    JOIN devices d
                        ON d.farm_id = ta.farm_id
                    JOIN farms f
                        ON f.id = ta.farm_id
                    LEFT JOIN zones z
                        ON z.id = d.zone_id
                    WHERE ta.technician_id = %s
                      AND (ta.farm_id = %s OR f.farm_code = %s)
                      AND ta.is_active = TRUE
                      AND d.is_active = TRUE
                    ORDER BY d.node_id
                    """,
                    (technician_id, farm_id, farm_id),
                )

                rows = cur.fetchall()

        device_ids = [str(row[0]) for row in rows]

        # TODO(MICROSERVICE-BOUNDARY):
        # - Boundary Crossover: Reading runtime state (recorded_at, device_state JSONB) via legacy_iot_adapter.
        # - Future Service Owner: IoT Service owns runtime state, telemetry, and device online/offline status.
        # - Eventual Replacement: Replace with IoT Service REST API call or local read model updated via RabbitMQ telemetry events.
        runtime_states = legacy_iot_adapter.get_devices_runtime_state(device_ids)

        devices = []

        for row in rows:
            dev_id = str(row[0])
            state_info = runtime_states.get(dev_id)
            is_online = state_info is not None
            recorded_at = state_info["recorded_at"] if state_info else None
            device_state = state_info["device_state"] if state_info else {}
            rssi = device_state.get("networkRssi")

            devices.append(
                {
                    "device_id": dev_id,
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
                        if is_online
                        else "OFFLINE"
                    ),
                    "rssi": rssi,
                    "mqtt_status": (
                        "Connected"
                        if is_online
                        else "Disconnected"
                    ),
                    "ip_address": row[7],
                    "firmware_version": row[8],
                    "last_seen": (
                        recorded_at.isoformat()
                        if recorded_at is not None
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
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(DISTINCT ta.farm_id)
                            AS assigned_farm_count,

                        COUNT(DISTINCT z.id)
                            AS zone_count,

                        COUNT(DISTINCT d.id)
                            AS device_count,

                        ARRAY_AGG(DISTINCT d.id) FILTER (WHERE d.id IS NOT NULL)
                            AS device_ids

                    FROM technician_assignments ta

                    LEFT JOIN zones z
                        ON z.farm_id = ta.farm_id

                    LEFT JOIN devices d
                        ON d.farm_id = ta.farm_id
                    AND d.is_active = TRUE

                    WHERE ta.technician_id = %s
                    AND ta.is_active = TRUE
                    """,
                    (technician_id,),
                )

                row = cur.fetchone()

        device_uuids = [str(did) for did in (row[3] or [])]

        # TODO(MICROSERVICE-BOUNDARY):
        # - Boundary Crossover: Reading runtime presence counts via legacy_iot_adapter.
        # - Future Service Owner: IoT Service owns device presence and telemetry state.
        # - Eventual Replacement: Query IoT Service metrics endpoint or read cached state projection.
        online_count, offline_count = legacy_iot_adapter.get_devices_presence_counts(
            device_uuids
        )

        return {
            "technician_id": technician_id,
            "assigned_farm_count": row[0] or 0,
            "zone_count": row[1] or 0,
            "device_count": row[2] or 0,
            "online_device_count": online_count,
            "offline_device_count": offline_count,
        }

    def assign_technician(self, technician_id: str, farm_id: str, is_primary: bool = True):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO technician_assignments (
                        technician_id, farm_id, is_primary, is_active
                    )
                    VALUES (%s, %s, %s, TRUE)
                    ON CONFLICT (technician_id, farm_id)
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
