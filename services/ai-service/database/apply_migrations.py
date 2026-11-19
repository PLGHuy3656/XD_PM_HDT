"""Database migration runner for AI Service (CP8.2).

Applies SQL migrations in services/ai-service/database/migrations/ to ai_db
with replay safety tracked via the `schema_migrations` table.

Role/database provisioning is intentionally separated into `provision_db.py`
so migrations never require superuser privileges or touch other services' `.env` files.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
import psycopg

SERVICE_ROOT = Path(__file__).resolve().parent.parent
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

_ENSURE_TRACKING_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(64) PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def apply_migrations(database_url: str | None = None) -> list[str]:
    """Applies unapplied SQL migration files in alphabetical order to `ai_db`.

    Checks `schema_migrations` before executing each file so re-running migrations
    is idempotent and replay-safe.
    """
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
            cur.execute(_ENSURE_TRACKING_TABLE_SQL)
            cur.execute("SELECT version FROM schema_migrations")
            existing_versions = {row[0] for row in cur.fetchall()}

            for mig_file in migration_files:
                version = mig_file.stem
                if version in existing_versions:
                    continue
                sql = mig_file.read_text(encoding="utf-8")
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations (version, description) "
                    "VALUES (%s, %s) ON CONFLICT (version) DO NOTHING",
                    (version, f"Applied {mig_file.name}"),
                )
                existing_versions.add(version)
                applied.append(mig_file.name)

    return applied


if __name__ == "__main__":
    applied_files = apply_migrations()
    print(f"[INFO] Applied AI migrations: {applied_files}")
