"""Idempotent database provisioning and migration runner for Notification Service (CP8.3)."""
from __future__ import annotations

import logging
import os
from pathlib import Path

import psycopg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("notification_service.migrations")

BASE_DIR = Path(__file__).resolve().parent
MIGRATIONS_DIR = BASE_DIR / "migrations"


def _resolve_admin_dsn() -> str:
    env_dsn = os.getenv("POSTGRES_ADMIN_URL")
    if env_dsn:
        return env_dsn
    mgmt_env = BASE_DIR.parent.parent / "management-service" / ".env"
    if mgmt_env.exists():
        for line in mgmt_env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("LEGACY_IOT_DATABASE_URL="):
                raw = line.split("=", 1)[1].strip().strip('"').strip("'")
                base = raw.rsplit("/", 1)[0]
                return f"{base}/postgres"
            if line.startswith("MANAGEMENT_DATABASE_URL="):
                raw = line.split("=", 1)[1].strip().strip('"').strip("'")
                if "postgres:" in raw:
                    base = raw.rsplit("/", 1)[0]
                    return f"{base}/postgres"
    admin_pw = os.getenv("PGPASSWORD", "")
    return f"postgresql://postgres:{admin_pw}@127.0.0.1:5432/postgres" if admin_pw else "postgresql://postgres@127.0.0.1:5432/postgres"


DEFAULT_ADMIN_DSN = _resolve_admin_dsn()
DEFAULT_NOTIFICATION_DB_DSN = os.getenv(
    "NOTIFICATION_DATABASE_URL",
    "",
)


def provision_database_and_role(admin_dsn: str = DEFAULT_ADMIN_DSN) -> None:
    """Create notification_user (least-privilege) and notification_db if they do not exist."""
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'notification_user'")
            if cur.fetchone() is None:
                logger.info("Creating least-privilege role 'notification_user'...")
                cur.execute(
                    """
                    CREATE ROLE notification_user WITH
                        LOGIN
                        NOSUPERUSER
                        NOCREATEDB
                        NOCREATEROLE
                        NOREPLICATION
                        PASSWORD 'notification_dev_pass_2026'
                    """
                )
            else:
                logger.info("Role 'notification_user' already exists; ensuring least-privilege attributes...")
                cur.execute(
                    """
                    ALTER ROLE notification_user WITH
                        LOGIN
                        NOSUPERUSER
                        NOCREATEDB
                        NOCREATEROLE
                        NOREPLICATION
                        PASSWORD 'notification_dev_pass_2026'
                    """
                )

            cur.execute("SELECT 1 FROM pg_database WHERE datname = 'notification_db'")
            if cur.fetchone() is None:
                logger.info("Creating dedicated database 'notification_db' owned by 'notification_user'...")
                cur.execute("CREATE DATABASE notification_db OWNER notification_user ENCODING 'UTF8'")
            else:
                logger.info("Database 'notification_db' already exists.")
                cur.execute("ALTER DATABASE notification_db OWNER TO notification_user")

            cur.execute("GRANT ALL PRIVILEGES ON DATABASE notification_db TO notification_user")

    # Grant schema privileges inside notification_db
    notification_admin_dsn = admin_dsn.rsplit("/", 1)[0] + "/notification_db"
    with psycopg.connect(notification_admin_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("GRANT ALL ON SCHEMA public TO notification_user")
            cur.execute(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO notification_user"
            )
            cur.execute(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO notification_user"
            )


def apply_migrations(notification_db_dsn: str = DEFAULT_NOTIFICATION_DB_DSN) -> list[str]:
    """Apply all SQL migrations in sorted order as notification_user."""
    applied: list[str] = []
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    with psycopg.connect(notification_db_dsn) as conn:
        with conn.cursor() as cur:
            for sql_file in migration_files:
                logger.info("Applying migration %s...", sql_file.name)
                sql_text = sql_file.read_text(encoding="utf-8")
                cur.execute(sql_text)
                applied.append(sql_file.name)
        conn.commit()

    logger.info("Successfully applied %d migration(s) to notification_db.", len(applied))
    return applied


if __name__ == "__main__":
    provision_database_and_role()
    apply_migrations()
