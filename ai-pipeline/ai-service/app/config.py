"""Configuration and path bootstrap for the AI Service reference prototype."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SERVICE_DIR = Path(__file__).resolve().parent.parent
AI_PIPELINE_DIR = Path(os.getenv("AI_PIPELINE_DIR", str(SERVICE_DIR.parent))).resolve()
REPO_ROOT = AI_PIPELINE_DIR.parent
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
                autostart=bool(c.get("autostart", False)),
            )
        )
    return out


__all__ = [
    "AI_PIPELINE_DIR",
    "AI_PIPELINE_SRC",
    "CameraConfig",
    "Cfg",
    "REPO_ROOT",
    "RuntimeCameraConfig",
    "SERVICE_DIR",
    "load_pipeline_config",
    "load_runtime_cameras",
    "load_yaml",
    "resolve_path",
]
