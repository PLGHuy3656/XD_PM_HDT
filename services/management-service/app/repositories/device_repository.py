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
                    query += " AND d.farm_id = %s"
                    params.append(farm_id)

                if zone_id:
                    query += " AND d.zone_id = %s"
                    params.append(zone_id)

                query += " ORDER BY d.node_id"
                cur.execute(query, tuple(params))
                rows = cur.fetchall()

        identifiers: list[str] = []
        for r in rows:
            identifiers.append(str(r[0]))
            if r[1]:
                identifiers.append(str(r[1]))

        runtime_states = self._iot_adapter.get_devices_runtime_state(identifiers)

        return [
            {
                "device_id": str(row[0]),
                "node_id": row[1],
                "name": row[2],
                "device_type": row[3],
                "farm_id": str(row[4]),
                "zone_id": str(row[5]) if row[5] else None,
                "zone_name": row[6],
                "ip_address": row[7],
                "firmware_version": row[8],
                "is_active": row[9],
                "status": (
                    "ONLINE"
                    if (str(row[0]) in runtime_states or (row[1] and str(row[1]) in runtime_states))
                    else "OFFLINE"
                ),
                "created_at": row[10].isoformat() if row[10] else None,
            }
            for row in rows
        ]

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

        presence = None
        if node_id:
            presence = self._iot_adapter.get_device_presence(node_id)
        if presence is None:
            presence = self._iot_adapter.get_device_presence(dev_uuid)

        is_online = bool(presence and presence.get("is_online"))
        presence_status = presence["status"] if presence and presence.get("status") else "UNKNOWN"

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
            "status": "ONLINE" if is_online else "OFFLINE",
            "presence_status": presence_status,
            "created_at": row[10].isoformat() if row[10] else None,
        }


device_repository = DeviceRepository()
