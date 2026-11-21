"""INT03-R1: apply additive, idempotent migrations at startup.

Only files listed in ADDITIVE_MIGRATIONS are applied. Each one uses CREATE ... IF NOT EXISTS only,
so running it against an existing database never drops or rewrites data. A PostgreSQL advisory lock
prevents two replicas from applying the same file concurrently.
"""
import logging
from pathlib import Path

from app.config import settings
from app.database import get_connection

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "database" / "migrations"
ADDITIVE_MIGRATIONS = ("004_add_event_outbox_and_inspection_requests.sql",)
_ADVISORY_LOCK_KEY = 0x5C4E_0004


def apply_additive_migrations() -> list[str]:
    if not settings.auto_apply_additive_migrations or not settings.database_url:
        return []
    applied: list[str] = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s);", (_ADVISORY_LOCK_KEY,))
            try:
                for name in ADDITIVE_MIGRATIONS:
                    sql = (MIGRATIONS_DIR / name).read_text(encoding="utf-8")
                    cur.execute(sql)
                    applied.append(name)
                conn.commit()
            finally:
                cur.execute("SELECT pg_advisory_unlock(%s);", (_ADVISORY_LOCK_KEY,))
                conn.commit()
    logger.info("Additive migrations ensured: %s", ", ".join(applied))
    return applied
