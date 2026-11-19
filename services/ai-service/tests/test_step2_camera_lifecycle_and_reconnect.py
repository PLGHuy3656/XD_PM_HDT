"""Tests verifying Step 2: Camera lifecycle (start/stop via REST/manager), autostart, and live reconnect."""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Iterator, List

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import RuntimeCameraConfig
from app.main import create_app
from app.runtime.camera_pipeline import CameraPipeline
from app.runtime.manager import AIRuntimeManager
from swiftletcare_ai.detector import CallableDetector
from swiftletcare_ai.predator import PredatorMonitor
from swiftletcare_ai.schemas import FramePacket
from swiftletcare_ai.tracker import CentroidTracker
from swiftletcare_ai.video_source import FrameSource


class MockRtspFrameSource(FrameSource):
    """Mock RTSP live stream source with controllable failures for reconnect testing."""

    def __init__(self, camera_id: str, fps: float = 10.0):
        self.camera_id = camera_id
        self.fps = fps
        self.kind = "rtsp"
        self.open_count = 0
        self.closed = False
        self._frame_id = 0

    def __iter__(self) -> Iterator[FramePacket]:
        self.open_count += 1
        self.closed = False
        if self.open_count == 1:
            # Yield 2 frames then disconnect
            for _ in range(2):
                self._frame_id += 1
                yield FramePacket(self.camera_id, self._frame_id, 1000.0 + self._frame_id * 0.1, np.ones((64, 64, 3), dtype=np.uint8) * 128)
            raise ConnectionResetError("RTSP connection reset by peer")
        elif self.open_count == 2:
            # Reconnect attempt 2 fails immediately on open
            raise TimeoutError("RTSP connection timed out")
        else:
            # Reconnect attempt 3 succeeds and keeps streaming
            while not self.closed:
                self._frame_id += 1
                yield FramePacket(self.camera_id, self._frame_id, 1000.0 + self._frame_id * 0.1, np.ones((64, 64, 3), dtype=np.uint8) * 128)
                time.sleep(0.01)

    def close(self) -> None:
        self.closed = True


class AlwaysFailingRtspSource(FrameSource):
    """Mock RTSP stream that always fails to open."""

    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        self.fps = 10.0
        self.kind = "rtsp"

    def __iter__(self) -> Iterator[FramePacket]:
        raise ConnectionRefusedError("RTSP connection refused")

    def close(self) -> None:
        pass


def test_rest_api_start_stop_camera(tmp_path: Path):
    """Verify POST /api/v1/ai/cameras/{cameraId}/start and /stop via REST API."""
    manager = AIRuntimeManager()
    dummy_source = MockRtspFrameSource("CAM-TEST-01")

    cam_cfg = RuntimeCameraConfig(
        camera_id="CAM-TEST-01",
        source=dummy_source,
        source_type="rtsp",
    )
    manager.register_camera(
        cam_cfg,
        detector=CallableDetector(lambda _img: []),
        tracker=CentroidTracker(),
        predator_monitor=PredatorMonitor(),
    )

    app = create_app(runtime_manager=manager, snapshot_dir=tmp_path / "snaps")
    client = TestClient(app)

    # 1. 404 on unknown camera
    res_unknown_start = client.post("/api/v1/ai/cameras/UNKNOWN-CAM/start")
    assert res_unknown_start.status_code == 404
    assert res_unknown_start.json()["detail"]["code"] == "CAMERA_NOT_FOUND"

    res_unknown_stop = client.post("/api/v1/ai/cameras/UNKNOWN-CAM/stop")
    assert res_unknown_stop.status_code == 404
    assert res_unknown_stop.json()["detail"]["code"] == "CAMERA_NOT_FOUND"

    # 2. Start camera
    res_start = client.post("/api/v1/ai/cameras/CAM-TEST-01/start")
    assert res_start.status_code == 200
    assert manager.is_running("CAM-TEST-01")

    # 3. Idempotent start on running camera
    res_start_dup = client.post("/api/v1/ai/cameras/CAM-TEST-01/start")
    assert res_start_dup.status_code == 200

    # Let worker run briefly
    time.sleep(0.1)

    # 4. Stop camera
    res_stop = client.post("/api/v1/ai/cameras/CAM-TEST-01/stop")
    assert res_stop.status_code == 200
    assert not manager.is_running("CAM-TEST-01")
    assert res_stop.json()["status"] == "OFFLINE"


def test_live_stream_reconnect_simulation():
    """Verify live stream (kind='rtsp') reconnects after error and recovers to ONLINE."""
    source = MockRtspFrameSource("CAM-RECONNECT-01")
    observed_statuses: List[str] = []

    cam_cfg = RuntimeCameraConfig(
        camera_id="CAM-RECONNECT-01",
        source=source,
        source_type="rtsp",
    )

    pipeline = CameraPipeline(
        camera_config=cam_cfg,
        detector=CallableDetector(lambda _img: []),
        tracker=CentroidTracker(),
        predator_monitor=PredatorMonitor(),
        max_reconnects=5,
        reconnect_delay_s=0.02,
    )

    def stop_after_delay():
        # Wait until reconnect succeeds and yields more frames
        for _ in range(50):
            time.sleep(0.05)
            if source.open_count >= 3 and pipeline.status.status == "ONLINE":
                break
        pipeline.stop()

    stopper = threading.Thread(target=stop_after_delay, daemon=True)
    stopper.start()

    final_status = pipeline.run()
    stopper.join(timeout=2.0)

    # Pipeline should have opened 3 times (initial + fail retry + success retry)
    assert source.open_count >= 3
    # At least 3 frames processed across cycles
    assert final_status.processedFrames >= 3
    assert final_status.status == "OFFLINE"


def test_live_stream_reconnect_exceeded_retries_transitions_to_error():
    """Verify that exceeding max_reconnects transitions the pipeline status to ERROR (STREAM_LOST)."""
    source = AlwaysFailingRtspSource("CAM-FAIL-01")

    cam_cfg = RuntimeCameraConfig(
        camera_id="CAM-FAIL-01",
        source=source,
        source_type="rtsp",
    )

    pipeline = CameraPipeline(
        camera_config=cam_cfg,
        detector=CallableDetector(lambda _img: []),
        tracker=CentroidTracker(),
        predator_monitor=PredatorMonitor(),
        max_reconnects=2,
        reconnect_delay_s=0.01,
    )

    final_status = pipeline.run()
    assert final_status.status == "ERROR"
    assert final_status.errorCode == "STREAM_LOST"


def test_autostart_cameras_on_lifespan(tmp_path: Path, monkeypatch):
    """Verify that cameras marked with autostart=True in cameras.yaml are started by app lifespan."""
    fake_pipeline_dir = tmp_path / "ai-pipeline"
    configs_dir = fake_pipeline_dir / "configs"
    configs_dir.mkdir(parents=True)

    cameras_yaml = configs_dir / "cameras.yaml"
    cameras_yaml.write_text(
        """
cameras:
  - camera_id: CAM-AUTO-01
    source: dummy.mp4
    source_type: auto
    autostart: true
  - camera_id: CAM-MANUAL-01
    source: dummy.mp4
    source_type: auto
    autostart: false
""",
        encoding="utf-8",
    )

    import app.main as main_mod

    monkeypatch.setattr(main_mod, "AI_PIPELINE_DIR", fake_pipeline_dir)

    manager = AIRuntimeManager()
    started_cams = []

    def mock_start(cid: str, max_frames: int = 0):
        started_cams.append(cid)
        return manager.get_pipeline(cid).status

    monkeypatch.setattr(manager, "start_camera", mock_start)

    app = create_app(
        runtime_manager=manager,
        load_configured_cameras=True,
    )

    with TestClient(app):
        # Lifespan executes upon entering TestClient context
        assert "CAM-AUTO-01" in started_cams
        assert "CAM-MANUAL-01" not in started_cams

