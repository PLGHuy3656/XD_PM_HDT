"""Service-private Redis client and frozen key builders for AI Service (CP8.4).

Frozen CP8.0 / CP8.4 Key Namespace:
- `ai:latest:{cameraId}`  — Bounded latest count & detection summary cache
- `ai:runtime:{cameraId}` — Live camera pipeline technical runtime status
"""
from __future__ import annotations

import redis

from app.config import settings

AI_LATEST_KEY_PREFIX = "ai:latest:"
AI_RUNTIME_KEY_PREFIX = "ai:runtime:"


def ai_latest_key(camera_id: str) -> str:
    """Returns canonical Redis key `ai:latest:{cameraId}`."""
    return f"{AI_LATEST_KEY_PREFIX}{camera_id}"


def ai_runtime_key(camera_id: str) -> str:
    """Returns canonical Redis key `ai:runtime:{cameraId}`."""
    return f"{AI_RUNTIME_KEY_PREFIX}{camera_id}"


def get_redis_client(redis_url: str | None = None) -> redis.Redis:
    """Creates a synchronous Redis client with UTF-8 string decoding and bounded socket timeouts."""
    url = redis_url or settings.ai_redis_url
    return redis.Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=1.5,
        socket_timeout=1.5,
    )
