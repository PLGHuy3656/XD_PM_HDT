"""Tests for Detection, Counting (LineCounter -> CountUpdate), and Predator (PredatorMonitor -> AIEvent) adaptation (CP5.2 Task 7, 8, 11.5, 11.7, 11.8)."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np

from app.config import RuntimeCameraConfig
from app.runtime.camera_pipeline import CameraPipeline
from app.runtime.sink import CallbackRuntimeSink
from app.schemas.canonical import AIEvent, CountUpdate, DetectionResult
from swiftletcare_ai.detector import CallableDetector
from swiftletcare_ai.predator import PredatorMonitor
from swiftletcare_ai.schemas import Detection as TV2Detection
from swiftletcare_ai.snapshot import SnapshotStore
from swiftletcare_ai.tracker import CentroidTracker
from swiftletcare_ai.video_source import ListFrameSource


def _blank_frames(n: int, h: int = 200, w: int = 200) -> List[np.ndarray]:
    return [np.zeros((h, w, 3), dtype=np.uint8) for _ in range(n)]


def test_detection_adaptation_preserves_class_confidence_bbox_and_track_id():
    tv2_det = TV2Detection("swiftlet", 0.91234, [50.12, 60.56, 110.89, 140.01], track_id=7)
    canonical = CameraPipeline.adapt_detection(tv2_det)
    assert canonical.to_dict() == {
        "class": "swiftlet",
        "confidence": 0.9123,
        "bbox": {"x1": 50.1, "y1": 60.6, "x2": 110.9, "y2": 140.0},
        "trackId": 7,
    }


def test_counting_adaptation_delta_and_net_change_semantics():
    """Verify entryCount, exitCount, netChange = entryCount - exitCount, and non-negative deltaEntry/deltaExit."""
    # Horizontal line at y = 100 (0.5 of height=200), inside_side="positive" (y > 100 is inside)
    # Bird 1: moves y=40 -> y=70 -> y=140 (crosses into positive side => ENTRY #1 on frame 2)
    # Bird 2: moves y=160 -> y=130 -> y=50 (crosses into negative side => EXIT #1 on frame 4)
    # Bird 3: moves y=30 -> y=60 -> y=150 (crosses into positive side => ENTRY #2 on frame 6)
    per_frame: Dict[int, List[TV2Detection]] = {
        0: [TV2Detection("swiftlet", 0.9, [90, 30, 110, 50])],   # center (100, 40)
        1: [TV2Detection("swiftlet", 0.9, [90, 60, 110, 80])],   # center (100, 70)
        2: [TV2Detection("swiftlet", 0.9, [90, 130, 110, 150])], # center (100, 140) -> ENTRY
        3: [TV2Detection("swiftlet", 0.9, [30, 150, 50, 170])],  # new bird at (40, 160)
        4: [TV2Detection("swiftlet", 0.9, [30, 120, 50, 140])],  # center (40, 130)
        5: [TV2Detection("swiftlet", 0.9, [30, 40, 50, 60])],    # center (40, 50) -> EXIT
        6: [TV2Detection("swiftlet", 0.9, [140, 20, 160, 40])],  # bird 3 at (150, 30)
        7: [TV2Detection("swiftlet", 0.9, [140, 50, 160, 70])],  # center (150, 60)
        8: [TV2Detection("swiftlet", 0.9, [140, 140, 160, 160])],# center (150, 150) -> ENTRY
    }
    frames = _blank_frames(9)
    idx_box = {"i": 0}

    def detect_fn(_img):
        i = idx_box["i"]
        idx_box["i"] += 1
        return per_frame.get(i, [])

    count_updates: List[CountUpdate] = []
    ai_events: List[AIEvent] = []
    sink = CallbackRuntimeSink(
        on_count=count_updates.append,
        on_event=ai_events.append,
    )

    cam_cfg = RuntimeCameraConfig(
        camera_id="CAM-COUNT-01",
        farm_id="FARM-01",
        zone_id="ZONE-A",
        source=ListFrameSource("CAM-COUNT-01", frames, fps=10.0, t0=1_761_489_600.0),
        line=((0.05, 0.50), (0.95, 0.50)),
        inside_side="positive",
    )

    pipeline = CameraPipeline(
        camera_config=cam_cfg,
        detector=CallableDetector(detect_fn),
        tracker=CentroidTracker(max_distance=0.45, max_missed=1),
        predator_monitor=PredatorMonitor(),
        sink=sink,
        count_report_interval_s=999.0,  # emit only on initial frame + crossings
    )
    pipeline.run()

    # No per-bird ENTRY/EXIT AIEvent records should ever be emitted
    assert ai_events == []

    # Initial frame 0 (0, 0) + frame 2 (entry=1, exit=0) + frame 5 (entry=1, exit=1) + frame 8 (entry=2, exit=1)
    assert len(count_updates) == 4

    u0, u1, u2, u3 = count_updates
    assert (u0.entryCount, u0.exitCount, u0.netChange, u0.deltaEntry, u0.deltaExit) == (0, 0, 0, 0, 0)
    assert (u1.entryCount, u1.exitCount, u1.netChange, u1.deltaEntry, u1.deltaExit) == (1, 0, 1, 1, 0)
    assert (u2.entryCount, u2.exitCount, u2.netChange, u2.deltaEntry, u2.deltaExit) == (1, 1, 0, 0, 1)
    assert (u3.entryCount, u3.exitCount, u3.netChange, u3.deltaEntry, u3.deltaExit) == (2, 1, 1, 1, 0)

    # WindowStartedAt stays constant across the session
    assert u0.windowStartedAt == u1.windowStartedAt == u2.windowStartedAt == u3.windowStartedAt
    for u in count_updates:
        assert u.deltaEntry >= 0
        assert u.deltaExit >= 0
        assert u.netChange == u.entryCount - u.exitCount
        dumped = u.to_dict()
        assert "occupancy" not in dumped
        assert "currentBirdCount" not in dumped
        assert "totalBirdPopulation" not in dumped


def test_predator_monitor_adaptation_debounce_cooldown_and_snapshot(tmp_path: Path):
    """Verify PredatorMonitor output adapts to canonical AIEvent(PREDATOR_DETECTED) with snapshot & cooldown."""
    # Frames 0, 1, 2: snake present for 3 consecutive frames -> triggers 1 AIEvent at frame 2
    # Frame 3, 4, 5: snake still present within 30s cooldown -> suppressed by cooldown
    # Frame 6, 7: rat present for only 2 frames (below min_consecutive_frames=3) -> no alert
    per_frame: Dict[int, List[TV2Detection]] = {
        0: [TV2Detection("snake", 0.88, [20, 30, 80, 90])],
        1: [TV2Detection("snake", 0.91, [22, 32, 82, 92])],
        2: [TV2Detection("snake", 0.94, [24, 34, 84, 94])],
        3: [TV2Detection("snake", 0.95, [25, 35, 85, 95])],
        4: [TV2Detection("snake", 0.95, [25, 35, 85, 95])],
        5: [TV2Detection("snake", 0.95, [25, 35, 85, 95])],
        6: [TV2Detection("rat", 0.80, [100, 100, 140, 140])],
        7: [TV2Detection("rat", 0.82, [102, 100, 142, 140])],
        8: [],
    }
    frames = _blank_frames(9, h=240, w=320)
    idx_box = {"i": 0}

    def detect_fn(_img):
        i = idx_box["i"]
        idx_box["i"] += 1
        return per_frame.get(i, [])

    events: List[AIEvent] = []
    detections: List[DetectionResult] = []
    sink = CallbackRuntimeSink(on_detection=detections.append, on_event=events.append)

    snap_store = SnapshotStore(directory=str(tmp_path / "snapshots"), public_base_url="/snapshots")
    cam_cfg = RuntimeCameraConfig(
        camera_id="CAM-PRED-01",
        farm_id="FARM-01",
        zone_id="ZONE-B",
        source=ListFrameSource("CAM-PRED-01", frames, fps=5.0, t0=1_761_489_700.0),
    )

    pipeline = CameraPipeline(
        camera_config=cam_cfg,
        detector=CallableDetector(detect_fn),
        tracker=CentroidTracker(),
        predator_monitor=PredatorMonitor(
            classes=("rat", "snake"),
            conf_threshold={"rat": 0.5, "snake": 0.5},
            min_consecutive_frames=3,
            cooldown_s=30.0,
        ),
        snapshot_store=snap_store,
        sink=sink,
    )
    pipeline.run()

    assert len(detections) == 9
    assert len(events) == 1

    ev = events[0]
    assert ev.eventType == "PREDATOR_DETECTED"
    assert ev.cameraId == "CAM-PRED-01"
    assert ev.farmId == "FARM-01"
    assert ev.zoneId == "ZONE-B"
    assert ev.frameId == 2
    assert ev.cls == "snake"
    assert ev.confidence == 0.94
    assert ev.bbox.to_dict() == {"x1": 24.0, "y1": 34.0, "x2": 84.0, "y2": 94.0}
    assert ev.snapshot is not None and ev.snapshot.startswith("/snapshots/CAM-PRED-01_snake_")
    assert "timestamp" not in ev.to_dict()

    saved_files = list((tmp_path / "snapshots").glob("*.jpg"))
    assert len(saved_files) == 1
