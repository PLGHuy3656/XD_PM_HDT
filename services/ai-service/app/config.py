"""Configuration and path bootstrap for the AI Service reference prototype."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SERVICE_DIR.parent.parent
AI_PIPELINE_DIR = REPO_ROOT / "ai-pipeline"
AI_PIPELINE_SRC = AI_PIPELINE_DIR / "src"

if str(AI_PIPELINE_SRC) not in sys.path:
    sys.path.insert(0, str(AI_PIPELINE_SRC))

from swiftletcare_ai.config import (  # noqa: E402
    CameraConfig,
    Cfg,
    load_pipeline_config,
    load_yaml,
    resolve_path,
)


@dataclass(frozen=True)
class RuntimeCameraConfig:
    """Camera configuration consumed by CameraPipeline.

    Note: Management Service remains the authoritative source of truth for
    camera registration, name, farmId, and zoneId. AI Service only consumes
    configured identifiers and owns runtime/inference state.
    """

    camera_id: str
    source: Any
    source_type: str = "auto"
    line: Tuple[Tuple[float, float], Tuple[float, float]] = ((0.1, 0.55), (0.9, 0.55))
    inside_side: str = "positive"
    farm_id: Optional[str] = None
    zone_id: Optional[str] = None

    @classmethod
    def from_tv2_camera_config(
        cls,
        cam: CameraConfig,
        farm_id: Optional[str] = None,
        zone_id: Optional[str] = None,
    ) -> "RuntimeCameraConfig":
        return cls(
            camera_id=cam.camera_id,
            source=cam.source,
            source_type=cam.source_type,
            line=cam.line,
            inside_side=cam.inside_side,
            farm_id=farm_id,
            zone_id=zone_id,
        )


def load_runtime_cameras(path: str | Path) -> List[RuntimeCameraConfig]:
    """Load camera configurations from YAML, supporting optional farm_id / zone_id."""
    data = load_yaml(path)
    out: List[RuntimeCameraConfig] = []
    seen: set[str] = set()
    for c in data.get("cameras", []):
        cid = str(c["camera_id"]).strip()
        if not cid:
            raise ValueError("camera_id must not be empty")
        if cid in seen:
            raise ValueError(f"Duplicate camera_id: {cid}")
        seen.add(cid)
        ln = c.get("counting_line", {})
        line = (
            tuple(ln.get("start", (0.1, 0.55))),
            tuple(ln.get("end", (0.9, 0.55))),
        )
        out.append(
            RuntimeCameraConfig(
                camera_id=cid,
                source=c["source"],
                source_type=c.get("source_type", "auto"),
                line=line,  # type: ignore[arg-type]
                inside_side=c.get("inside_side", "positive"),
                farm_id=c.get("farm_id") or c.get("farmId"),
                zone_id=c.get("zone_id") or c.get("zoneId"),
            )
        )
    return out


class Settings(BaseSettings):
    """Runtime and infrastructure configuration for AI Service."""

    model_config = SettingsConfigDict(
        env_file=str(SERVICE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "ai-service"
    service_host: str = "127.0.0.1"
    service_port: int = 8003

    # PostgreSQL Durable Persistence Configuration (CP8.2 — ai_db)
    ai_database_url: str = Field(
        default="",
        validation_alias=AliasChoices("ai_database_url", "AI_DATABASE_URL"),
    )

    # Redis Runtime State & Fast Cache Configuration (CP8.4)
    ai_redis_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("ai_redis_enabled", "AI_REDIS_ENABLED", "redis_enabled", "REDIS_ENABLED"),
    )
    ai_redis_url: str = Field(
        default="redis://127.0.0.1:6379/0",
        validation_alias=AliasChoices("ai_redis_url", "AI_REDIS_URL", "redis_url", "REDIS_URL"),
    )
    ai_latest_ttl_seconds: int = Field(
        default=3600,
        validation_alias=AliasChoices("ai_latest_ttl_seconds", "AI_LATEST_TTL_SECONDS"),
    )
    ai_runtime_ttl_seconds: int = Field(
        default=300,
        validation_alias=AliasChoices("ai_runtime_ttl_seconds", "AI_RUNTIME_TTL_SECONDS"),
    )

    # RabbitMQ Configuration (CP7.3)
    rabbitmq_enabled: bool = False
    rabbitmq_host: str = "127.0.0.1"
    rabbitmq_port: int = Field(default=5672, validation_alias=AliasChoices("rabbitmq_port", "rabbitmq_amqp_port"))
    rabbitmq_user: str = Field(default="swiftlet", validation_alias=AliasChoices("rabbitmq_user", "rabbitmq_default_user"))
    rabbitmq_password: str = Field(default="swiftlet123", validation_alias=AliasChoices("rabbitmq_password", "rabbitmq_default_pass"))
    rabbitmq_vhost: str = "/"
    rabbitmq_exchange: str = "swiftlet.domain.events"

    # AI Runtime Internal Control Endpoint Security (CP13 Remediation R1.3)
    ai_runtime_internal_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("ai_runtime_internal_enabled", "AI_RUNTIME_INTERNAL_ENABLED"),
    )
    # No default secret (CP13 hardening R1). Must be provisioned per environment,
    # e.g. python -c "import secrets; print(secrets.token_urlsafe(32))".
    ai_internal_service_key: str = Field(
        default="",
        repr=False,
        validation_alias=AliasChoices("ai_internal_service_key", "AI_INTERNAL_SERVICE_KEY"),
    )
    # Authoritative camera registry (CP13 hardening R2): Management Service.
    ai_management_service_url: str = Field(
        default="http://127.0.0.1:8001",
        validation_alias=AliasChoices("ai_management_service_url", "AI_MANAGEMENT_SERVICE_URL", "MANAGEMENT_SERVICE_URL"),
    )
    ai_registry_timeout_seconds: float = Field(
        default=3.0,
        validation_alias=AliasChoices("ai_registry_timeout_seconds", "AI_REGISTRY_TIMEOUT_SECONDS"),
    )
    ai_allowed_source_dirs: list[str] = Field(
        default_factory=lambda: [str((REPO_ROOT / "ai-pipeline" / "data" / "samples").resolve())],
        validation_alias=AliasChoices("ai_allowed_source_dirs", "AI_ALLOWED_SOURCE_DIRS"),
    )
    ai_allowed_model_paths: list[str] = Field(
        default_factory=lambda: [
            str((REPO_ROOT / "ai-pipeline" / "models" / "best.pt").resolve()),
            "ai-pipeline/models/best.pt",
            "models/best.pt",
        ],
        validation_alias=AliasChoices("ai_allowed_model_paths", "AI_ALLOWED_MODEL_PATHS"),
    )


settings = Settings()


# Minimum length of a secrets.token_urlsafe(32) value (32 random bytes -> 43 chars).
MIN_INTERNAL_KEY_LENGTH = 43
# SHA-256 of secret values that were committed/published and must never be accepted.
_REVOKED_INTERNAL_KEY_SHA256 = frozenset(
    {
        # CP13 pre-hardening default key (published in source/tests on 2026-11-14)
        "5a995368ee43ac79c977a27578f9dd4a5f5eb2f2ca3dc375f4defac306920635",
    }
)
_REVOKED_INTERNAL_KEY_PREFIXES = ("swiftlet-internal-", "changeme", "change-me", "test-key", "dev-key")


def is_internal_key_acceptable(key: str) -> bool:
    """Reject empty, short, low-variety, placeholder or previously published keys."""
    import hashlib

    k = (key or "").strip()
    if len(k) < MIN_INTERNAL_KEY_LENGTH:
        return False
    if len(set(k)) < 16:
        return False
    lowered = k.lower()
    if lowered.startswith(_REVOKED_INTERNAL_KEY_PREFIXES):
        return False
    if hashlib.sha256(k.encode("utf-8")).hexdigest() in _REVOKED_INTERNAL_KEY_SHA256:
        return False
    return True


__all__ = [
    "AI_PIPELINE_DIR",
    "AI_PIPELINE_SRC",
    "CameraConfig",
    "Cfg",
    "REPO_ROOT",
    "RuntimeCameraConfig",
    "SERVICE_DIR",
    "Settings",
    "load_pipeline_config",
    "load_runtime_cameras",
    "load_yaml",
    "resolve_path",
    "settings",
]
