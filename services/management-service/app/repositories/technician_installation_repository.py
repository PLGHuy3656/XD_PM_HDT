from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from app.database import get_connection


class DeviceAlreadyRegisteredError(Exception):
    pass


class InstallationStateError(Exception):
    pass


_INSTALLATION_SELECT = """
    SELECT
        ti.id,
        ti.device_id,
        d.node_id,
        ti.technician_id,
        ti.farm_id,
        ti.zone_id,
        d.name,
        d.device_type,
        d.firmware_version,
        d.ip_address,
        d.is_active,
        ti.status,
        ti.configuration,
        ti.validation_report,
        ti.created_at,
        ti.updated_at,
        ti.activated_at,
        ti.validated_at,
        ti.handed_over_at,
        (
            ti.status = 'HANDED_OVER'
            OR (
                d.farm_id = ti.farm_id
                AND d.zone_id IS NOT DISTINCT FROM ti.zone_id
                AND (
                    ti.zone_id IS NULL
                    OR (z.id IS NOT NULL AND z.farm_id = ti.farm_id)
                )
            )
        )
    FROM technician_installations AS ti
    JOIN devices AS d ON d.id = ti.device_id
    LEFT JOIN zones AS z ON z.id = ti.zone_id
"""

_ACTIVE_ASSIGNMENT = """
    EXISTS (
        SELECT 1
        FROM technician_assignments AS assignment
        WHERE assignment.technician_id = ti.technician_id
          AND assignment.farm_id = ti.farm_id
          AND assignment.is_active = TRUE
    )
"""


def _serialize_installation(row: tuple) -> dict[str, Any]:
    return {
        "installation_id": row[0],
        "device_id": row[1],
        "node_id": row[2],
        "technician_id": row[3],
        "farm_id": row[4],
        "zone_id": row[5],
        "name": row[6],
        "device_type": row[7],
        "firmware_version": row[8],
        "ip_address": row[9],
        "is_active": row[10],
        "status": row[11],
        "configuration": row[12] or {},
        "validation_report": row[13] or {},
        "created_at": row[14].isoformat(),
        "updated_at": row[15].isoformat(),
        "activated_at": row[16].isoformat() if row[16] else None,
        "validated_at": row[17].isoformat() if row[17] else None,
        "handed_over_at": row[18].isoformat() if row[18] else None,
        "farm_zone_linked": bool(row[19]),
    }


class TechnicianInstallationRepository:
    def create_installation(
        self,
        *,
        technician_id: UUID,
        node_id: str,
        farm_id: UUID,
        zone_id: UUID | None,
        name: str | None,
        device_type: str,
        firmware_version: str | None,
        ip_address: str | None,
    ) -> dict[str, Any] | None:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id
                        FROM technician_assignments
                        WHERE technician_id = %s
                          AND farm_id = %s
                          AND is_active = TRUE
                        FOR SHARE
                        """,
                        (technician_id, farm_id),
                    )
                    if cur.fetchone() is None:
                        return None

                    cur.execute(
                        """
                        INSERT INTO devices (
                            node_id, farm_id, zone_id, name, device_type,
                            firmware_version, ip_address, is_active
                        )
                        SELECT %s, farm.id, zone.id, %s, %s, %s, %s, FALSE
                        FROM farms AS farm
                        LEFT JOIN zones AS zone
                            ON zone.id = %s
                           AND zone.farm_id = farm.id
                        WHERE farm.id = %s
                          AND (%s::uuid IS NULL OR zone.id IS NOT NULL)
                          AND EXISTS (
                              SELECT 1
                              FROM technician_assignments AS assignment
                              WHERE assignment.technician_id = %s
                                AND assignment.farm_id = farm.id
                                AND assignment.is_active = TRUE
                          )
                        RETURNING id
                        """,
                        (
                            node_id,
                            name,
                            device_type,
                            firmware_version,
                            ip_address,
                            zone_id,
                            farm_id,
                            zone_id,
                            technician_id,
                        ),
                    )
                    device_row = cur.fetchone()
                    if device_row is None:
                        return None

                    cur.execute(
                        """
                        INSERT INTO technician_installations (
                            device_id, technician_id, farm_id, zone_id
                        )
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                        """,
                        (device_row[0], technician_id, farm_id, zone_id),
                    )
                    installation_id = cur.fetchone()[0]
                    row = self._get_installation(
                        cur,
                        installation_id,
                        technician_id,
                    )
                    return (
                        _serialize_installation(row)
                        if row is not None
                        else None
                    )
        except psycopg.errors.UniqueViolation as exc:
            raise DeviceAlreadyRegisteredError(
                f"Device node_id '{node_id}' is already registered",
            ) from exc

    def list_installations(
        self,
        technician_id: UUID,
        farm_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        query = (
            _INSTALLATION_SELECT
            + f"""
            WHERE ti.technician_id = %s
              AND {_ACTIVE_ASSIGNMENT}
            """
        )
        params: list[Any] = [technician_id]
        if farm_id is not None:
            query += " AND ti.farm_id = %s"
            params.append(farm_id)
        query += " ORDER BY ti.created_at DESC, ti.id"

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                return [_serialize_installation(row) for row in cur.fetchall()]

    def get_installation(
        self,
        installation_id: UUID,
        technician_id: UUID,
    ) -> dict[str, Any] | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                row = self._get_installation(
                    cur,
                    installation_id,
                    technician_id,
                )
        return _serialize_installation(row) if row is not None else None

    def save_configuration(
        self,
        installation_id: UUID,
        technician_id: UUID,
        configuration: dict[str, Any],
    ) -> dict[str, Any] | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                row = self._lock_installation(
                    cur,
                    installation_id,
                    technician_id,
                )
                if row is None:
                    return None
                if row[0] not in {"REGISTERED", "CONFIGURED"} or row[2]:
                    raise InstallationStateError(
                        "Configuration can only be saved before activation",
                    )

                cur.execute(
                    """
                    UPDATE technician_installations
                    SET configuration = %s,
                        status = 'CONFIGURED',
                        configured_at = COALESCE(configured_at, NOW()),
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (Jsonb(configuration), installation_id),
                )
                updated = self._get_installation(
                    cur,
                    installation_id,
                    technician_id,
                )
                return _serialize_installation(updated)

    def activate_installation(
        self,
        installation_id: UUID,
        technician_id: UUID,
    ) -> dict[str, Any] | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                row = self._lock_installation(
                    cur,
                    installation_id,
                    technician_id,
                )
                if row is None:
                    return None
                if (
                    row[0] != "CONFIGURED"
                    or not row[1]
                    or row[1] == {}
                    or row[2]
                ):
                    raise InstallationStateError(
                        "Installation must be configured and inactive before activation",
                    )

                cur.execute(
                    """
                    UPDATE devices
                    SET is_active = TRUE, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (row[3],),
                )
                cur.execute(
                    """
                    UPDATE technician_installations
                    SET status = 'ACTIVATED',
                        activated_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (installation_id,),
                )
                updated = self._get_installation(
                    cur,
                    installation_id,
                    technician_id,
                )
                return _serialize_installation(updated)

    def save_validation_report(
        self,
        installation_id: UUID,
        technician_id: UUID,
        *,
        passed: bool,
        report: dict[str, Any],
    ) -> dict[str, Any] | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                row = self._lock_installation(
                    cur,
                    installation_id,
                    technician_id,
                )
                if row is None:
                    return None
                if row[0] != "ACTIVATED" or not row[2]:
                    raise InstallationStateError(
                        "Only an activated installation can be validated",
                    )

                cur.execute(
                    """
                    UPDATE technician_installations
                    SET status = CASE WHEN %s THEN 'VALIDATED' ELSE status END,
                        validation_report = %s,
                        validated_at = CASE
                            WHEN %s THEN NOW()
                            ELSE validated_at
                        END,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (passed, Jsonb(report), passed, installation_id),
                )
                updated = self._get_installation(
                    cur,
                    installation_id,
                    technician_id,
                )
                return _serialize_installation(updated)

    def hand_over_installation(
        self,
        installation_id: UUID,
        technician_id: UUID,
    ) -> dict[str, Any] | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                row = self._lock_installation(
                    cur,
                    installation_id,
                    technician_id,
                )
                if row is None:
                    return None
                if row[0] != "VALIDATED":
                    raise InstallationStateError(
                        "Installation must pass validation before handover",
                    )

                cur.execute(
                    """
                    UPDATE technician_installations
                    SET status = 'HANDED_OVER',
                        handed_over_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (installation_id,),
                )
                updated = self._get_installation(
                    cur,
                    installation_id,
                    technician_id,
                )
                return _serialize_installation(updated)

    @staticmethod
    def _get_installation(
        cur,
        installation_id: UUID,
        technician_id: UUID,
    ) -> tuple | None:
        cur.execute(
            _INSTALLATION_SELECT
            + f"""
            WHERE ti.id = %s
              AND ti.technician_id = %s
              AND {_ACTIVE_ASSIGNMENT}
            """,
            (installation_id, technician_id),
        )
        return cur.fetchone()

    @staticmethod
    def _lock_installation(
        cur,
        installation_id: UUID,
        technician_id: UUID,
    ) -> tuple | None:
        cur.execute(
            """
            SELECT assignment.id
            FROM technician_assignments AS assignment
            JOIN technician_installations AS ti
              ON ti.farm_id = assignment.farm_id
             AND ti.technician_id = assignment.technician_id
            WHERE ti.id = %s
              AND ti.technician_id = %s
              AND assignment.is_active = TRUE
            FOR SHARE OF assignment
            """,
            (installation_id, technician_id),
        )
        if cur.fetchone() is None:
            return None

        cur.execute(
            f"""
            SELECT ti.status, ti.configuration, d.is_active, d.id
            FROM technician_installations AS ti
            JOIN devices AS d ON d.id = ti.device_id
            WHERE ti.id = %s
              AND ti.technician_id = %s
              AND {_ACTIVE_ASSIGNMENT}
            FOR UPDATE OF ti, d
            """,
            (installation_id, technician_id),
        )
        return cur.fetchone()


technician_installation_repository = TechnicianInstallationRepository()
