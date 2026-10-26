"""
Database Migration Script for Management Service (Checkpoint 3)
Copies management-owned data from legacy 'swiftletcare' database to 'management_db'.

PRINCIPLES:
1. READ-ONLY on legacy 'swiftletcare' database.
2. Idempotent insertion into 'management_db'.
3. NO password guessing or mock passwords for users (password_hash is NULL).
4. Strictly NO cross-database JOINs.
"""

import os
import sys
from pathlib import Path
import psycopg

# Ensure services/management-service is on sys.path to access app.config
SERVICE_ROOT = Path(__file__).resolve().parent.parent
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.config import settings

LEGACY_DB_URL = os.getenv("LEGACY_DATABASE_URL") or settings.legacy_iot_database_url
MANAGEMENT_DB_URL = os.getenv("DATABASE_URL") or settings.database_url


def apply_schema(mgmt_conn):
    schema_path = Path(__file__).parent / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")
    with mgmt_conn.cursor() as cur:
        cur.execute(sql)
    mgmt_conn.commit()
    print("[INFO] Applied schema.sql to management_db successfully.")


def migrate_data():
    if not LEGACY_DB_URL:
        raise ValueError("LEGACY_DATABASE_URL or settings.legacy_iot_database_url is required")
    if not MANAGEMENT_DB_URL:
        raise ValueError("DATABASE_URL or settings.database_url is required")

    print("[INFO] Connecting to legacy DB...")
    print("[INFO] Connecting to target DB...")

    with psycopg.connect(LEGACY_DB_URL) as legacy_conn, psycopg.connect(MANAGEMENT_DB_URL) as mgmt_conn:
        # Step 1: Ensure schema is applied
        apply_schema(mgmt_conn)

        with legacy_conn.cursor() as leg_cur, mgmt_conn.cursor() as mgmt_cur:
            # 1. Migrate Houses -> Farms
            print("[INFO] Migrating houses -> farms...")
            leg_cur.execute("SELECT id, house_code, name, created_at FROM public.houses;")
            houses = leg_cur.fetchall()
            for h in houses:
                mgmt_cur.execute(
                    """
                    INSERT INTO farms (id, farm_code, name, status, created_at, updated_at)
                    VALUES (%s, %s, %s, 'ACTIVE', %s, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        farm_code = EXCLUDED.farm_code,
                        name = EXCLUDED.name,
                        updated_at = NOW();
                    """,
                    (h[0], h[1], h[2], h[3]),
                )
            print(f"[INFO] Migrated {len(houses)} farms.")

            # 2. Migrate Zones
            print("[INFO] Migrating zones...")
            leg_cur.execute("SELECT id, house_id, zone_code, name, created_at FROM public.zones;")
            zones = leg_cur.fetchall()
            for z in zones:
                mgmt_cur.execute(
                    """
                    INSERT INTO zones (id, farm_id, zone_code, name, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        farm_id = EXCLUDED.farm_id,
                        zone_code = EXCLUDED.zone_code,
                        name = EXCLUDED.name,
                        updated_at = NOW();
                    """,
                    (z[0], z[1], z[2], z[3], z[4]),
                )
            print(f"[INFO] Migrated {len(zones)} zones.")

            # 3. Migrate Devices (Metadata / Registry)
            print("[INFO] Migrating devices...")
            leg_cur.execute(
                """
                SELECT id, node_id, house_id, zone_id, name, device_type, firmware_version, ip_address, is_active, created_at
                FROM public.devices;
                """
            )
            devices = leg_cur.fetchall()
            for d in devices:
                mgmt_cur.execute(
                    """
                    INSERT INTO devices (id, node_id, farm_id, zone_id, name, device_type, firmware_version, ip_address, is_active, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        node_id = EXCLUDED.node_id,
                        farm_id = EXCLUDED.farm_id,
                        zone_id = EXCLUDED.zone_id,
                        name = EXCLUDED.name,
                        device_type = EXCLUDED.device_type,
                        firmware_version = EXCLUDED.firmware_version,
                        ip_address = EXCLUDED.ip_address,
                        is_active = EXCLUDED.is_active,
                        updated_at = NOW();
                    """,
                    (d[0], d[1], d[2], d[3], d[4], d[5] or "ENVIRONMENT_MONITOR", d[6], d[7], d[8], d[9]),
                )
            print(f"[INFO] Migrated {len(devices)} devices.")

            # 4. Migrate Technicians -> Users, User_Roles, Technicians
            # TODO(MANAGEMENT-IDENTITY):
            # Technicians are migrated into the unified 'users' table with TECHNICIAN role.
            # Notice password_hash is deliberately set to NULL because legacy backend never had credentials.
            # Initial credentials must be provisioned via an administrative onboarding or password reset workflow,
            # avoiding any mock or hardcoded credentials.
            print("[INFO] Migrating technicians -> users, user_roles, technicians...")
            # Fetch TECHNICIAN role ID
            mgmt_cur.execute("SELECT id FROM roles WHERE name = 'TECHNICIAN';")
            role_row = mgmt_cur.fetchone()
            if not role_row:
                raise RuntimeError("TECHNICIAN role not found in roles table")
            tech_role_id = role_row[0]

            leg_cur.execute("SELECT id, full_name, email, phone, status, created_at FROM public.technicians;")
            technicians = leg_cur.fetchall()
            for t in technicians:
                # Insert into users (password_hash is explicitly NULL, preserving integrity)
                mgmt_cur.execute(
                    """
                    INSERT INTO users (id, email, password_hash, full_name, phone, status, created_at, updated_at)
                    VALUES (%s, %s, NULL, %s, %s, %s, %s, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        email = EXCLUDED.email,
                        full_name = EXCLUDED.full_name,
                        phone = EXCLUDED.phone,
                        status = EXCLUDED.status,
                        updated_at = NOW();
                    """,
                    (t[0], t[2], t[1], t[3], t[4] or "ACTIVE", t[5]),
                )

                # Link user to TECHNICIAN role
                mgmt_cur.execute(
                    """
                    INSERT INTO user_roles (user_id, role_id, assigned_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (user_id, role_id) DO NOTHING;
                    """,
                    (t[0], tech_role_id),
                )

                # Insert into technicians
                mgmt_cur.execute(
                    """
                    INSERT INTO technicians (id, full_name, email, phone, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        full_name = EXCLUDED.full_name,
                        email = EXCLUDED.email,
                        phone = EXCLUDED.phone,
                        status = EXCLUDED.status,
                        updated_at = NOW();
                    """,
                    (t[0], t[1], t[2], t[3], t[4] or "ACTIVE", t[5]),
                )
            print(f"[INFO] Migrated {len(technicians)} technicians.")

            # 5. Migrate Technician House Assignments -> Technician Assignments
            print("[INFO] Migrating technician_house_assignments -> technician_assignments...")
            leg_cur.execute(
                """
                SELECT id, technician_id, house_id, is_primary, is_active, assigned_at
                FROM public.technician_house_assignments;
                """
            )
            assignments = leg_cur.fetchall()
            for a in assignments:
                mgmt_cur.execute(
                    """
                    INSERT INTO technician_assignments (id, technician_id, farm_id, is_primary, is_active, assigned_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (technician_id, farm_id) DO UPDATE SET
                        is_primary = EXCLUDED.is_primary,
                        is_active = EXCLUDED.is_active,
                        assigned_at = EXCLUDED.assigned_at;
                    """,
                    (a[0], a[1], a[2], a[3], a[4], a[5]),
                )
            print(f"[INFO] Migrated {len(assignments)} technician assignments.")

            # Commit all changes to management_db
            mgmt_conn.commit()

            # Verification of Row Counts
            print("\n=== VERIFICATION OF ROW COUNTS ===")
            mgmt_cur.execute("SELECT COUNT(*) FROM farms;")
            m_farms = mgmt_cur.fetchone()[0]
            assert m_farms == len(houses), f"Farms count mismatch: {m_farms} != {len(houses)}"
            print(f"[VERIFIED] farms: {m_farms} (source houses: {len(houses)})")

            mgmt_cur.execute("SELECT COUNT(*) FROM zones;")
            m_zones = mgmt_cur.fetchone()[0]
            assert m_zones == len(zones), f"Zones count mismatch: {m_zones} != {len(zones)}"
            print(f"[VERIFIED] zones: {m_zones} (source zones: {len(zones)})")

            mgmt_cur.execute("SELECT COUNT(*) FROM devices;")
            m_devices = mgmt_cur.fetchone()[0]
            assert m_devices == len(devices), f"Devices count mismatch: {m_devices} != {len(devices)}"
            print(f"[VERIFIED] devices: {m_devices} (source devices: {len(devices)})")

            mgmt_cur.execute("SELECT COUNT(*) FROM technicians;")
            m_techs = mgmt_cur.fetchone()[0]
            assert m_techs == len(technicians), f"Technicians count mismatch: {m_techs} != {len(technicians)}"
            print(f"[VERIFIED] technicians: {m_techs} (source technicians: {len(technicians)})")

            mgmt_cur.execute("SELECT COUNT(*) FROM technician_assignments;")
            m_assigns = mgmt_cur.fetchone()[0]
            assert m_assigns == len(assignments), f"Assignments count mismatch: {m_assigns} != {len(assignments)}"
            print(f"[VERIFIED] technician_assignments: {m_assigns} (source assignments: {len(assignments)})")

            mgmt_cur.execute("SELECT COUNT(*) FROM users;")
            m_users = mgmt_cur.fetchone()[0]
            print(f"[VERIFIED] users: {m_users}")

            mgmt_cur.execute("SELECT COUNT(*) FROM roles;")
            m_roles = mgmt_cur.fetchone()[0]
            print(f"[VERIFIED] roles: {m_roles}")

    print("\n[SUCCESS] Migration from legacy database completed successfully!")


if __name__ == "__main__":
    migrate_data()
