"""Database provisioning and migration runner for AI Service (CP8.2).

Applies SQL migrations in services/ai-service/database/migrations/ to ai_db.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
import psycopg

SERVICE_ROOT = Path(__file__).resolve().parent.parent
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))


def provision_ai_database(admin_url: str, ai_password: str = "ai_dev_pass_2026") -> None:
    """Provisions ai_user and ai_db using superuser connection if not already present."""
    with psycopg.connect(admin_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", ("ai_user",))
            if not cur.fetchone():
                cur.execute(
                    f"CREATE ROLE ai_user WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT PASSWORD '{ai_password}'"
                )
            else:
                cur.execute(
                    f"ALTER ROLE ai_user WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT PASSWORD '{ai_password}'"
                )

            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", ("ai_db",))
            if not cur.fetchone():
                cur.execute("CREATE DATABASE ai_db OWNER ai_user")
            cur.execute("REVOKE ALL ON DATABASE ai_db FROM PUBLIC")
            cur.execute("GRANT CONNECT, TEMPORARY ON DATABASE ai_db TO ai_user")

    ai_admin_url = admin_url.rsplit("/", 1)[0] + "/ai_db"
    with psycopg.connect(ai_admin_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
            cur.execute("GRANT USAGE, CREATE ON SCHEMA public TO ai_user")
            cur.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ai_user")
            cur.execute("GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO ai_user")
            cur.execute(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ai_user"
            )
            cur.execute(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO ai_user"
            )


def apply_migrations(database_url: str | None = None) -> list[str]:
    """Applies all SQL migration files in alphabetical order to the target AI database."""
    if not database_url:
        from app.config import settings
        database_url = os.getenv("AI_DATABASE_URL") or settings.ai_database_url

    if not database_url:
        raise ValueError("AI_DATABASE_URL is required to apply AI migrations")

    migrations_dir = Path(__file__).resolve().parent / "migrations"
    migration_files = sorted(migrations_dir.glob("*.sql"))
    applied: list[str] = []

    with psycopg.connect(database_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            for mig_file in migration_files:
                sql = mig_file.read_text(encoding="utf-8")
                cur.execute(sql)
                applied.append(mig_file.name)

    return applied


if __name__ == "__main__":
    from dotenv import dotenv_values
    mgmt_env = SERVICE_ROOT.parent / "management-service" / ".env"
    if mgmt_env.exists():
        env_vals = dotenv_values(mgmt_env)
        admin_conn_url = env_vals.get("LEGACY_IOT_DATABASE_URL")
        if admin_conn_url:
            provision_ai_database(admin_conn_url)
    applied_files = apply_migrations()
    print(f"[INFO] Applied AI migrations: {applied_files}")
