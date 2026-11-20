"""INT02 frame sources for interactive camera sessions.

* LoopingVideoSource - replays a server-side demo video (never a caller-supplied path) in real
  time, so the real detector/tracker/counter keep processing it while the session is active.
* PushFrameSource    - receives JPEG frames pushed by an authorised client session (browser
  webcam via Gateway) through a small bounded queue; nothing is written to disk.
* UploadedVideoSource - plays a user-uploaded video ONCE (server-generated temp file name),
  sampled to a bounded FPS and wall-clock budget, and deletes the file when done/closed.

Both feed swiftletcare_ai FramePackets into the unchanged CameraPipeline.
"""
from __future__ import annotations

import os
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


class UploadedVideoError(ValueError):
    """Validation failure for an uploaded video (code is returned to the client)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def probe_uploaded_video(path: str, max_duration_s: float, max_width: int, max_height: int) -> dict:
    """Validate an uploaded file with the real decoder: it must open, decode a first frame and
    stay within the duration / resolution limits. Extension or MIME alone is never trusted."""
    cap = cv2.VideoCapture(path)
    try:
        if not cap.isOpened():
            raise UploadedVideoError("VIDEO_UNREADABLE", "Không giải mã được video (codec không hỗ trợ hoặc file hỏng)")
        ok, frame = cap.read()
        if not ok or frame is None:
            raise UploadedVideoError("VIDEO_UNREADABLE", "Video không có khung hình đọc được")
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        h, w = frame.shape[:2]
    finally:
        cap.release()
    if fps <= 0 or fps > 120:
        raise UploadedVideoError("VIDEO_UNREADABLE", "Không xác định được FPS hợp lệ của video")
    if w > max_width or h > max_height:
        raise UploadedVideoError("VIDEO_RESOLUTION_TOO_HIGH", f"Độ phân giải {w}x{h} vượt giới hạn {max_width}x{max_height}")
    duration = frames / fps if frames > 0 else 0.0
    if duration <= 0:
        raise UploadedVideoError("VIDEO_UNREADABLE", "Không xác định được thời lượng video")
    if duration > max_duration_s:
        raise UploadedVideoError("VIDEO_TOO_LONG", f"Video dài {duration:.0f}s, vượt giới hạn {max_duration_s:.0f}s")
    return {"fps": fps, "frames": int(frames), "width": int(w), "height": int(h), "durationS": round(duration, 2)}


class UploadedVideoSource(FrameSource):
    """One pass over an uploaded video at real-time pace, sampled to <= max_fps.

    `completed` is True only when the whole file was processed (not stopped / timed out).
    The temp file is removed when iteration ends or the source is closed.
    """

    kind = "video"

    def __init__(self, camera_id: str, path: str, native_fps: float, max_fps: float = 10.0, max_wall_s: float = 900.0) -> None:
        self.camera_id = camera_id
        self.path = path
        self.native_fps = float(native_fps) if native_fps and native_fps > 0 else 10.0
        self.fps = min(self.native_fps, float(max_fps))
        self.max_wall_s = float(max_wall_s)
        self.completed = False
        self.timed_out = False
        self._closed = threading.Event()
        self._deleted = False
        self._lock = threading.Lock()

    def _delete_file(self) -> None:
        with self._lock:
            if self._deleted:
                return
            self._deleted = True
        try:
            os.remove(self.path)
        except FileNotFoundError:
            pass

    def __iter__(self) -> Iterator[FramePacket]:
        step = max(1, int(round(self.native_fps / self.fps)))
        interval = step / self.native_fps
        started = time.monotonic()
        next_emit = time.perf_counter()
        t0 = time.time()
        cap = cv2.VideoCapture(self.path)
        frame_id = 0
        idx = 0
        try:
            if not cap.isOpened():
                raise RuntimeError("Uploaded video could not be opened")
            while not self._closed.is_set():
                if time.monotonic() - started > self.max_wall_s:
                    self.timed_out = True
                    return
                ok, frame = cap.read()
                if not ok or frame is None:
                    self.completed = True
                    return
                if idx % step:
                    idx += 1
                    continue
                idx += 1
                wait = next_emit - time.perf_counter()
                if wait > 0 and self._closed.wait(wait):
                    return
                next_emit = max(next_emit + interval, time.perf_counter())
                yield FramePacket(self.camera_id, frame_id, t0 + frame_id * interval, frame)
                frame_id += 1
        finally:
            cap.release()
            self._delete_file()

    def close(self) -> None:
        self._closed.set()
        self._delete_file()
