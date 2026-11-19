"""PostgreSQL durable repository for UserDevice FCM push token registrations (CP8.3)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

import psycopg

from app.database import get_connection
from app.domain.enums import DevicePlatform
from app.ports.user_device_repository import UserDeviceRepository
from app.schemas.canonical import UserDevice

logger = logging.getLogger("notification_service.repositories.user_device")


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _row_to_user_device(row: tuple[Any, ...]) -> UserDevice:
    return UserDevice(
        device_id=row[0],
        user_id=row[1],
        fcm_token=row[2],
        platform=DevicePlatform(row[3]),
        device_name=row[4],
        is_enabled=bool(row[5]),
        created_at=_ensure_utc(row[6]),
        updated_at=_ensure_utc(row[7]),
    )


_SELECT_COLUMNS = """
    device_id,
    user_id,
    fcm_token,
    platform,
    device_name,
    is_enabled,
    created_at,
    updated_at
"""


class PostgreSQLUserDeviceRepository(UserDeviceRepository):
    """Durable PostgreSQL implementation of UserDeviceRepository backed by `notification_db.user_devices`."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        self._database_url = database_url

    def _connect(self) -> psycopg.Connection:
        return get_connection(self._database_url)

    def register_device(self, device: UserDevice) -> UserDevice:
        """Register or refresh a user device push token with global token uniqueness."""
        now = datetime.now(timezone.utc)
        created_at = _ensure_utc(device.created_at) or now
        updated_at = now

        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    # Enforce global fcm_token uniqueness across different device_id registrations
                    cur.execute(
                        "DELETE FROM user_devices WHERE fcm_token = %s AND device_id <> %s",
                        (device.fcm_token, device.device_id),
                    )
                    cur.execute(
                        f"""
                        INSERT INTO user_devices (
                            device_id,
                            user_id,
                            fcm_token,
                            platform,
                            device_name,
                            is_enabled,
                            created_at,
                            updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (device_id) DO UPDATE SET
                            user_id = EXCLUDED.user_id,
                            fcm_token = EXCLUDED.fcm_token,
                            platform = EXCLUDED.platform,
                            device_name = EXCLUDED.device_name,
                            is_enabled = EXCLUDED.is_enabled,
                            updated_at = EXCLUDED.updated_at
                        RETURNING {_SELECT_COLUMNS}
                        """,
                        (
                            device.device_id,
                            device.user_id,
                            device.fcm_token,
                            device.platform.value,
                            device.device_name,
                            device.is_enabled,
                            created_at,
                            updated_at,
                        ),
                    )
                    row = cur.fetchone()
                conn.commit()
            assert row is not None
            return _row_to_user_device(row)
        except Exception as exc:
            logger.error(
                "[NOTIFICATION USER DEVICE PERSISTENCE FAILED] Failed to register UserDevice deviceId='%s' userId='%s': %s",
                device.device_id,
                device.user_id,
                exc,
            )
            raise

    def get_by_id(self, device_id: str) -> Optional[UserDevice]:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT {_SELECT_COLUMNS} FROM user_devices WHERE device_id = %s",
                        (device_id,),
                    )
                    row = cur.fetchone()
                    return _row_to_user_device(row) if row is not None else None
        except Exception as exc:
            logger.error(
                "[NOTIFICATION USER DEVICE QUERY FAILED] Failed to query UserDevice deviceId='%s': %s",
                device_id,
                exc,
            )
            raise

    def get_by_token(self, fcm_token: str) -> Optional[UserDevice]:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT {_SELECT_COLUMNS} FROM user_devices WHERE fcm_token = %s",
                        (fcm_token,),
                    )
                    row = cur.fetchone()
                    return _row_to_user_device(row) if row is not None else None
        except Exception as exc:
            logger.error("[NOTIFICATION USER DEVICE TOKEN QUERY FAILED] Failed to query token: %s", exc)
            raise

    def list_by_user(
        self,
        user_id: str,
        is_enabled_only: bool = True,
    ) -> List[UserDevice]:
        clauses = ["user_id = %s"]
        params: list[Any] = [user_id]
        if is_enabled_only:
            clauses.append("is_enabled = TRUE")

        where_sql = " AND ".join(clauses)

        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT {_SELECT_COLUMNS}
                        FROM user_devices
                        WHERE {where_sql}
                        ORDER BY created_at ASC, device_id ASC
                        """,
                        tuple(params),
                    )
                    rows = cur.fetchall()
                    return [_row_to_user_device(r) for r in rows]
        except Exception as exc:
            logger.error(
                "[NOTIFICATION USER DEVICE LIST FAILED] Failed to list UserDevices for userId='%s': %s",
                user_id,
                exc,
            )
            raise

    def disable_device(self, device_id: str) -> Optional[UserDevice]:
        now = datetime.now(timezone.utc)
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        UPDATE user_devices
                        SET is_enabled = FALSE,
                            updated_at = %s
                        WHERE device_id = %s
                        RETURNING {_SELECT_COLUMNS}
                        """,
                        (now, device_id),
                    )
                    row = cur.fetchone()
                conn.commit()
            return _row_to_user_device(row) if row is not None else None
        except Exception as exc:
            logger.error(
                "[NOTIFICATION USER DEVICE DISABLE FAILED] Failed to disable UserDevice deviceId='%s': %s",
                device_id,
                exc,
            )
            raise

    def disable_by_token(self, fcm_token: str) -> Optional[UserDevice]:
        now = datetime.now(timezone.utc)
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        UPDATE user_devices
                        SET is_enabled = FALSE,
                            updated_at = %s
                        WHERE fcm_token = %s
                        RETURNING {_SELECT_COLUMNS}
                        """,
                        (now, fcm_token),
                    )
                    row = cur.fetchone()
                conn.commit()
            return _row_to_user_device(row) if row is not None else None
        except Exception as exc:
            logger.error("[NOTIFICATION USER DEVICE TOKEN DISABLE FAILED] Failed to disable token: %s", exc)
            raise

    def delete_device(self, device_id: str) -> bool:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM user_devices WHERE device_id = %s", (device_id,))
                    deleted = cur.rowcount > 0
                conn.commit()
            return deleted
        except Exception as exc:
            logger.error(
                "[NOTIFICATION USER DEVICE DELETE FAILED] Failed to delete UserDevice deviceId='%s': %s",
                device_id,
                exc,
            )
            raise


__all__ = ["PostgreSQLUserDeviceRepository"]
