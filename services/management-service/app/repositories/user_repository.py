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
        """Resolves the parent farm_id for a zone by UUID strictly."""
        if not zone_id or not str(zone_id).strip():
            return None
        import uuid
        zone_id_str = str(zone_id).strip()
        try:
            uuid.UUID(zone_id_str)
        except (ValueError, AttributeError, TypeError):
            return None

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT farm_id
                    FROM zones
                    WHERE id = %s;
                    """,
                    (zone_id_str,),
                )
                row = cur.fetchone()
                return str(row[0]) if row else None

    def resolve_farm_uuid(self, farm_id_or_code: str) -> str | None:
        """
        Resolves a farm identifier (canonical UUID or farm_code) to its canonical UUID.
        Returns None if farm does not exist.
        """
        if not farm_id_or_code or not str(farm_id_or_code).strip():
            return None

        import uuid
        raw_val = str(farm_id_or_code).strip()
        is_uuid = False
        try:
            uuid.UUID(raw_val)
            is_uuid = True
        except (ValueError, AttributeError, TypeError):
            is_uuid = False

        with get_connection() as conn:
            with conn.cursor() as cur:
                if is_uuid:
                    cur.execute(
                        "SELECT id FROM farms WHERE id = %s OR farm_code = %s LIMIT 1;",
                        (raw_val, raw_val),
                    )
                else:
                    cur.execute(
                        "SELECT id FROM farms WHERE farm_code = %s LIMIT 1;",
                        (raw_val,),
                    )
                row = cur.fetchone()
                return str(row[0]) if row else None

    def get_farm_id_for_device(self, device_id: str) -> str | None:
        """Resolves the parent farm_id for a device."""
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
                        SELECT farm_id
                        FROM devices
                        WHERE id = %s OR node_id = %s;
                        """,
                        (dev_id_str, dev_id_str),
                    )
                else:
                    cur.execute(
                        """
                        SELECT farm_id
                        FROM devices
                        WHERE node_id = %s;
                        """,
                        (dev_id_str,),
                    )
                row = cur.fetchone()
                return str(row[0]) if row else None


    def farm_exists(self, farm_id: str) -> bool:
        """Checks if a farm exists by id (UUID) or farm_code."""
        if not farm_id or not str(farm_id).strip():
            return False

        import uuid
        farm_id_str = str(farm_id).strip()
        is_uuid = False
        try:
            uuid.UUID(farm_id_str)
            is_uuid = True
        except (ValueError, AttributeError, TypeError):
            is_uuid = False

        with get_connection() as conn:
            with conn.cursor() as cur:
                if is_uuid:
                    cur.execute(
                        "SELECT 1 FROM farms WHERE id = %s OR farm_code = %s LIMIT 1;",
                        (farm_id_str, farm_id_str),
                    )
                else:
                    cur.execute(
                        "SELECT 1 FROM farms WHERE farm_code = %s LIMIT 1;",
                        (farm_id_str,),
                    )
                return cur.fetchone() is not None


    def list_users(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """Lists all users with their assigned roles."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.id, u.email, u.full_name, u.phone, u.status, u.created_at, u.updated_at,
                           COALESCE(array_agg(r.name) FILTER (WHERE r.name IS NOT NULL), '{}') as roles
                    FROM users u
                    LEFT JOIN user_roles ur ON ur.user_id = u.id
                    LEFT JOIN roles r ON r.id = ur.role_id
                    GROUP BY u.id, u.email, u.full_name, u.phone, u.status, u.created_at, u.updated_at
                    ORDER BY u.created_at DESC
                    LIMIT %s OFFSET %s;
                    """,
                    (limit, offset),
                )
                rows = cur.fetchall()

        return [
            {
                "id": str(r[0]),
                "email": r[1],
                "full_name": r[2],
                "phone": r[3],
                "status": r[4],
                "created_at": r[5],
                "updated_at": r[6],
                "roles": list(r[7]),
            }
            for r in rows
        ]

    def create_user(
        self,
        email: str,
        password_hash: str,
        full_name: str,
        phone: str | None = None,
        role: str = "FARM_OWNER",
        status: str = "ACTIVE",
    ) -> dict:
        """Creates a new user and assigns the initial role."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (email, password_hash, full_name, phone, status)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, email, full_name, phone, status, created_at, updated_at;
                    """,
                    (email, password_hash, full_name, phone, status),
                )
                row = cur.fetchone()
                user_id = str(row[0])

                # Assign role
                cur.execute("SELECT id FROM roles WHERE name = %s;", (role,))
                role_row = cur.fetchone()
                if role_row:
                    role_id = role_row[0]
                    cur.execute(
                        "INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
                        (user_id, role_id),
                    )

                # If technician, initialize technician profile
                if role == "TECHNICIAN":
                    cur.execute(
                        """
                        INSERT INTO technicians (id, full_name, email, phone, status)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE
                        SET full_name = EXCLUDED.full_name, phone = EXCLUDED.phone, status = EXCLUDED.status;
                        """,
                        (user_id, full_name, email, phone, status),
                    )

                conn.commit()

        return {
            "id": user_id,
            "email": row[1],
            "full_name": row[2],
            "phone": row[3],
            "status": row[4],
            "roles": [role],
            "created_at": row[5],
            "updated_at": row[6],
        }

    def update_user(
        self,
        user_id: str,
        full_name: str | None = None,
        phone: str | None = None,
        status: str | None = None,
        role: str | None = None,
    ) -> dict | None:
        """Updates user profile details and role."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Update users table
                updates = []
                params = []
                if full_name is not None:
                    updates.append("full_name = %s")
                    params.append(full_name)
                if phone is not None:
                    updates.append("phone = %s")
                    params.append(phone)
                if status is not None:
                    updates.append("status = %s")
                    params.append(status)

                if updates:
                    updates.append("updated_at = NOW()")
                    params.append(user_id)
                    cur.execute(
                        f"UPDATE users SET {', '.join(updates)} WHERE id = %s;",
                        params,
                    )

                # Update role if specified
                if role is not None:
                    cur.execute("SELECT id FROM roles WHERE name = %s;", (role,))
                    role_row = cur.fetchone()
                    if role_row:
                        role_id = role_row[0]
                        cur.execute("DELETE FROM user_roles WHERE user_id = %s;", (user_id,))
                        cur.execute(
                            "INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s);",
                            (user_id, role_id),
                        )
                        if role == "TECHNICIAN":
                            cur.execute(
                                """
                                INSERT INTO technicians (id, full_name, email, phone, status)
                                SELECT id, full_name, email, phone, status FROM users WHERE id = %s
                                ON CONFLICT (id) DO UPDATE SET full_name = EXCLUDED.full_name, status = EXCLUDED.status;
                                """,
                                (user_id,),
                            )

                conn.commit()

        return self.get_user_by_id(user_id)

    def update_user_status(self, user_id: str, status: str) -> bool:
        """Updates user account status (ACTIVE, LOCKED, INACTIVE)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET status = %s, updated_at = NOW() WHERE id = %s;",
                    (status, user_id),
                )
                updated = cur.rowcount > 0
                if updated:
                    # Sync to technicians table if technician
                    cur.execute("UPDATE technicians SET status = %s, updated_at = NOW() WHERE id = %s;", (status, user_id))
                conn.commit()
        return updated

    def delete_user(self, user_id: str) -> bool:
        """Deletes user permanently."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE id = %s;", (user_id,))
                deleted = cur.rowcount > 0
                conn.commit()
        return deleted


user_repository = UserRepository()
