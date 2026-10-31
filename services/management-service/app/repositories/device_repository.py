from app.adapters.legacy_iot_adapter import legacy_iot_adapter
from app.database import get_connection


class DeviceRepository:
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

        device_ids = [str(r[0]) for r in rows]

        # TODO(MICROSERVICE-BOUNDARY):
        # - Boundary Crossover: Reading runtime state via legacy_iot_adapter to project device online status.
        # - Future Service Owner: IoT Service owns runtime state, device presence, heartbeat, and online/offline status.
        # - Eventual Replacement: Replace with IoT Service REST API call (e.g., GET /api/iot/devices/presence)
        #   or a cached runtime projection via Redis/RabbitMQ presence events.
        runtime_states = legacy_iot_adapter.get_devices_runtime_state(device_ids)

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
                "status": "ONLINE" if str(row[0]) in runtime_states else "OFFLINE",
                "created_at": row[10].isoformat() if row[10] else None,
            }
            for row in rows
        ]

    def get_device_by_id(self, device_id: str):
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
                        d.firmware_version,
                        d.is_active,
                        d.created_at
                    FROM devices d
                    LEFT JOIN zones z
                        ON z.id = d.zone_id
                    WHERE d.id = %s OR d.node_id = %s
                    """,
                    (device_id, device_id),
                )
                row = cur.fetchone()

        if row is None:
            return None

        dev_uuid = str(row[0])

        # TODO(MICROSERVICE-BOUNDARY):
        # - Boundary Crossover: Reading runtime status from IoT adapter.
        # - Future Service Owner: IoT Service owns runtime status.
        # - Eventual Replacement: Inter-service call to IoT Service or Redis presence cache.
        runtime_states = legacy_iot_adapter.get_devices_runtime_state([dev_uuid])

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
            "status": "ONLINE" if dev_uuid in runtime_states else "OFFLINE",
            "created_at": row[10].isoformat() if row[10] else None,
        }


device_repository = DeviceRepository()
