"""Nạp cấu hình YAML (pipeline.yaml + cameras.yaml) thành object truy cập bằng dấu chấm."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


class Cfg(dict):
    """dict hỗ trợ cfg.a.b; thiếu khoá -> AttributeError rõ ràng."""

    def __getattr__(self, k):
        try:
            v = self[k]
        except KeyError as e:
            raise AttributeError(k) from e
        return Cfg(v) if isinstance(v, dict) else v


def load_yaml(path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_pipeline_config(path) -> Cfg:
    return Cfg(load_yaml(path))


class CameraConfig:
    def __init__(self, camera_id: str, source, source_type: str = "auto",
                 line: Tuple[Tuple[float, float], Tuple[float, float]] = ((0.1, 0.5), (0.9, 0.5)),
                 inside_side: str = "positive"):
        self.camera_id = camera_id
        self.source = source
        self.source_type = source_type
        self.line = line
        self.inside_side = inside_side


def load_cameras(path) -> List[CameraConfig]:
    data = load_yaml(path)
    out, seen = [], set()
    for c in data.get("cameras", []):
        cid = c["camera_id"]
        if cid in seen:
            raise ValueError(f"camera_id trùng: {cid}")  # Assumption: ID duy nhất
        seen.add(cid)
        ln = c.get("counting_line", {})
        line = (tuple(ln.get("start", (0.1, 0.5))), tuple(ln.get("end", (0.9, 0.5))))
        out.append(CameraConfig(cid, c["source"], c.get("source_type", "auto"),
                                line, c.get("inside_side", "positive")))
    return out


def resolve_path(p: str, base: Path) -> str:
    q = Path(p)
    return str(q if q.is_absolute() else (base / q))