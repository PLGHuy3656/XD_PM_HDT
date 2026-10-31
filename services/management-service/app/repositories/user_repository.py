from app.database import get_connection


class UserRepository:
    def get_user_by_email(self, email: str) -> dict | None:
        """Retrieves a user and their assigned roles by email."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, email, password_hash, full_name, phone, status
                    FROM users
                    WHERE email = %s;
                    """,
                    (email,),
                )
                user_row = cur.fetchone()

                if not user_row:
                    return None

                user_id = str(user_row[0])
                cur.execute(
                    """
                    SELECT r.name
                    FROM user_roles ur
                    JOIN roles r ON r.id = ur.role_id
                    WHERE ur.user_id = %s;
                    """,
                    (user_id,),
                )
                roles = [r[0] for r in cur.fetchall()]

        return {
            "id": user_id,
            "email": user_row[1],
            "password_hash": user_row[2],
            "full_name": user_row[3],
            "phone": user_row[4],
            "status": user_row[5],
            "roles": roles,
        }

    def get_user_by_id(self, user_id: str) -> dict | None:
        """Retrieves a user and their assigned roles by UUID."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, email, password_hash, full_name, phone, status
                    FROM users
                    WHERE id = %s;
                    """,
                    (user_id,),
                )
                user_row = cur.fetchone()

                if not user_row:
                    return None

                cur.execute(
                    """
                    SELECT r.name
                    FROM user_roles ur
                    JOIN roles r ON r.id = ur.role_id
                    WHERE ur.user_id = %s;
                    """,
                    (user_id,),
                )
                roles = [r[0] for r in cur.fetchall()]

        return {
            "id": str(user_row[0]),
            "email": user_row[1],
            "password_hash": user_row[2],
            "full_name": user_row[3],
            "phone": user_row[4],
            "status": user_row[5],
            "roles": roles,
        }

    def update_password_hash(self, user_id: str, password_hash: str) -> bool:
        """Updates the password hash for a user."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE users
                    SET password_hash = %s, updated_at = NOW()
                    WHERE id = %s;
                    """,
                    (password_hash, user_id),
                )
                updated = cur.rowcount > 0
                conn.commit()
        return updated

    def is_farm_assigned_to_technician(self, technician_id: str, farm_id: str) -> bool:
        """
        Verifies if a farm is actively assigned to the technician.
        Resolves by farm UUID or farm_code.
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM technician_assignments ta
                    JOIN farms f ON f.id = ta.farm_id
                    WHERE ta.technician_id = %s
                      AND (ta.farm_id::text = %s OR f.farm_code = %s)
                      AND ta.is_active = TRUE;
                    """,
                    (technician_id, farm_id, farm_id),
                )
                return cur.fetchone() is not None

    def is_farm_owned_by_user(self, user_id: str, farm_id: str) -> bool:
        """
        Verifies if a farm is owned by the user.
        Queries authoritative management_db.farms.owner_id column directly.
        Returns False if farm does not exist, owner_id is NULL, or owned by another user.
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM farms
                    WHERE (id::text = %s OR farm_code = %s)
                      AND owner_id IS NOT NULL
                      AND owner_id::text = %s;
                    """,
                    (farm_id, farm_id, user_id),
                )
                return cur.fetchone() is not None

    def get_farm_id_for_zone(self, zone_id: str) -> str | None:
        """Resolves the parent farm_id for a zone."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT farm_id
                    FROM zones
                    WHERE id::text = %s OR zone_code = %s;
                    """,
                    (zone_id, zone_id),
                )
                row = cur.fetchone()
                return str(row[0]) if row else None

    def get_farm_id_for_device(self, device_id: str) -> str | None:
        """Resolves the parent farm_id for a device."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT farm_id
                    FROM devices
                    WHERE id::text = %s OR node_id = %s;
                    """,
                    (device_id, device_id),
                )
                row = cur.fetchone()
                return str(row[0]) if row else None


user_repository = UserRepository()
