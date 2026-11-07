"""Tests verifying Step 1 refactoring: config paths, FrameCleaner, DetectionFilter, LockedDetector."""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import List

import numpy as np
import pytest

from fastapi import HTTPException

from app.api.snapshots import _resolve_safe_snapshot_path
from app.config import AI_PIPELINE_DIR, RuntimeCameraConfig
from app.runtime.camera_pipeline import CameraPipeline
from app.runtime.manager import AIRuntimeManager, LockedDetector
from app.runtime.sink import CallbackRuntimeSink
from swiftletcare_ai.detector import BaseDetector, CallableDetector
from swiftletcare_ai.frame_clean import FrameCleaner
from swiftletcare_ai.postfilter import DetectionFilter
from swiftletcare_ai.predator import PredatorMonitor
from swiftletcare_ai.schemas import Detection as TV2Detection, FramePacket
from swiftletcare_ai.tracker import CentroidTracker
from swiftletcare_ai.video_source import ListFrameSource


def test_ai_pipeline_dir_resolution():
    """Verify AI_PIPELINE_DIR resolves to parent of ai-service by default."""
    service_dir = Path(__file__).resolve().parent.parent
    assert AI_PIPELINE_DIR == service_dir.parent
    assert (AI_PIPELINE_DIR / "src").exists()


def test_locked_detector_thread_safety():
    """Verify LockedDetector serializes concurrent inference calls."""
    active_calls = 0
    max_active = 0
    lock = threading.Lock()

    class SlowDetector(BaseDetector):
        def detect(self, image):
            nonlocal active_calls, max_active
            with lock:
                active_calls += 1
                if active_calls > max_active:
                    max_active = active_calls
            time.sleep(0.05)
            with lock:
                active_calls -= 1
            return []

    detector = LockedDetector(SlowDetector())
    threads = []
    fake_img = np.ones((64, 64, 3), dtype=np.uint8) * 128

    for _ in range(5):
        t = threading.Thread(target=lambda: detector.detect(fake_img))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Even with 5 concurrent threads, max active inside detect must be 1
    assert max_active == 1


def test_camera_pipeline_with_frame_cleaner_rejects_black_frame():
    """Verify that a black frame is rejected by FrameCleaner and pipeline transitions to DEGRADED."""
    # 1 bright frame followed by 1 pitch black frame
    bright = np.ones((100, 100, 3), dtype=np.uint8) * 150
    black = np.zeros((100, 100, 3), dtype=np.uint8)
    frames = [bright, black]

    cam_cfg = RuntimeCameraConfig(
        camera_id="CAM-CLEAN-01",
        source=ListFrameSource("CAM-CLEAN-01", frames, fps=10.0, t0=1_000.0),
    )

    cleaner = FrameCleaner(min_size=32, dark_threshold=60.0, target_brightness=100.0, enhance_dark=True)
    pipeline = CameraPipeline(
        camera_config=cam_cfg,
        detector=CallableDetector(lambda _img: []),
        tracker=CentroidTracker(),
        predator_monitor=PredatorMonitor(),
        frame_cleaner=cleaner,
    )

    # Frame 0 (bright) -> processed
    pkt0 = FramePacket("CAM-CLEAN-01", 0, 1_000.0, bright)
    res0 = pipeline.process_packet(pkt0)
    assert res0 is not None
    assert pipeline.status.status == "ONLINE"

    # Frame 1 (black) -> rejected by FrameCleaner -> returns None & transitions to DEGRADED
    pkt1 = FramePacket("CAM-CLEAN-01", 1, 1_000.1, black)
    res1 = pipeline.process_packet(pkt1)
    assert res1 is None
    assert pipeline.status.status == "DEGRADED"
    assert pipeline.status.errorCode == "INVALID_FRAME"


def test_camera_pipeline_with_detection_filter_drops_tiny_and_cross_class_dups():
    """Verify DetectionFilter drops sub-threshold boxes and keeps higher confidence on cross-class overlap."""
    img = np.ones((200, 200, 3), dtype=np.uint8) * 120  # area = 40000

    # Tiny box: 2x2 = 4 pixels, area_frac = 4/40000 = 0.0001 < 0.0005 min_area_frac
    tiny = TV2Detection("swiftlet", 0.95, [10, 10, 12, 12])

    # Overlapping boxes (IOU ~ 1.0): rat (conf=0.7) vs snake (conf=0.9) -> snake should survive
    rat = TV2Detection("rat", 0.70, [50, 50, 100, 100])
    snake = TV2Detection("snake", 0.90, [50, 50, 100, 100])

    detections_output: List[TV2Detection] = []

    def mock_detect(_img):
        return [tiny, rat, snake]

    cam_cfg = RuntimeCameraConfig(
        camera_id="CAM-FILTER-01",
        source=ListFrameSource("CAM-FILTER-01", [img], fps=10.0, t0=1_000.0),
    )

    filter_ = DetectionFilter(min_area_frac=0.0005, cross_class_iou=0.6)
    pipeline = CameraPipeline(
        camera_config=cam_cfg,
        detector=CallableDetector(mock_detect),
        tracker=CentroidTracker(),
        predator_monitor=PredatorMonitor(),
        detection_filter=filter_,
    )

    pkt = FramePacket("CAM-FILTER-01", 0, 1_000.0, img)
    res = pipeline.process_packet(pkt)
    assert res is not None

    classes = [d.cls for d in res.detections]
    # Tiny box dropped, rat dropped in favor of higher confidence snake
    assert "swiftlet" not in classes
    assert "rat" not in classes
    assert "snake" in classes


def test_snapshot_safe_path_resolution(tmp_path: Path):
    """Verify _resolve_safe_snapshot_path works correctly with simplified parent check."""
    snap_dir = tmp_path / "snaps"
    snap_dir.mkdir()
    valid_file = snap_dir / "valid_image.jpg"
    valid_file.write_bytes(b"data")

    # Valid direct file
    resolved = _resolve_safe_snapshot_path("valid_image.jpg", snap_dir)
    assert resolved == valid_file

    # Non-existent file
    with pytest.raises(HTTPException) as exc_info:
        _resolve_safe_snapshot_path("missing.jpg", snap_dir)
    assert exc_info.value.status_code == 404

    # Traversal attempt
    with pytest.raises(HTTPException) as exc_info:
        _resolve_safe_snapshot_path("../escape.jpg", snap_dir)
    assert exc_info.value.status_code == 400
