from app.adapters.iot_service_adapter import IoTServiceAdapter, iot_service_adapter
from app.database import get_connection


class DeviceRepository:
    def __init__(self, iot_adapter: IoTServiceAdapter | None = None):
        self._iot_adapter = iot_adapter or iot_service_adapter

    def list_devices(self, farm_id: str | None = None, zone_id: str | None = None):
        with get_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT
                        d.id,
                        d.node_id,
                        d.name,
                        d.device_type,
                        d.farm_id,
                        d.zone_id,
                        z.name AS zone_name,
                        d.ip_address,
                        d.firmware_version,
                        d.is_active,
                        d.created_at
                    FROM devices d
                    LEFT JOIN zones z
                        ON z.id = d.zone_id
                    WHERE d.is_active = TRUE
                """
                params = []

                if farm_id:
                    import uuid
                    farm_str = str(farm_id).strip()
                    is_f_uuid = False
                    try:
                        uuid.UUID(farm_str)
                        is_f_uuid = True
                    except (ValueError, AttributeError, TypeError):
                        is_f_uuid = False

                    if is_f_uuid:
                        query += " AND d.farm_id = %s"
                        params.append(farm_str)
                    else:
                        query += " AND d.farm_id IN (SELECT f.id FROM farms f WHERE f.farm_code = %s)"
                        params.append(farm_str)

                if zone_id:
                    import uuid
                    zone_str = str(zone_id).strip()
                    is_z_uuid = False
                    try:
                        uuid.UUID(zone_str)
                        is_z_uuid = True
                    except (ValueError, AttributeError, TypeError):
                        is_z_uuid = False

                    if is_z_uuid:
                        query += " AND d.zone_id = %s"
                        params.append(zone_str)
                    else:
                        query += " AND d.zone_id IN (SELECT z.id FROM zones z WHERE z.zone_code = %s)"
                        params.append(zone_str)

                query += " ORDER BY d.node_id"
                cur.execute(query, tuple(params))
                rows = cur.fetchall()

        all_presence = self._iot_adapter.list_devices_presence()
        iot_reachable = all_presence is not None

        devices = []
        for row in rows:
            dev_id = str(row[0])
            node_id = str(row[1]) if row[1] else None

            if not iot_reachable:
                status_val = "UNKNOWN"
            else:
                presence_info = (
                    all_presence.get(node_id)
                    if node_id and node_id in all_presence
                    else all_presence.get(dev_id)
                )
                if presence_info:
                    raw_status = presence_info.get("status")
                    status_val = raw_status if raw_status in ("ONLINE", "OFFLINE") else "UNKNOWN"
                else:
                    status_val = "OFFLINE"

            devices.append(
                {
                    "device_id": dev_id,
                    "node_id": row[1],
                    "name": row[2],
                    "device_type": row[3],
                    "farm_id": str(row[4]),
                    "zone_id": str(row[5]) if row[5] else None,
                    "zone_name": row[6],
                    "ip_address": row[7],
                    "firmware_version": row[8],
                    "is_active": row[9],
                    "status": status_val,
                    "created_at": row[10].isoformat() if row[10] else None,
                }
            )

        return devices

    def get_device_by_id(self, device_id: str):
        import uuid
        dev_id_str = str(device_id).strip()
        is_uuid = False
        try:
            uuid.UUID(dev_id_str)
            is_uuid = True
        except (ValueError, AttributeError, TypeError):
            is_uuid = False

        with get_connection() as conn:
            with conn.cursor() as cur:
                if is_uuid:
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
                            d.firmware_version,
                            d.is_active,
                            d.created_at
                        FROM devices d
                        LEFT JOIN zones z
                            ON z.id = d.zone_id
                        WHERE d.id = %s OR d.node_id = %s
                        """,
                        (dev_id_str, dev_id_str),
                    )
                else:
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
                            d.firmware_version,
                            d.is_active,
                            d.created_at
                        FROM devices d
                        LEFT JOIN zones z
                            ON z.id = d.zone_id
                        WHERE d.node_id = %s
                        """,
                        (dev_id_str,),
                    )
                row = cur.fetchone()

        if row is None:
            return None

        dev_uuid = str(row[0])
        node_id = str(row[1]) if row[1] else None

        # M-1: Query presence ONCE using primary identifier (node_id preferred, dev_uuid as fallback)
        primary_id = node_id or dev_uuid
        presence = self._iot_adapter.resolve_device_presence(primary_id)

        # M-3: Distinguish confirmed OFFLINE from UNKNOWN (IoT unavailable / no presence record)
        raw_status = presence.get("status") if presence else None
        status_val = raw_status if raw_status in ("ONLINE", "OFFLINE") else "UNKNOWN"

        return {
            "device_id": dev_uuid,
            "node_id": row[1],
            "name": row[2],
            "device_type": row[3],
            "farm_id": str(row[4]),
            "zone_id": str(row[5]) if row[5] else None,
            "zone_name": row[6],
            "ip_address": row[7],
            "firmware_version": row[8],
            "is_active": row[9],
            "status": status_val,
            "presence_status": status_val,
            "created_at": row[10].isoformat() if row[10] else None,
        }


device_repository = DeviceRepository()
