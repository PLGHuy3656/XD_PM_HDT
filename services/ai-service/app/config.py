"""Configuration and path bootstrap for the AI Service reference prototype."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SERVICE_DIR.parent.parent
AI_PIPELINE_DIR = Path(os.getenv("AI_PIPELINE_DIR", str(REPO_ROOT / "ai-pipeline"))).resolve()
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
    autostart: bool = False

    @classmethod
    def from_tv2_camera_config(
        cls,
        cam: CameraConfig,
        farm_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        autostart: bool = False,
    ) -> "RuntimeCameraConfig":
        return cls(
            camera_id=cam.camera_id,
            source=cam.source,
            source_type=cam.source_type,
            line=cam.line,
            inside_side=cam.inside_side,
            farm_id=farm_id,
            zone_id=zone_id,
            autostart=autostart,
        )


def load_runtime_cameras(path: str | Path) -> List[RuntimeCameraConfig]:
    """Load camera configurations from YAML, supporting optional farm_id / zone_id / autostart."""
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
                autostart=bool(c.get("autostart", False)),
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


settings = Settings()


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
