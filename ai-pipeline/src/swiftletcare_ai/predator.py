"""Predator alerts (AI-FR-004/005/008). False alarms are filtered by threshold, consecutive frames and cooldown."""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from .schemas import Detection


class PredatorMonitor:
    def __init__(self, classes: Sequence[str] = ("rat", "snake"),
                 conf_threshold: Optional[Dict[str, float]] = None,
                 min_consecutive_frames: int = 3, cooldown_s: float = 30.0, default_conf: float = 0.5):
        self.classes = set(classes)
        self.thr = conf_threshold or {}
        self.default_conf = default_conf
        self.min_frames = max(1, min_consecutive_frames)
        self.cooldown_s = cooldown_s
        self._streak: Dict[str, int] = {c: 0 for c in self.classes}
        self._last_fire: Dict[str, float] = {}

    def threshold(self, cls: str) -> float:
        return float(self.thr.get(cls, self.default_conf))

    def update(self, detections: List[Detection], timestamp: float) -> List[Detection]:
        """Return detections to alert on in this frame (max 1 per class: highest confidence)."""
        best: Dict[str, Detection] = {}
        for d in detections:
            if d.cls in self.classes and d.confidence >= self.threshold(d.cls):
                if d.cls not in best or d.confidence > best[d.cls].confidence:
                    best[d.cls] = d
        fired: List[Detection] = []
        for c in self.classes:
            if c not in best:
                self._streak[c] = 0
                continue
            self._streak[c] += 1
            if self._streak[c] >= self.min_frames:
                last = self._last_fire.get(c)
                if last is None or timestamp - last >= self.cooldown_s:
                    self._last_fire[c] = timestamp
                    fired.append(best[c])
        return fired