"""Draw boxes and save evidence snapshots (AI-FR-007, AI-FR-014)."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable, Optional

import cv2
import numpy as np

from .schemas import Detection

COLORS = {"swiftlet": (80, 200, 80), "rat": (0, 140, 255), "snake": (0, 0, 255)}


def draw_detections(image: np.ndarray, dets: Iterable[Detection], line=None, counts=None) -> np.ndarray:
    img = image.copy()
    for d in dets:
        x1, y1, x2, y2 = [int(v) for v in d.bbox]
        col = COLORS.get(d.cls, (255, 255, 0))
        cv2.rectangle(img, (x1, y1), (x2, y2), col, 2)
        tag = f"{d.cls} {d.confidence:.2f}" + (f" #{d.track_id}" if d.track_id is not None else "")
        cv2.putText(img, tag, (x1, max(12, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1, cv2.LINE_AA)
    if line is not None:
        (ax, ay), (bx, by) = line
        cv2.line(img, (int(ax), int(ay)), (int(bx), int(by)), (255, 255, 0), 2)
    if counts is not None:
        cv2.putText(img, f"IN {counts[0]}  OUT {counts[1]}  NET {counts[0] - counts[1]}", (10, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    return img


class SnapshotStore:
    """Save locally; public_base_url (if set) is used to return a URL to Backend."""

    def __init__(self, directory: str = "outputs/snapshots", public_base_url: str = "", jpeg_quality: int = 85):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.base = public_base_url.rstrip("/")
        self.q = int(jpeg_quality)

    def save(self, image: np.ndarray, camera_id: str, event_type: str, timestamp: float) -> str:
        name = f"{camera_id}_{event_type}_{int(timestamp)}_{int((timestamp % 1) * 1000):03d}.jpg"
        path = self.dir / name
        cv2.imwrite(str(path), image, [int(cv2.IMWRITE_JPEG_QUALITY), self.q])
        return f"{self.base}/{name}" if self.base else str(path)