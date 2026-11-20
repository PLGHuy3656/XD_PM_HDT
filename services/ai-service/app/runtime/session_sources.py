"""INT02 frame sources for interactive camera sessions.

* LoopingVideoSource - replays a server-side demo video (never a caller-supplied path) in real
  time, so the real detector/tracker/counter keep processing it while the session is active.
* PushFrameSource    - receives JPEG frames pushed by an authorised client session (browser
  webcam via Gateway) through a small bounded queue; nothing is written to disk.

Both feed swiftletcare_ai FramePackets into the unchanged CameraPipeline.
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Iterator, Optional

import cv2
import numpy as np

from swiftletcare_ai.schemas import FramePacket
from swiftletcare_ai.video_source import FrameSource, open_source


class LoopingVideoSource(FrameSource):
    """Replay a local video file in a loop at its native FPS until closed."""

    kind = "video"

    def __init__(self, camera_id: str, path: str, fps: Optional[float] = None) -> None:
        self.camera_id = camera_id
        self.path = path
        self._closed = threading.Event()
        probe = cv2.VideoCapture(path)
        if not probe.isOpened():
            raise FileNotFoundError(f"Demo video not readable: {path}")
        native = probe.get(cv2.CAP_PROP_FPS) or 0.0
        probe.release()
        self.fps = float(fps or native or 10.0)
        self.loops_completed = 0

    def __iter__(self) -> Iterator[FramePacket]:
        frame_id = 0
        interval = 1.0 / self.fps if self.fps > 0 else 0.1
        t0 = time.time()
        next_emit = time.perf_counter()
        while not self._closed.is_set():
            inner = open_source(self.camera_id, self.path, source_type="video")
            emitted = 0
            try:
                for pkt in inner:
                    if self._closed.is_set():
                        return
                    wait = next_emit - time.perf_counter()
                    if wait > 0 and self._closed.wait(wait):
                        return
                    next_emit = max(next_emit + interval, time.perf_counter())
                    yield FramePacket(self.camera_id, frame_id, t0 + frame_id * interval, pkt.image)
                    frame_id += 1
                    emitted += 1
            finally:
                inner.close()
            if emitted == 0:
                raise RuntimeError(f"Demo video produced no frames: {self.path}")
            self.loops_completed += 1

    def close(self) -> None:
        self._closed.set()


class PushFrameSource(FrameSource):
    """Bounded in-memory queue of client-pushed JPEG frames (latest-wins, no persistence)."""

    kind = "push"

    def __init__(
        self,
        camera_id: str,
        max_queue: int = 2,
        idle_timeout_s: float = 20.0,
        max_width: int = 1280,
        max_height: int = 960,
    ) -> None:
        self.camera_id = camera_id
        self.fps = 0.0
        self.idle_timeout_s = float(idle_timeout_s)
        self.max_width = int(max_width)
        self.max_height = int(max_height)
        self._queue: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=max(1, int(max_queue)))
        self._closed = threading.Event()
        self._last_push = time.monotonic()
        self.accepted = 0
        self.dropped = 0
        self.rejected = 0

    @property
    def closed(self) -> bool:
        return self._closed.is_set()

    def push_jpeg(self, data: bytes) -> bool:
        """Decode and enqueue one frame. Returns False if the bytes are not a valid image."""
        if self._closed.is_set():
            return False
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None or img.ndim != 3:
            self.rejected += 1
            return False
        h, w = img.shape[:2]
        if w > self.max_width or h > self.max_height:
            self.rejected += 1
            return False
        try:
            self._queue.put_nowait(img)
        except queue.Full:
            try:
                self._queue.get_nowait()  # drop the oldest frame, keep latency low
                self.dropped += 1
            except queue.Empty:
                pass
            self._queue.put_nowait(img)
        self._last_push = time.monotonic()
        self.accepted += 1
        return True

    def __iter__(self) -> Iterator[FramePacket]:
        frame_id = 0
        while not self._closed.is_set():
            try:
                img = self._queue.get(timeout=0.5)
            except queue.Empty:
                if time.monotonic() - self._last_push > self.idle_timeout_s:
                    # client session went away without stopping -> end the session cleanly
                    self._closed.set()
                    return
                continue
            yield FramePacket(self.camera_id, frame_id, time.time(), img)
            frame_id += 1

    def close(self) -> None:
        self._closed.set()
