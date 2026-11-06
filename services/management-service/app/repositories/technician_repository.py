from app.adapters.iot_service_adapter import IoTServiceAdapter, iot_service_adapter
from app.database import get_connection


class TechnicianRepository:
    def __init__(self, iot_adapter: IoTServiceAdapter | None = None):
        self._iot_adapter = iot_adapter or iot_service_adapter
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
        import uuid
        farm_id_str = str(farm_id).strip()
        is_farm_uuid = False
        try:
            uuid.UUID(farm_id_str)
            is_farm_uuid = True
        except (ValueError, AttributeError, TypeError):
            is_farm_uuid = False

        where_farm = "(ta.farm_id = %s OR f.farm_code = %s)" if is_farm_uuid else "f.farm_code = %s"
        farm_params = (farm_id_str, farm_id_str) if is_farm_uuid else (farm_id_str,)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
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
                      AND {where_farm}
                      AND ta.is_active = TRUE
                    GROUP BY
                        f.id,
                        f.farm_code,
                        f.name
                    """,
                    (technician_id, *farm_params),
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
        import uuid
        farm_id_str = str(farm_id).strip()
        is_farm_uuid = False
        try:
            uuid.UUID(farm_id_str)
            is_farm_uuid = True
        except (ValueError, AttributeError, TypeError):
            is_farm_uuid = False

        where_farm = "(ta.farm_id = %s OR f.farm_code = %s)" if is_farm_uuid else "f.farm_code = %s"
        farm_params = (farm_id_str, farm_id_str) if is_farm_uuid else (farm_id_str,)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
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
                      AND {where_farm}
                      AND ta.is_active = TRUE
                      AND d.is_active = TRUE
                    ORDER BY d.node_id
                    """,
                    (technician_id, *farm_params),
                )

                rows = cur.fetchall()

        all_presence = self._iot_adapter.list_devices_presence()
        iot_reachable = all_presence is not None

        devices = []

        for row in rows:
            dev_id = str(row[0])
            node_id = str(row[1]) if row[1] else None
            presence_info = (
                all_presence.get(node_id)
                if (all_presence and node_id and node_id in all_presence)
                else (all_presence.get(dev_id) if all_presence else None)
            )

            status_val, mqtt_val, rssi, recorded_at = self._iot_adapter.resolve_status(
                presence_info,
                iot_reachable,
            )

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
                    "status": status_val,
                    "rssi": rssi,
                    "mqtt_status": mqtt_val,
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
                            AS device_ids,

                        ARRAY_AGG(DISTINCT d.node_id) FILTER (WHERE d.node_id IS NOT NULL)
                            AS node_ids

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
        node_ids = [str(nid) for nid in (row[4] or [])] if len(row) > 4 else []
        lookup_ids = node_ids if node_ids else device_uuids
        total_devices = int(row[2] or 0)

        all_presence = self._iot_adapter.list_devices_presence()
        if all_presence is None:
            # IoT Service is down / unreachable: all devices are UNKNOWN; never count UNKNOWN as OFFLINE
            online_count = 0
            offline_count = 0
            unknown_count = total_devices
        else:
            online_count = 0
            offline_count = 0
            unknown_count = 0
            for did in lookup_ids:
                p_info = all_presence.get(did)
                status_val, _, _, _ = self._iot_adapter.resolve_status(p_info, iot_reachable=True)
                if status_val == "ONLINE":
                    online_count += 1
                elif status_val == "OFFLINE":
                    offline_count += 1
                else:
                    unknown_count += 1

            accounted = online_count + offline_count + unknown_count
            if accounted < total_devices:
                offline_count += (total_devices - accounted)

        return {
            "technician_id": technician_id,
            "assigned_farm_count": row[0] or 0,
            "zone_count": row[1] or 0,
            "device_count": total_devices,
            "online_device_count": online_count,
            "offline_device_count": offline_count,
            "unknown_device_count": unknown_count,
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
