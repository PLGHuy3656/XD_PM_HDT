"""End-to-end synthetic pipeline integration and real best.pt inference tests (CP5.2 Task 10, 11.12, 12)."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np
import pytest

from app.config import AI_PIPELINE_DIR, RuntimeCameraConfig
from app.runtime.manager import AIRuntimeManager
from swiftletcare_ai.detector import CallableDetector, YoloDetector
from swiftletcare_ai.schemas import Detection as TV2Detection
from swiftletcare_ai.snapshot import SnapshotStore
from swiftletcare_ai.video_source import ListFrameSource


def test_no_standalone_preprocessing_module_exists():
    """Task 10: Confirm preprocessing remains encapsulated in YoloDetector, not a fake preprocessing.py."""
    assert not (AI_PIPELINE_DIR / "src" / "swiftletcare_ai" / "preprocessing.py").exists()
    service_app_dir = Path(__file__).resolve().parent.parent / "app"
    assert not (service_app_dir / "preprocessing.py").exists()


def test_ai_runtime_manager_synthetic_end_to_end_pipeline(tmp_path: Path):
    """Task 11.12: Full synthetic pipeline orchestration via AIRuntimeManager."""
    frames = [np.zeros((200, 300, 3), dtype=np.uint8) for _ in range(6)]
    # Line at y = 100 (0.5 * 200), inside_side="positive"
    # Swiftlet 1 crosses into positive side (entry)
    # Swiftlet 2 crosses into negative side (exit)
    # Snake appears for 3 consecutive frames (predator alert)
    scripted: Dict[int, List[TV2Detection]] = {
        0: [
            TV2Detection("swiftlet", 0.92, [50, 30, 70, 50]),
            TV2Detection("swiftlet", 0.89, [200, 140, 220, 160]),
        ],
        1: [
            TV2Detection("swiftlet", 0.93, [50, 70, 70, 90]),
            TV2Detection("swiftlet", 0.88, [200, 115, 220, 135]),
        ],
        2: [
            TV2Detection("swiftlet", 0.95, [50, 130, 70, 150]),  # Swiftlet 1 ENTRY
            TV2Detection("swiftlet", 0.90, [200, 50, 220, 70]),    # Swiftlet 2 EXIT
            TV2Detection("snake", 0.85, [10, 150, 60, 190]),
        ],
        3: [
            TV2Detection("snake", 0.89, [12, 150, 62, 190]),
        ],
        4: [
            TV2Detection("snake", 0.93, [14, 150, 64, 190]),      # 3rd consecutive frame -> AIEvent
        ],
        5: [
            TV2Detection("swiftlet", 0.91, [120, 30, 140, 50]),
        ],
    }

    idx = {"i": 0}

    def detect_fn(_img):
        f = idx["i"]
        idx["i"] += 1
        return scripted.get(f, [])

    pipeline_cfg = {
        "model": {"path": "models/best.pt", "imgsz": 640},
        "tracker": {"type": "centroid", "centroid_max_distance": 0.4, "centroid_max_missed": 2},
        "counting": {"inside_side": "positive", "report_interval_s": 5.0, "min_track_hits": 2},
        "predator": {
            "classes": ["rat", "snake"],
            "conf_threshold": {"rat": 0.5, "snake": 0.5},
            "min_consecutive_frames": 3,
            "cooldown_s": 30.0,
        },
    }

    snap_store = SnapshotStore(directory=str(tmp_path / "snaps"), public_base_url="/snapshots")
    manager = AIRuntimeManager(
        pipeline_cfg=pipeline_cfg,
        detector=CallableDetector(detect_fn),
        snapshot_store=snap_store,
    )

    cam_cfg = RuntimeCameraConfig(
        camera_id="CAM-SYN-01",
        farm_id="FARM-01",
        zone_id="ZONE-A",
        source=ListFrameSource("CAM-SYN-01", frames, fps=10.0, t0=1_761_490_000.0),
        line=((0.05, 0.50), (0.95, 0.50)),
        inside_side="positive",
    )
    manager.register_camera(cam_cfg)
    assert manager.list_camera_ids() == ["CAM-SYN-01"]

    final_status = manager.run_camera("CAM-SYN-01")
    assert final_status.status == "OFFLINE"
    assert final_status.processedFrames == 6

    latest_count = manager.state_store.get_latest_count("CAM-SYN-01")
    assert latest_count is not None
    assert latest_count.entryCount == 1
    assert latest_count.exitCount == 1
    assert latest_count.netChange == 0

    latest_det = manager.state_store.get_latest_detection("CAM-SYN-01")
    assert latest_det is not None
    assert latest_det.frameId == 5
    assert latest_det.frame.to_dict() == {"width": 300, "height": 200}
    assert len(latest_det.detections) == 1
    assert latest_det.detections[0].trackId is not None

    events = manager.state_store.list_events("CAM-SYN-01")
    assert len(events) == 1
    assert events[0].eventType == "PREDATOR_DETECTED"
    assert events[0].cls == "snake"
    assert events[0].confidence == 0.93


def test_real_yolo26_best_pt_inference_through_camera_pipeline(tmp_path: Path):
    """Separate real-model CPU integration test using TV2's actual models/best.pt weights."""
    weights_path = AI_PIPELINE_DIR / "models" / "best.pt"
    if not weights_path.exists():
        pytest.skip("models/best.pt not found")
    pytest.importorskip("ultralytics")

    detector = YoloDetector(
        model_path=str(weights_path),
        imgsz=640,
        device="cpu",
        min_conf=0.15,
        iou=0.5,
    )
    assert set(detector.names.values()) == {"swiftlet", "rat", "snake"}

    # Non-square 720p frame to verify Ultralytics internal letterbox preprocessing + bbox rescaling
    frames = [np.zeros((720, 1280, 3), dtype=np.uint8)]
    manager = AIRuntimeManager(
        pipeline_cfg={"model": {"path": "models/best.pt"}, "tracker": {"type": "bytetrack"}},
        detector=detector,
        snapshot_store=SnapshotStore(directory=str(tmp_path / "snaps")),
    )
    manager.register_camera(
        RuntimeCameraConfig(
            camera_id="CAM-REAL-01",
            farm_id="FARM-01",
            zone_id="ZONE-A",
            source=ListFrameSource("CAM-REAL-01", frames, fps=15.0, t0=1_761_490_100.0),
        )
    )
    status = manager.run_camera("CAM-REAL-01")
    assert status.status == "OFFLINE"
    assert status.processedFrames == 1
    assert status.width == 1280
    assert status.height == 720
    assert status.trackerType == "bytetrack"

    latest_det = manager.state_store.get_latest_detection("CAM-REAL-01")
    assert latest_det is not None
    assert latest_det.frame.to_dict() == {"width": 1280, "height": 720}
    assert "timestamp" not in latest_det.to_dict()
