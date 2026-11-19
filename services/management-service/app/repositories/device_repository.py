from app.adapters.iot_service_adapter import IoTServiceAdapter, iot_service_adapter
from app.database import get_connection


class AmbiguousDeviceIdentifierError(ValueError):
    """Raised when an identifier matches multiple devices across UUID and node_id spaces."""
    pass


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

            presence_info = (
                all_presence.get(node_id)
                if (all_presence and node_id and node_id in all_presence)
                else (all_presence.get(dev_id) if all_presence else None)
            )
            status_val, _, _, _ = self._iot_adapter.resolve_status(
                presence_info,
                iot_reachable,
            )

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
                    "presence_status": status_val,
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

        # L-1 & M-3: Re-use central resolve_status helper to unify Owner and Technician behavior
        iot_reachable = presence.get("reason") != "IOT_SERVICE_UNREACHABLE"
        presence_info = presence if presence.get("reason") != "PRESENCE_NOT_FOUND" else None
        status_val, _, _, _ = self._iot_adapter.resolve_status(
            presence_info,
            iot_reachable,
        )

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

    def get_internal_device_metadata(self, identifier: str) -> dict | None:
        """Resolves minimal internal metadata for a device by MQTT node_id or canonical UUID.

        Enforces security invariants:
        - Safe SQL branching: never casts non-UUID strings to UUID in Postgres.
        - Excludes PII (user/owner personal information).
        - Authoritatively queries management_db without relying on caller inputs.
        """
        import uuid
        if not identifier or not str(identifier).strip() or "\x00" in identifier or "\0" in identifier:
            return None

        clean_id = str(identifier).strip()
        if len(clean_id) > 100 or any(ord(c) < 32 or ord(c) == 127 for c in clean_id):
            return None

        is_uuid = False
        try:
            uuid.UUID(clean_id)
            is_uuid = True
        except (ValueError, AttributeError, TypeError):
            is_uuid = False

        with get_connection() as conn:
            try:
                with conn.cursor() as cur:
                    if is_uuid:
                        cur.execute(
                            """
                            SELECT
                                d.id,
                                d.node_id,
                                d.farm_id,
                                d.is_active,
                                d.updated_at,
                                d.metadata_version
                            FROM devices d
                            WHERE d.id = %s OR d.node_id = %s;
                            """,
                            (clean_id, clean_id),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT
                                d.id,
                                d.node_id,
                                d.farm_id,
                                d.is_active,
                                d.updated_at,
                                d.metadata_version
                            FROM devices d
                            WHERE d.node_id = %s;
                            """,
                            (clean_id,),
                        )
                    rows = cur.fetchall()
            except Exception:
                conn.rollback()
                raise

        if not rows:
            return None

        if len(rows) > 1:
            raise AmbiguousDeviceIdentifierError(
                f"Ambiguous device identifier '{clean_id}' matches multiple records in registry"
            )

        row = rows[0]

        dev_uuid = str(row[0])
        node_id = str(row[1])
        farm_uuid = str(row[2])
        is_active = bool(row[3])
        updated_at_dt = row[4]
        raw_version = row[5] if len(row) > 5 else None

        updated_at_str = updated_at_dt.isoformat() if updated_at_dt else None
        # Monotonic database-enforced version with fallback
        if raw_version is not None:
            metadata_version = int(raw_version)
        elif updated_at_dt is not None:
            metadata_version = int(updated_at_dt.timestamp() * 1_000_000)
        else:
            metadata_version = 1
        status_str = "ACTIVE" if is_active else "DISABLED"

        return {
            "deviceId": dev_uuid,
            "nodeId": node_id,
            "farmId": farm_uuid,
            "status": status_str,
            "isActive": is_active,
            "updatedAt": updated_at_str,
            "metadataVersion": metadata_version,
            "device_id": dev_uuid,
            "node_id": node_id,
            "farm_id": farm_uuid,
            "is_active": is_active,
            "updated_at": updated_at_str,
            "metadata_version": metadata_version,
        }


device_repository = DeviceRepository()
