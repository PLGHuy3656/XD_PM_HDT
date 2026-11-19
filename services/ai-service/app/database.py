"""Database connection helper for AI Service durable persistence (CP8.2 â€” ai_db)."""
from __future__ import annotations

import os
from urllib.parse import urlparse

import psycopg

from app.config import settings

# CP13 hardening R4: destructive test helpers (full-table clears) may only run on
# databases whose name is in this allowlist. Extend via AI_TEST_DB_ALLOWLIST
# (comma-separated). Main databases (ai_db, ...) are never allowed.
_DEFAULT_TEST_DB_ALLOWLIST = ("ai_test_db",)
_NEVER_TEST_DATABASES = frozenset({"ai_db", "management_db", "iot_db", "notification_db", "analytics_db", "postgres", "swiftletcare"})


def get_database_url(override_url: str | None = None) -> str:
    """Resolves the target AI PostgreSQL connection URL."""
    url = override_url if override_url is not None else (os.getenv("AI_DATABASE_URL") or settings.ai_database_url)
    if not url:
        raise ValueError("AI_DATABASE_URL is not configured")
    return url


def database_name(url: str) -> str:
    """Returns the database name of a postgresql:// URL (lower-cased)."""
    return (urlparse(url).path or "").lstrip("/").split("?")[0].strip().lower()


def allowed_test_databases() -> frozenset[str]:
    extra = [x.strip().lower() for x in os.getenv("AI_TEST_DB_ALLOWLIST", "").split(",") if x.strip()]
    return frozenset(_DEFAULT_TEST_DB_ALLOWLIST) | (frozenset(extra) - _NEVER_TEST_DATABASES)


def is_test_database_url(url: str | None) -> bool:
    if not url:
        return False
    return database_name(url) in allowed_test_databases()


def assert_test_database(url: str | None) -> None:
    """Raises RuntimeError unless url points to an allowlisted test database."""
    if not is_test_database_url(url):
        raise RuntimeError(
            "Refusing destructive operation: target database is not an allowlisted test database "
            f"(got '{database_name(url) if url else ''}', allowed {sorted(allowed_test_databases())})"
        )


def get_connection(database_url: str | None = None, connect_timeout: int = 5) -> psycopg.Connection:
    """Opens a new PostgreSQL connection to ai_db with explicit timeout."""
    url = get_database_url(database_url)
    return psycopg.connect(url, connect_timeout=connect_timeout)


__all__ = [
    "assert_test_database",
    "database_name",
    "get_connection",
    "get_database_url",
    "is_test_database_url",
    "allowed_test_databases",
]
