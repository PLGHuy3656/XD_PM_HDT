"""Frame sources: video file, image folder, single image, webcam, RTSP, MJPEG (AI-FR-001, AI-FR-010)."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable, Iterator, Optional

import cv2
import numpy as np

from .schemas import FramePacket

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
T0 = 1_728_135_000.0


def read_image(path) -> Optional[np.ndarray]:
    """imdecode keeps non-ASCII paths working on Windows."""
    try:
        return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        return None


class FrameSource:
    """Common interface: iterate FramePacket."""

    fps: float = 30.0

    def __iter__(self) -> Iterator[FramePacket]:
        raise NotImplementedError

    def close(self):
        pass


class ListFrameSource(FrameSource):
    """In-memory frames (tests, simulation)."""

    def __init__(self, camera_id: str, frames: Iterable, fps: float = 30.0, t0: float = T0):
        self.camera_id, self.frames, self.fps, self.t0 = camera_id, frames, fps, t0

    def __iter__(self):
        for i, img in enumerate(self.frames):
            yield FramePacket(self.camera_id, i, self.t0 + i / self.fps, img)


class CvFrameSource(FrameSource):
    """Video file / webcam / RTSP / MJPEG through cv2.VideoCapture."""

    def __init__(self, camera_id: str, source, source_type: str = "auto",
                 realtime_ts: Optional[bool] = None, max_fps: float = 0.0):
        self.camera_id = camera_id
        self.source = int(source) if str(source).isdigit() else source
        self.kind = self._kind(self.source, source_type)
        self.max_fps = max_fps
        # live stream: wall clock; video file: time follows frame index (cooldown works in video time)
        self.realtime_ts = (self.kind != "video") if realtime_ts is None else realtime_ts
        self.cap = cv2.VideoCapture(self.source)
        if not self.cap.isOpened():
            raise IOError(f"cannot open source: {source} (on Windows a non-ASCII path may fail; copy the file to a plain path)")
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.fps = fps if fps and fps > 1 else 30.0

    @staticmethod
    def _kind(src, st):
        if st != "auto":
            return st
        if isinstance(src, int):
            return "webcam"
        s = str(src).lower()
        if s.startswith("rtsp://"):
            return "rtsp"
        if s.startswith("http"):
            return "mjpeg"
        return "video"

    def __iter__(self):
        i, wall0, last = 0, time.time(), 0.0
        while True:
            ok, img = self.cap.read()
            if not ok:
                break
            if self.max_fps > 0:
                wait = 1.0 / self.max_fps - (time.time() - last)
                if wait > 0:
                    time.sleep(wait)
                last = time.time()
            ts = time.time() if self.realtime_ts else (wall0 + i / self.fps)
            yield FramePacket(self.camera_id, i, ts, img)
            i += 1

    def close(self):
        self.cap.release()


class ImageDirSource(FrameSource):
    def __init__(self, camera_id: str, folder: str, fps: float = 10.0):
        self.camera_id, self.fps = camera_id, fps
        self.files = sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in IMG_EXT)
        if not self.files:
            raise IOError(f"no images in folder: {folder}")

    def __iter__(self):
        t0 = time.time()
        for i, p in enumerate(self.files):
            img = read_image(p)
            if img is not None:
                yield FramePacket(self.camera_id, i, t0 + i / self.fps, img)


def open_source(camera_id: str, source, source_type: str = "auto", max_fps: float = 0.0) -> FrameSource:
    p = Path(str(source))
    if source_type == "image_dir" or (source_type == "auto" and p.is_dir()):
        return ImageDirSource(camera_id, str(p))
    if source_type == "auto" and p.suffix.lower() in IMG_EXT and p.is_file():
        return ListFrameSource(camera_id, [read_image(p)], fps=10.0)
    return CvFrameSource(camera_id, source, source_type, max_fps=max_fps)