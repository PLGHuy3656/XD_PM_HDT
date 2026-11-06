"""Object detection wrapper (AI-FR-002..006).

BaseDetector keeps other modules and tests independent from torch (AI-NFR-007).
"""
from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np

from .schemas import Detection

log = logging.getLogger("swiftletcare.detector")


class BaseDetector:
    names: Dict[int, str] = {}

    def detect(self, image: np.ndarray) -> List[Detection]:
        raise NotImplementedError


class YoloDetector(BaseDetector):
    """Ultralytics YOLO26 (best.pt). Classes are mapped by NAME, not index."""

    def __init__(self, model_path: str, imgsz: int = 640, device: str = "auto",
                 half: bool = False, min_conf: float = 0.15, iou: float = 0.5,
                 keep_classes: Optional[Sequence[str]] = None):
        from ultralytics import YOLO  # lazy import: other modules work without torch
        self.model = YOLO(model_path)
        self.names = dict(self.model.names)
        self.imgsz, self.half, self.min_conf, self.iou = imgsz, half, min_conf, iou
        self.device = self._pick_device(device)
        trained = (getattr(self.model, "overrides", None) or {}).get("imgsz")
        if trained and int(trained) != int(imgsz):
            log.warning("imgsz=%s differs from training size %s; set model.imgsz=%s", imgsz, trained, trained)
        self.keep = set(keep_classes) if keep_classes else None

    @staticmethod
    def _pick_device(device: str) -> str:
        if device != "auto":
            return device
        try:
            import torch
            return "cuda:0" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    def detect(self, image: np.ndarray) -> List[Detection]:
        kw = {"half": True} if (self.half and self.device != "cpu") else {}
        res = self.model.predict(image, imgsz=self.imgsz, conf=self.min_conf, iou=self.iou,
                                 device=self.device, verbose=False, **kw)[0]
        out: List[Detection] = []
        if res.boxes is None or len(res.boxes) == 0:
            return out
        xyxy = res.boxes.xyxy.cpu().numpy()
        conf = res.boxes.conf.cpu().numpy()
        cls = res.boxes.cls.cpu().numpy().astype(int)
        for b, c, k in zip(xyxy, conf, cls):
            name = self.names.get(int(k), str(k))
            if self.keep and name not in self.keep:
                continue
            out.append(Detection(name, float(c), [float(v) for v in b]))
        return out

    def warmup(self, shape=(480, 640, 3)):
        self.detect(np.zeros(shape, dtype=np.uint8))


class CallableDetector(BaseDetector):
    """Fake detector for tests/simulation: fn(image) -> List[Detection]."""

    def __init__(self, fn: Callable[[np.ndarray], List[Detection]], names: Optional[Dict[int, str]] = None):
        self.fn = fn
        self.names = names or {0: "swiftlet", 1: "rat", 2: "snake"}

    def detect(self, image):
        return self.fn(image)