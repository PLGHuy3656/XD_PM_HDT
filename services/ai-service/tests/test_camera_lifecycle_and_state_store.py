"""Tests for CameraRuntimeStatus lifecycle transitions, RuntimeEventSink dispatch, and InMemoryAIRuntimeStateStore (CP5.2 Task 5, 6, 9, 11.9-11.11)."""
from __future__ import annotations

from typing import List

import numpy as np
import pytest

from app.config import RuntimeCameraConfig
from app.runtime.camera_pipeline import CameraPipeline
from app.runtime.sink import CallbackRuntimeSink, CompositeRuntimeSink
from app.runtime.state_store import InMemoryAIRuntimeStateStore
from app.schemas.canonical import (
    AIEvent,
    CameraRuntimeStatus,
    CountUpdate,
    DetectionResult,
)
from swiftletcare_ai.detector import BaseDetector, CallableDetector
from swiftletcare_ai.predator import PredatorMonitor
from swiftletcare_ai.schemas import Detection as TV2Detection, FramePacket
from swiftletcare_ai.tracker import CentroidTracker
from swiftletcare_ai.video_source import FrameSource, ListFrameSource


# ---------------------------------------------------------------------------
# 1. Camera Lifecycle Transitions (STARTING -> ONLINE -> DEGRADED -> OFFLINE, -> ERROR)
# ---------------------------------------------------------------------------
def test_camera_lifecycle_starting_to_online_to_offline():
    statuses: List[CameraRuntimeStatus] = []
    sink = CallbackRuntimeSink(on_status=statuses.append)

    frames = [np.zeros((120, 160, 3), dtype=np.uint8) for _ in range(3)]
    cam_cfg = RuntimeCameraConfig(
        camera_id="CAM-LIFE-01",
        farm_id="FARM-01",
        zone_id="ZONE-A",
        source=ListFrameSource("CAM-LIFE-01", frames, fps=20.0, t0=1_761_489_800.0),
    )

    pipeline = CameraPipeline(
        camera_config=cam_cfg,
        detector=CallableDetector(lambda _img: []),
        tracker=CentroidTracker(),
        predator_monitor=PredatorMonitor(),
        sink=sink,
        tracker_type="centroid",
    )

    # Initial status emitted at construction is STARTING
    assert len(statuses) == 1
    assert statuses[0].status == "STARTING"
    assert statuses[0].sourceConnected is False

    final_status = pipeline.run()
    assert final_status.status == "OFFLINE"
    assert final_status.inferenceStatus == "STOPPED"
    assert final_status.sourceConnected is False
    assert final_status.processedFrames == 3
    assert final_status.width == 160
    assert final_status.height == 120
    assert final_status.lastFrameAt is not None

    observed_states = [s.status for s in statuses]
    assert observed_states == ["STARTING", "ONLINE", "OFFLINE"]


def test_camera_lifecycle_degraded_on_low_fps_or_invalid_frame_and_recovers():
    statuses: List[CameraRuntimeStatus] = []
    sink = CallbackRuntimeSink(on_status=statuses.append)

    cam_cfg = RuntimeCameraConfig(
        camera_id="CAM-DEG-01",
        source=ListFrameSource("CAM-DEG-01", [], fps=10.0),
    )
    pipeline = CameraPipeline(
        camera_config=cam_cfg,
        detector=CallableDetector(lambda _img: []),
        tracker=CentroidTracker(),
        predator_monitor=PredatorMonitor(),
        sink=sink,
        degraded_fps_threshold=10.0,
    )

    valid_img = np.zeros((100, 100, 3), dtype=np.uint8)
    # Frame 0: STARTING -> ONLINE
    pipeline.process_packet(FramePacket("CAM-DEG-01", 0, 1000.0, valid_img))
    assert pipeline.status.status == "ONLINE"

    # Frame 1 arrives 2.0s later (0.5 FPS < degraded_fps_threshold=10.0) -> DEGRADED
    pipeline.process_packet(FramePacket("CAM-DEG-01", 1, 1002.0, valid_img))
    assert pipeline.status.status == "DEGRADED"
    assert pipeline.status.errorCode == "LOW_FPS"

    # Empty frame also keeps/marks DEGRADED without crashing
    res = pipeline.process_packet(FramePacket("CAM-DEG-01", 2, 1002.05, np.array([])))
    assert res is None
    assert pipeline.status.status == "DEGRADED"

    # Close transitions DEGRADED -> OFFLINE
    pipeline.close()
    assert pipeline.status.status == "OFFLINE"

    state_sequence = [s.status for s in statuses]
    assert state_sequence == ["STARTING", "ONLINE", "DEGRADED", "OFFLINE"]


def test_camera_lifecycle_transitions_to_error_on_source_failure():
    statuses: List[CameraRuntimeStatus] = []
    sink = CallbackRuntimeSink(on_status=statuses.append)

    cam_cfg = RuntimeCameraConfig(
        camera_id="CAM-ERR-SRC",
        source="nonexistent_video_file_that_does_not_exist.mp4",
    )
    pipeline = CameraPipeline(
        camera_config=cam_cfg,
        detector=CallableDetector(lambda _img: []),
        tracker=CentroidTracker(),
        predator_monitor=PredatorMonitor(),
        sink=sink,
    )

    with pytest.raises(OSError):
        pipeline.run()

    assert pipeline.status.status == "ERROR"
    assert pipeline.status.inferenceStatus == "ERROR"
    assert pipeline.status.errorCode == "SOURCE_OPEN_FAILED"
    assert pipeline.status.errorMessage is not None
    assert [s.status for s in statuses] == ["STARTING", "ERROR"]


def test_camera_lifecycle_transitions_to_error_on_detector_exception():
    class FailingDetector(BaseDetector):
        def detect(self, image):
            raise RuntimeError("Simulated detector crash")

    statuses: List[CameraRuntimeStatus] = []
    sink = CallbackRuntimeSink(on_status=statuses.append)
    frames = [np.zeros((100, 100, 3), dtype=np.uint8)]
    cam_cfg = RuntimeCameraConfig(
        camera_id="CAM-ERR-DET",
        source=ListFrameSource("CAM-ERR-DET", frames, fps=10.0),
    )
    pipeline = CameraPipeline(
        camera_config=cam_cfg,
        detector=FailingDetector(),
        tracker=CentroidTracker(),
        predator_monitor=PredatorMonitor(),
        sink=sink,
    )

    with pytest.raises(RuntimeError, match="Simulated detector crash"):
        pipeline.run()

    assert pipeline.status.status == "ERROR"
    assert pipeline.status.errorCode == "INFERENCE_ERROR"
    assert [s.status for s in statuses] == ["STARTING", "ERROR"]


# ---------------------------------------------------------------------------
# 2. CompositeRuntimeSink & InMemoryAIRuntimeStateStore
# ---------------------------------------------------------------------------
def test_composite_sink_fanout_and_error_isolation():
    store = InMemoryAIRuntimeStateStore(max_events=3)
    callback_calls: List[str] = []

    class BrokenSink(CallbackRuntimeSink):
        def on_detection(self, result):
            raise ValueError("sink failure should be isolated")

    good_sink = CallbackRuntimeSink(
        on_detection=lambda r: callback_calls.append(f"det:{r.frameId}"),
        on_count=lambda c: callback_calls.append(f"cnt:{c.entryCount}"),
        on_event=lambda e: callback_calls.append(f"evt:{e.eventId}"),
        on_status=lambda s: callback_calls.append(f"sts:{s.status}"),
    )

    composite = CompositeRuntimeSink([BrokenSink(), store, good_sink], isolate_errors=True)

    frames = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in range(3)]
    cam_cfg = RuntimeCameraConfig(
        camera_id="CAM-SINK-01",
        farm_id="FARM-01",
        zone_id="ZONE-A",
        source=ListFrameSource("CAM-SINK-01", frames, fps=10.0, t0=1_761_489_900.0),
    )

    pipeline = CameraPipeline(
        camera_config=cam_cfg,
        detector=CallableDetector(lambda _img: [TV2Detection("rat", 0.9, [10, 10, 40, 40])]),
        tracker=CentroidTracker(),
        predator_monitor=PredatorMonitor(min_consecutive_frames=2, cooldown_s=30.0),
        sink=composite,
    )
    pipeline.run()

    assert store.get_latest_detection("CAM-SINK-01") is not None
    assert store.get_latest_detection("CAM-SINK-01").frameId == 2
    assert store.get_latest_count("CAM-SINK-01") is not None
    assert store.get_camera_status("CAM-SINK-01").status == "OFFLINE"
    assert len(store.list_events("CAM-SINK-01")) == 1
    assert any(c.startswith("det:") for c in callback_calls)
    assert any(c.startswith("evt:") for c in callback_calls)


def test_state_store_event_ring_buffer_eviction_and_lookup():
    store = InMemoryAIRuntimeStateStore(max_events=2)
    for i in range(4):
        ev = AIEvent(
            **{
                "eventId": f"evt_{i}",
                "eventType": "PREDATOR_DETECTED",
                "cameraId": "CAM-01" if i % 2 == 0 else "CAM-02",
                "frameId": i,
                "detectedAt": "2026-10-26T14:40:12.000Z",
                "class": "rat",
                "confidence": 0.85,
                "bbox": {"x1": 10, "y1": 10, "x2": 30, "y2": 30},
            }
        )
        store.record_event(ev)

    # Only newest 2 events (evt_2, evt_3) should remain
    events = store.list_events()
    assert [e.eventId for e in events] == ["evt_3", "evt_2"]
    assert store.get_event("evt_0") is None
    assert store.get_event("evt_1") is None
    assert store.get_event("evt_2") is not None
    assert [e.eventId for e in store.list_events(camera_id="CAM-01")] == ["evt_2"]
