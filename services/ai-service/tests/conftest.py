"""Pytest configuration for services/ai-service."""
from __future__ import annotations

import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parent.parent
AI_PIPELINE_SRC = SERVICE_ROOT.parent.parent / "ai-pipeline" / "src"

if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

if str(AI_PIPELINE_SRC) not in sys.path:
    sys.path.insert(0, str(AI_PIPELINE_SRC))

import os  # noqa: E402

import pytest  # noqa: E402

# CP13 hardening R4: fail fast unless tests target an allowlisted test database.
# Several fixtures/tests perform full-table clears; they must never touch ai_db.
from app.config import settings as _settings  # noqa: E402
from app.database import allowed_test_databases, database_name, is_test_database_url  # noqa: E402

_TARGET_DB_URL = os.getenv("AI_DATABASE_URL") or _settings.ai_database_url
if _TARGET_DB_URL and not is_test_database_url(_TARGET_DB_URL):
    pytest.exit(
        "Refusing to run ai-service tests against non-test database "
        f"'{database_name(_TARGET_DB_URL)}'. Set AI_DATABASE_URL to one of "
        f"{sorted(allowed_test_databases())}; note services/ai-service/.env is used when it is unset.",
        returncode=2,
    )
from app.redis_client import AI_LATEST_KEY_PREFIX, AI_RUNTIME_KEY_PREFIX, get_redis_client  # noqa: E402
from app.repositories import (  # noqa: E402
    default_ai_event_repository,
    default_count_update_repository,
)


def _clear_ai_redis_keys() -> None:
    try:
        client = get_redis_client()
        keys = [
            *client.keys(f"{AI_LATEST_KEY_PREFIX}*"),
            *client.keys(f"{AI_RUNTIME_KEY_PREFIX}*"),
        ]
        if keys:
            client.delete(*keys)
    except Exception:
        pass


@pytest.fixture(autouse=True)
def clean_ai_repositories():
    """Resets durable AI repositories and Redis runtime/cache keys before and after each test."""
    default_count_update_repository.clear()
    default_ai_event_repository.clear()
    _clear_ai_redis_keys()
    yield
    default_count_update_repository.clear()
    default_ai_event_repository.clear()
    _clear_ai_redis_keys()
