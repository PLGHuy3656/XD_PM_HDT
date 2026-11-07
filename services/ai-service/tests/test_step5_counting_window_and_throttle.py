"""Tests verifying Step 5: Counting time windows, count reset & history, WebSocket detection throttling, and snapshot pruning."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import RuntimeCameraConfig
from app.main import create_app
from app.runtime.camera_pipeline import CameraPipeline
from app.runtime.manager import AIRuntimeManager, PruningSnapshotStore
from app.runtime.sink import BaseRuntimeSink
from app.runtime.state_store import InMemoryAIRuntimeStateStore
from app.schemas.canonical import (
    AIEvent,
    BoundingBox,
    CameraRuntimeStatus,
    CountUpdate,
    DetectionResult,
    FrameInfo,
    epoch_to_iso8601_utc,
)
from app.websocket.manager import AIWebSocketManager, WebSocketRuntimeSink
from swiftletcare_ai.detector import CallableDetector
from swiftletcare_ai.predator import PredatorMonitor
from swiftletcare_ai.schemas import Detection as TV2Detection
from swiftletcare_ai.snapshot import SnapshotStore
from swiftletcare_ai.tracker import CentroidTracker
from swiftletcare_ai.video_source import ListFrameSource


# ---------------------------------------------------------------------------
# Test Helpers & Scripted Sources
# ---------------------------------------------------------------------------
class RecordingSink(BaseRuntimeSink):
    """Sink that collects all emitted canonical objects for assertions."""

    def __init__(self) -> None:
        self.detections: List[DetectionResult] = []
        self.counts: List[CountUpdate] = []
        self.events: List[AIEvent] = []
        self.statuses: List[CameraRuntimeStatus] = []

    def on_detection(self, result: DetectionResult) -> None:
        self.detections.append(result)

    def on_count(self, update: CountUpdate) -> None:
        self.counts.append(update)

    def on_event(self, event: AIEvent) -> None:
        self.events.append(event)

    def on_status(self, status: CameraRuntimeStatus) -> None:
        self.statuses.append(status)


def _make_dummy_count_update(camera_id: str, frame_id: int, entry: int = 1, exit_: int = 0) -> CountUpdate:
    now_iso = epoch_to_iso8601_utc()
    return CountUpdate(
        cameraId=camera_id,
        farmId="FARM-01",
        zoneId="ZONE-A",
        frameId=frame_id,
        recordedAt=now_iso,
        windowStartedAt=now_iso,
        entryCount=entry,
        exitCount=exit_,
        netChange=entry - exit_,
        deltaEntry=entry,
        deltaExit=exit_,
    )


# ---------------------------------------------------------------------------
# 1. State Store Count History Ring Buffer
# ---------------------------------------------------------------------------
def test_state_store_count_history():
    store = InMemoryAIRuntimeStateStore(max_events=100, max_count_history=5)

    # Initially empty history
    assert store.get_count_history("CAM-01") == []

    # Record 7 count updates (exceeds max_count_history=5)
    for i in range(1, 8):
        update = _make_dummy_count_update("CAM-01", frame_id=i, entry=i, exit_=0)
        store.record_count(update)

    # Should retain exactly 5 newest updates (frames 7, 6, 5, 4, 3) in newest-first order
    history = store.get_count_history("CAM-01", limit=10)
    assert len(history) == 5
    assert [u.frameId for u in history] == [7, 6, 5, 4, 3]

    # Test limit slicing
    sliced = store.get_count_history("CAM-01", limit=2)
    assert len(sliced) == 2
    assert [u.frameId for u in sliced] == [7, 6]

    # Another camera has separate history
    store.record_count(_make_dummy_count_update("CAM-02", frame_id=100))
    cam2_history = store.get_count_history("CAM-02")
    assert len(cam2_history) == 1
    assert cam2_history[0].cameraId == "CAM-02"

    # Unknown camera returns empty list
    assert store.get_count_history("NONEXISTENT") == []

    # Invalid limit raises ValueError
    with pytest.raises(ValueError):
        store.get_count_history("CAM-01", limit=0)

    # Clear resets history
    store.clear()
    assert store.get_count_history("CAM-01") == []


# ---------------------------------------------------------------------------
# 2. CameraPipeline Time Window Rotation
# ---------------------------------------------------------------------------
def test_camera_pipeline_time_window_rotation():
    """Verify count_window_s automatically rolls over counts and resets virtual line counter."""
    sink = RecordingSink()
    frames = [np.zeros((200, 300, 3), dtype=np.uint8) for _ in range(8)]

    # 8 frames at 1 fps starting at t0=100.0:
    # Frame 0: t=100.0, bird at y=40
    # Frame 1: t=101.0, bird at y=70
    # Frame 2: t=102.0, bird at y=140 -> crosses horizontal line at y=100 -> Entry = 1
    # Frame 3: t=103.0, bird at y=160
    # Frame 4: t=104.0, no bird
    # Frame 5: t=105.0 (t - t0 = 5.0 >= window_s = 5.0) -> WINDOW ROLLS OVER! Old window finalized, counter reset to 0.
    #          bird at y=40 (starts new track)
    # Frame 6: t=106.0, bird at y=70
    # Frame 7: t=107.0, bird at y=140 -> crosses line at y=100 -> Entry = 1 in new window!
    scripted_dets: Dict[int, List[TV2Detection]] = {
        0: [TV2Detection("swiftlet", 0.91, [90, 30, 110, 50])],
        1: [TV2Detection("swiftlet", 0.92, [90, 60, 110, 80])],
        2: [TV2Detection("swiftlet", 0.95, [90, 130, 110, 150])],
        3: [TV2Detection("swiftlet", 0.94, [90, 150, 110, 170])],
        4: [],
        5: [TV2Detection("swiftlet", 0.91, [90, 30, 110, 50])],
        6: [TV2Detection("swiftlet", 0.92, [90, 60, 110, 80])],
        7: [TV2Detection("swiftlet", 0.95, [90, 130, 110, 150])],
    }

    step = {"idx": 0}

    def detect_fn(_img):
        i = step["idx"]
        step["idx"] += 1
        return scripted_dets.get(i, [])

    cam_cfg = RuntimeCameraConfig(
        camera_id="CAM-WIN",
        source=ListFrameSource("CAM-WIN", frames, fps=1.0, t0=100.0),
        line=((0.05, 0.50), (0.95, 0.50)),
        inside_side="positive",
    )

    pipeline = CameraPipeline(
        camera_config=cam_cfg,
        detector=CallableDetector(detect_fn),
        tracker=CentroidTracker(max_distance=0.45, max_missed=2),
        predator_monitor=PredatorMonitor(classes=()),
        sink=sink,
        min_track_hits=2,
        count_report_interval_s=10.0,  # only emit on crossing or window roll
        count_window_s=5.0,            # 5-second window
    )

    pipeline.run()

    # Verify count emissions occurred
    assert len(sink.counts) >= 2

    crossing_updates = [c for c in sink.counts if c.entryCount == 1]
    assert len(crossing_updates) >= 2, "Expected entries in both window 1 and window 2"

    w1_start = crossing_updates[0].windowStartedAt
    w2_start = crossing_updates[-1].windowStartedAt
    assert w1_start != w2_start, "Second window must have different windowStartedAt than first"
    assert crossing_updates[-1].entryCount == 1, "New window must have reset to 0 before counting 1 entry"


# ---------------------------------------------------------------------------
# 3. Pipeline & Manager reset_counts
# ---------------------------------------------------------------------------
def test_pipeline_and_manager_reset_counts(tmp_path: Path):
    manager = AIRuntimeManager(
        pipeline_cfg={
            "model": {"path": "models/best.pt"},
            "tracker": {"type": "centroid", "centroid_max_distance": 0.45, "centroid_max_missed": 2},
            "counting": {"inside_side": "positive", "min_track_hits": 2},
        },
        detector=CallableDetector(lambda _img: []),
        base_dir=tmp_path,
    )

    frames = [np.zeros((200, 300, 3), dtype=np.uint8) for _ in range(4)]
    scripted_dets = {
        0: [TV2Detection("swiftlet", 0.91, [90, 30, 110, 50])],
        1: [TV2Detection("swiftlet", 0.92, [90, 60, 110, 80])],
        2: [TV2Detection("swiftlet", 0.95, [90, 130, 110, 150])],  # crossing -> entry = 1
        3: [TV2Detection("swiftlet", 0.94, [90, 150, 110, 170])],
    }
    step = {"i": 0}

    def detect_fn(_img):
        i = step["i"]
        step["i"] += 1
        return scripted_dets.get(i, [])

    cam_cfg = RuntimeCameraConfig(
        camera_id="CAM-RESET",
        source=ListFrameSource("CAM-RESET", frames, fps=10.0, t0=1000.0),
        line=((0.05, 0.50), (0.95, 0.50)),
        inside_side="positive",
    )
    manager.register_camera(cam_cfg, detector=CallableDetector(detect_fn))
    manager.run_camera("CAM-RESET")

    # Camera produced count with entryCount = 1
    latest_before = manager.state_store.get_latest_count("CAM-RESET")
    assert latest_before is not None
    assert latest_before.entryCount == 1

    # Call reset_camera_counts
    reset_update = manager.reset_camera_counts("CAM-RESET")
    assert reset_update.cameraId == "CAM-RESET"
    assert reset_update.entryCount == 0
    assert reset_update.exitCount == 0
    assert reset_update.netChange == 0
    assert reset_update.deltaEntry == 0
    assert reset_update.deltaExit == 0

    # State store updated
    latest_after = manager.state_store.get_latest_count("CAM-RESET")
    assert latest_after is not None
    assert latest_after.entryCount == 0

    # History contains both the pre-reset update and the reset update
    history = manager.state_store.get_count_history("CAM-RESET")
    assert len(history) >= 2
    assert history[0].entryCount == 0  # newest is reset
    assert history[1].entryCount == 1

    # Calling reset on unknown camera raises KeyError
    with pytest.raises(KeyError):
        manager.reset_camera_counts("UNKNOWN_CAMERA")


# ---------------------------------------------------------------------------
# 4. REST Endpoints: counts/reset and counts/history
# ---------------------------------------------------------------------------
def test_rest_counts_reset_and_history(tmp_path: Path):
    manager = AIRuntimeManager(
        pipeline_cfg={
            "model": {"path": "models/best.pt"},
            "tracker": {"type": "centroid", "centroid_max_distance": 0.45, "centroid_max_missed": 2},
            "counting": {"inside_side": "positive", "min_track_hits": 2},
        },
        detector=CallableDetector(lambda _img: []),
        base_dir=tmp_path,
    )

    frames = [np.zeros((200, 300, 3), dtype=np.uint8) for _ in range(4)]
    scripted_dets = {
        0: [TV2Detection("swiftlet", 0.91, [90, 30, 110, 50])],
        1: [TV2Detection("swiftlet", 0.92, [90, 60, 110, 80])],
        2: [TV2Detection("swiftlet", 0.95, [90, 130, 110, 150])],
        3: [TV2Detection("swiftlet", 0.94, [90, 150, 110, 170])],
    }
    step = {"i": 0}

    def detect_fn(_img):
        i = step["i"]
        step["i"] += 1
        return scripted_dets.get(i, [])

    cam_cfg = RuntimeCameraConfig(
        camera_id="CAM-API",
        source=ListFrameSource("CAM-API", frames, fps=10.0, t0=1000.0),
        line=((0.05, 0.50), (0.95, 0.50)),
        inside_side="positive",
    )
    manager.register_camera(cam_cfg, detector=CallableDetector(detect_fn))
    manager.run_camera("CAM-API")

    app = create_app(runtime_manager=manager, snapshot_dir=tmp_path / "snapshots")

    with TestClient(app) as client:
        # Check initial history
        res_hist = client.get("/api/v1/ai/cameras/CAM-API/counts/history?limit=10")
        assert res_hist.status_code == 200
        hist_data = res_hist.json()
        assert len(hist_data) >= 1
        assert hist_data[0]["entryCount"] == 1

        # Reset counts via POST
        res_reset = client.post("/api/v1/ai/cameras/CAM-API/counts/reset")
        assert res_reset.status_code == 200
        reset_body = res_reset.json()
        assert reset_body["cameraId"] == "CAM-API"
        assert reset_body["entryCount"] == 0
        assert reset_body["exitCount"] == 0
        assert reset_body["netChange"] == 0
        assert reset_body["deltaEntry"] == 0
        assert reset_body["deltaExit"] == 0

        # Latest count is now reset
        res_latest = client.get("/api/v1/ai/cameras/CAM-API/counts/latest")
        assert res_latest.status_code == 200
        assert res_latest.json()["entryCount"] == 0

        # History now shows reset count first
        res_hist2 = client.get("/api/v1/ai/cameras/CAM-API/counts/history?limit=5")
        assert res_hist2.status_code == 200
        hist2_data = res_hist2.json()
        assert len(hist2_data) >= 2
        assert hist2_data[0]["entryCount"] == 0

        # Unknown camera returns 404
        assert client.post("/api/v1/ai/cameras/NONEXISTENT/counts/reset").status_code == 404
        assert client.get("/api/v1/ai/cameras/NONEXISTENT/counts/history").status_code == 404


# ---------------------------------------------------------------------------
# 5. WebSocket detection throttling
# ---------------------------------------------------------------------------
def test_websocket_detection_throttling():
    """Verify WebSocketRuntimeSink throttles detection.updated at detection_max_hz without throttling counts/events."""
    ws_manager = AIWebSocketManager(detection_max_hz=5.0)  # max 5 Hz -> 0.2s interval
    sink = ws_manager.sink

    app = create_app(ws_manager=ws_manager)

    with TestClient(app) as client:
        with client.websocket_connect("/ws/ai") as ws:
            # 1. Send 5 detection results in rapid succession (within 0.05s)
            for i in range(5):
                det = DetectionResult(
                    cameraId="CAM-THROTTLE",
                    frameId=i,
                    capturedAt=epoch_to_iso8601_utc(),
                    frame=FrameInfo(width=100, height=100),
                    detections=[],
                )
                sink.on_detection(det)

            ws_manager.flush_sync(timeout=2.0)

            # Receive first message
            first_msg = ws.receive_json()
            assert first_msg["type"] == "detection.updated"
            assert first_msg["data"]["frameId"] == 0

            # 2. Immediately send CountUpdate, AIEvent, CameraRuntimeStatus -> MUST NOT be throttled!
            count_update = _make_dummy_count_update("CAM-THROTTLE", frame_id=1, entry=1)
            ai_event = AIEvent(
                eventId="evt_test_1",
                eventType="PREDATOR_DETECTED",
                cameraId="CAM-THROTTLE",
                frameId=1,
                detectedAt=epoch_to_iso8601_utc(),
                **{"class": "snake"},
                confidence=0.9,
                bbox=BoundingBox.from_xyxy([10, 10, 30, 30]),
            )
            cam_status = CameraRuntimeStatus(
                cameraId="CAM-THROTTLE",
                status="ONLINE",
                sourceConnected=True,
                inferenceStatus="RUNNING",
                fps=25.0,
                modelVersion="best",
                trackerType="centroid",
                processedFrames=10,
                updatedAt=epoch_to_iso8601_utc(),
            )

            sink.on_count(count_update)
            sink.on_event(ai_event)
            sink.on_status(cam_status)

            ws_manager.flush_sync(timeout=2.0)

            msg_cnt = ws.receive_json()
            assert msg_cnt["type"] == "count.updated"

            msg_evt = ws.receive_json()
            assert msg_evt["type"] == "ai.event"

            msg_sts = ws.receive_json()
            assert msg_sts["type"] == "camera.status"

            # 3. Wait for throttle interval to expire (min_interval = 1/5 = 0.2s)
            time.sleep(0.25)
            det_after = DetectionResult(
                cameraId="CAM-THROTTLE",
                frameId=99,
                capturedAt=epoch_to_iso8601_utc(),
                frame=FrameInfo(width=100, height=100),
                detections=[],
            )
            sink.on_detection(det_after)
            ws_manager.flush_sync(timeout=2.0)

            msg_det2 = ws.receive_json()
            assert msg_det2["type"] == "detection.updated"
            assert msg_det2["data"]["frameId"] == 99


# ---------------------------------------------------------------------------
# 6. Snapshot Pruning (snapshot.max_files)
# ---------------------------------------------------------------------------
def test_snapshot_pruning_max_files(tmp_path: Path):
    snap_dir = tmp_path / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)

    # Initialize PruningSnapshotStore with max_files = 3
    store = PruningSnapshotStore(directory=str(snap_dir), max_files=3)
    dummy_img = np.zeros((32, 32, 3), dtype=np.uint8)

    # Save 5 snapshots sequentially with slightly spaced timestamps
    created_paths = []
    for i in range(5):
        t = 1000.0 + i * 10.0
        ref = store.save(dummy_img, camera_id="CAM-01", event_type="test", timestamp=t)
        created_paths.append(Path(ref))
        time.sleep(0.02)  # ensure different filesystem mtimes

    # Exactly 3 files remain
    existing_files = list(snap_dir.glob("*.jpg"))
    assert len(existing_files) == 3

    # Oldest 2 files (from i=0 and i=1) must have been removed
    assert not created_paths[0].exists()
    assert not created_paths[1].exists()
    # Newest 3 files (from i=2, 3, 4) must exist
    assert created_paths[2].exists()
    assert created_paths[3].exists()
    assert created_paths[4].exists()

    # Test AIRuntimeManager.prune_snapshots(max_files=1)
    manager = AIRuntimeManager(
        pipeline_cfg={"snapshot": {"dir": str(snap_dir), "max_files": 3}},
        snapshot_store=store,
        detector=CallableDetector(lambda _img: []),
        base_dir=tmp_path,
    )
    deleted = manager.prune_snapshots(max_files=1)
    assert deleted == 2
    assert len(list(snap_dir.glob("*.jpg"))) == 1
