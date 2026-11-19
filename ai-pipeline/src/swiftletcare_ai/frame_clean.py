"""Input cleaning (AI-FR-001, AI-FR-010): reject unusable frames, brighten dark ones.

No resize here, so bbox coordinates stay in the original frame space.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import cv2
import numpy as np


@dataclass
class CleanStats:
    ok: int = 0
    bad: int = 0
    enhanced: int = 0


class FrameCleaner:
    def __init__(self, min_size: int = 32, dark_threshold: float = 60.0, target_brightness: float = 100.0,
                 enhance_dark: bool = True, max_gamma: float = 3.0):
        self.min_size = min_size
        self.dark_threshold = dark_threshold
        self.target = target_brightness
        self.enhance_dark = enhance_dark
        self.max_gamma = max_gamma
        self.stats = CleanStats()
        self._lut: Dict[float, np.ndarray] = {}

    @staticmethod
    def brightness(img: np.ndarray) -> float:
        return float(img[::4, ::4].mean())          # sampled mean, cheap enough for every frame

    def _gamma_lut(self, gamma: float) -> np.ndarray:
        if gamma not in self._lut:
            self._lut[gamma] = (np.power(np.arange(256) / 255.0, 1.0 / gamma) * 255).astype(np.uint8)
        return self._lut[gamma]

    def clean(self, img) -> Tuple[Optional[np.ndarray], dict]:
        """Return (image or None, info). None means the frame must be skipped."""
        bad = (not isinstance(img, np.ndarray) or img.ndim != 3 or img.shape[2] != 3
               or img.dtype != np.uint8 or min(img.shape[:2]) < self.min_size)
        if bad:
            self.stats.bad += 1
            return None, {"reason": "invalid"}
        b = self.brightness(img)
        if b < 1.0:                                   # black frame, nothing to detect
            self.stats.bad += 1
            return None, {"reason": "black"}
        enhanced = False
        if self.enhance_dark and b < self.dark_threshold:
            gamma = math.log(b / 255.0) / math.log(self.target / 255.0)   # mean(out) ~ target
            gamma = round(min(max(gamma, 1.0), self.max_gamma), 2)
            img = cv2.LUT(img, self._gamma_lut(gamma))
            enhanced = True
            self.stats.enhanced += 1
        self.stats.ok += 1
        return img, {"brightness": round(b, 1), "enhanced": enhanced}