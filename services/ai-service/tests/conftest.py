"""Pytest configuration for services/ai-service."""
from __future__ import annotations

import socket
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parent.parent
AI_PIPELINE_SRC = SERVICE_ROOT.parent.parent / "ai-pipeline" / "src"
REPO_ROOT = SERVICE_ROOT.parent.parent

for p in (SERVICE_ROOT, AI_PIPELINE_SRC, REPO_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import pytest  # noqa: E402
from app.config import settings  # noqa: E402
from app.ports.metadata_resolver import default_camera_metadata_resolver  # noqa: E402
from app.redis_client import AI_LATEST_KEY_PREFIX, AI_RUNTIME_KEY_PREFIX, get_redis_client  # noqa: E402
import app.repositories as repo_pkg  # noqa: E402
import app.repositories.ai_event_repository as ai_event_repo_mod  # noqa: E402
import app.repositories.count_update_repository as count_repo_mod  # noqa: E402
import app.runtime.manager as manager_mod  # noqa: E402
import app.runtime.publisher_sink as publisher_sink_mod  # noqa: E402


def is_port_open(host: str, port: int, timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


POSTGRES_AVAILABLE = is_port_open("127.0.0.1", 5432)
REDIS_AVAILABLE = is_port_open("127.0.0.1", 6379)

if not POSTGRES_AVAILABLE:
    _mem_count_repo = count_repo_mod.InMemoryCountUpdateRepository()
    _mem_event_repo = ai_event_repo_mod.InMemoryAIEventRepository()
    count_repo_mod.default_count_update_repository = _mem_count_repo
    ai_event_repo_mod.default_ai_event_repository = _mem_event_repo
    repo_pkg.default_count_update_repository = _mem_count_repo
    repo_pkg.default_ai_event_repository = _mem_event_repo
    manager_mod.default_count_update_repository = _mem_count_repo
    manager_mod.default_ai_event_repository = _mem_event_repo
    publisher_sink_mod.default_ai_event_repository = _mem_event_repo

if not REDIS_AVAILABLE:
    settings.ai_redis_enabled = False


def _clear_ai_redis_keys() -> None:
    if not REDIS_AVAILABLE:
        return
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
    """Resets durable AI repositories, camera metadata mappings, and Redis keys before and after each test."""
    try:
        repo_pkg.default_count_update_repository.clear()
    except Exception:
        pass
    try:
        repo_pkg.default_ai_event_repository.clear()
    except Exception:
        pass
    default_camera_metadata_resolver._mappings.clear()
    _clear_ai_redis_keys()
    yield
    try:
        repo_pkg.default_count_update_repository.clear()
    except Exception:
        pass
    try:
        repo_pkg.default_ai_event_repository.clear()
    except Exception:
        pass
    default_camera_metadata_resolver._mappings.clear()
    _clear_ai_redis_keys()
