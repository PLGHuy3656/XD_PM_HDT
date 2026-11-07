"""Light cleanup of detector output: drop tiny boxes, low-confidence classes, duplicate boxes with 2 labels."""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from .schemas import Detection


def iou(a: Sequence[float], b: Sequence[float]) -> float:
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


class DetectionFilter:
    def __init__(self, min_area_frac: float = 0.0005, cross_class_iou: float = 0.6,
                 class_min_conf: Optional[Dict[str, float]] = None):
        self.min_area_frac = min_area_frac
        self.cross_iou = cross_class_iou
        self.class_min_conf = class_min_conf or {}

    def apply(self, dets: List[Detection], frame_shape) -> List[Detection]:
        h, w = frame_shape[:2]
        frame_area = float(h * w)
        keep: List[Detection] = []
        for d in dets:
            bw, bh = d.bbox[2] - d.bbox[0], d.bbox[3] - d.bbox[1]
            if bw <= 0 or bh <= 0 or (bw * bh) / frame_area < self.min_area_frac:
                continue
            if d.confidence < self.class_min_conf.get(d.cls, 0.0):
                continue
            keep.append(d)
        keep.sort(key=lambda d: -d.confidence)
        out: List[Detection] = []
        for d in keep:      # same object labelled rat and snake: keep the more confident label only
            if any(o.cls != d.cls and iou(o.bbox, d.bbox) >= self.cross_iou for o in out):
                continue
            out.append(d)
        return out