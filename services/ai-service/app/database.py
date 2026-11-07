"""Database connection helper for AI Service durable persistence (CP8.2 — ai_db)."""
from __future__ import annotations

import os
import psycopg

from app.config import settings


def get_database_url(override_url: str | None = None) -> str:
    """Resolves the target AI PostgreSQL connection URL."""
    url = override_url if override_url is not None else (os.getenv("AI_DATABASE_URL") or settings.ai_database_url)
    if not url:
        raise ValueError("AI_DATABASE_URL is not configured")
    return url


def get_connection(database_url: str | None = None, connect_timeout: int = 5) -> psycopg.Connection:
    """Opens a new PostgreSQL connection to ai_db with explicit timeout."""
    url = get_database_url(database_url)
    return psycopg.connect(url, connect_timeout=connect_timeout)


__all__ = ["get_connection", "get_database_url"]
