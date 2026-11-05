"""Comprehensive tests for AI Service REST API V1, WebSocket V1, Snapshot security,
Thread->Async bridge, and Architecture boundaries (CP5.3 Task 15 & Task 16.1-16.25).
"""
from __future__ import annotations

import ast
import threading
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import RuntimeCameraConfig
from app.main import create_app
from app.runtime.manager import AIRuntimeManager
from app.schemas.canonical import (
    AIEvent,
    CameraRuntimeStatus,
    CountUpdate,
    DetectionResult,
)
from app.websocket.manager import AIWebSocketManager
from swiftletcare_ai.detector import CallableDetector
from swiftletcare_ai.schemas import Detection as TV2Detection
from swiftletcare_ai.snapshot import SnapshotStore
from swiftletcare_ai.video_source import ListFrameSource


def _make_synthetic_manager(tmp_path: Path) -> AIRuntimeManager:
    snap_dir = tmp_path / "snapshots"
    snap_store = SnapshotStore(directory=str(snap_dir), public_base_url="")
    pipeline_cfg = {
        "model": {"path": "models/best.pt", "imgsz": 640},
        "tracker": {"type": "centroid", "centroid_max_distance": 0.45, "centroid_max_missed": 2},
        "counting": {"inside_side": "positive", "report_interval_s": 5.0, "min_track_hits": 2},
        "predator": {
            "classes": ["rat", "snake"],
            "conf_threshold": {"rat": 0.5, "snake": 0.5},
            "min_consecutive_frames": 2,
            "cooldown_s": 30.0,
        },
        "snapshot": {"dir": str(snap_dir), "public_base_url": ""},
    }
    return AIRuntimeManager(
        pipeline_cfg=pipeline_cfg,
        detector=CallableDetector(lambda _img: []),
        snapshot_store=snap_store,
    )


def _register_and_run_scripted_camera(
    manager: AIRuntimeManager,
    camera_id: str = "CAM-01",
    farm_id: str = "FARM-01",
    zone_id: str = "ZONE-A",
) -> None:
    frames = [np.zeros((200, 300, 3), dtype=np.uint8) for _ in range(4)]
    # Line at y=100; bird crosses from y=40 -> y=70 -> y=140 (1 entry on frame 2)
    # Snake appears on frames 1 and 2 (min_consecutive_frames=2 -> 1 predator AIEvent on frame 2)
    scripted: Dict[int, List[TV2Detection]] = {
        0: [TV2Detection("swiftlet", 0.91, [90, 30, 110, 50])],
        1: [
            TV2Detection("swiftlet", 0.92, [90, 60, 110, 80]),
            TV2Detection("snake", 0.88, [20, 140, 70, 190]),
        ],
        2: [
            TV2Detection("swiftlet", 0.95, [90, 130, 110, 150]),
            TV2Detection("snake", 0.93, [22, 142, 72, 192]),
        ],
        3: [TV2Detection("swiftlet", 0.94, [90, 150, 110, 170])],
    }
    idx = {"i": 0}

    def detect_fn(_img):
        f = idx["i"]
        idx["i"] += 1
        return scripted.get(f, [])

    cam_cfg = RuntimeCameraConfig(
        camera_id=camera_id,
        farm_id=farm_id,
        zone_id=zone_id,
        source=ListFrameSource(camera_id, frames, fps=10.0, t0=1_761_500_000.0),
        line=((0.05, 0.50), (0.95, 0.50)),
        inside_side="positive",
    )
    manager.register_camera(cam_cfg, detector=CallableDetector(detect_fn))
    manager.run_camera(camera_id)


# ---------------------------------------------------------------------------
# REST 1-4: /health, camera list, camera status, unknown camera 404
# ---------------------------------------------------------------------------
def test_1_health_endpoint(tmp_path: Path):
    manager = _make_synthetic_manager(tmp_path)
    app = create_app(runtime_manager=manager, snapshot_dir=tmp_path / "snapshots")
    with TestClient(app) as client:
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json() == {"service": "ai-service", "status": "ok"}


def test_2_and_3_camera_list_and_camera_status(tmp_path: Path):
    manager = _make_synthetic_manager(tmp_path)
    _register_and_run_scripted_camera(manager, camera_id="CAM-01")
    manager.register_camera(
        RuntimeCameraConfig(
            camera_id="CAM-02",
            farm_id="FARM-01",
            zone_id="ZONE-B",
            source=ListFrameSource("CAM-02", [], fps=10.0),
        )
    )

    app = create_app(runtime_manager=manager, snapshot_dir=tmp_path / "snapshots")
    with TestClient(app) as client:
        list_res = client.get("/api/v1/ai/cameras")
        assert list_res.status_code == 200
        cameras = list_res.json()
        assert [c["cameraId"] for c in cameras] == ["CAM-01", "CAM-02"]
        assert cameras[0]["status"] == "OFFLINE"
        assert cameras[0]["processedFrames"] == 4
        assert cameras[1]["status"] == "STARTING"
        assert cameras[1]["processedFrames"] == 0

        status_res = client.get("/api/v1/ai/cameras/CAM-01/status")
        assert status_res.status_code == 200
        status_body = status_res.json()
        assert status_body["cameraId"] == "CAM-01"
        assert status_body["farmId"] == "FARM-01"
        assert status_body["zoneId"] == "ZONE-A"
        assert status_body["width"] == 300
        assert status_body["height"] == 200
        assert "timestamp" not in status_body


def test_4_unknown_camera_returns_404_camera_not_found(tmp_path: Path):
    manager = _make_synthetic_manager(tmp_path)
    app = create_app(runtime_manager=manager, snapshot_dir=tmp_path / "snapshots")
    with TestClient(app) as client:
        for subpath in ("status", "detections/latest", "counts/latest"):
            res = client.get(f"/api/v1/ai/cameras/CAM-UNKNOWN/{subpath}")
            assert res.status_code == 404
            assert res.json() == {
                "detail": {
                    "code": "CAMERA_NOT_FOUND",
                    "message": "Camera 'CAM-UNKNOWN' is not registered in AI runtime.",
                }
            }


# ---------------------------------------------------------------------------
# REST 5-8: Latest detection & count + unavailable 404 contracts
# ---------------------------------------------------------------------------
def test_5_and_6_latest_detection_and_detection_unavailable(tmp_path: Path):
    manager = _make_synthetic_manager(tmp_path)
    # Register CAM-IDLE without running any frames
    manager.register_camera(
        RuntimeCameraConfig(
            camera_id="CAM-IDLE",
            source=ListFrameSource("CAM-IDLE", [], fps=10.0),
        )
    )
    _register_and_run_scripted_camera(manager, camera_id="CAM-01")

    app = create_app(runtime_manager=manager, snapshot_dir=tmp_path / "snapshots")
    with TestClient(app) as client:
        # Registered camera with no frames yet -> 404 DETECTION_NOT_AVAILABLE
        unavail = client.get("/api/v1/ai/cameras/CAM-IDLE/detections/latest")
        assert unavail.status_code == 404
        assert unavail.json()["detail"]["code"] == "DETECTION_NOT_AVAILABLE"

        # Active/processed camera -> 200 DetectionResult
        det_res = client.get("/api/v1/ai/cameras/CAM-01/detections/latest")
        assert det_res.status_code == 200
        body = det_res.json()
        assert body["cameraId"] == "CAM-01"
        assert body["frameId"] == 3
        assert body["frame"] == {"width": 300, "height": 200}
        assert "timestamp" not in body
        assert len(body["detections"]) == 1
        assert body["detections"][0]["class"] == "swiftlet"
        assert "bboxNormalized" not in body["detections"][0]
        assert body["detections"][0]["bbox"] == {
            "x1": 90.0,
            "y1": 150.0,
            "x2": 110.0,
            "y2": 170.0,
        }


def test_7_and_8_latest_count_and_count_unavailable(tmp_path: Path):
    manager = _make_synthetic_manager(tmp_path)
    manager.register_camera(
        RuntimeCameraConfig(
            camera_id="CAM-IDLE",
            source=ListFrameSource("CAM-IDLE", [], fps=10.0),
        )
    )
    _register_and_run_scripted_camera(manager, camera_id="CAM-01")

    app = create_app(runtime_manager=manager, snapshot_dir=tmp_path / "snapshots")
    with TestClient(app) as client:
        unavail = client.get("/api/v1/ai/cameras/CAM-IDLE/counts/latest")
        assert unavail.status_code == 404
        assert unavail.json()["detail"]["code"] == "COUNT_NOT_AVAILABLE"

        cnt_res = client.get("/api/v1/ai/cameras/CAM-01/counts/latest")
        assert cnt_res.status_code == 200
        body = cnt_res.json()
        assert body["cameraId"] == "CAM-01"
        assert body["entryCount"] == 1
        assert body["exitCount"] == 0
        assert body["netChange"] == 1
        assert body["deltaEntry"] == 1
        assert body["deltaExit"] == 0
        assert "occupancy" not in body
        assert "currentBirdCount" not in body
        assert "totalBirdPopulation" not in body
        assert "timestamp" not in body


# ---------------------------------------------------------------------------
# REST 9-12: AI Events list, cameraId filtering, eventId lookup, 404
# ---------------------------------------------------------------------------
def test_9_to_12_events_list_filtering_lookup_and_not_found(tmp_path: Path):
    manager = _make_synthetic_manager(tmp_path)
    _register_and_run_scripted_camera(manager, camera_id="CAM-01")
    _register_and_run_scripted_camera(manager, camera_id="CAM-02")

    app = create_app(runtime_manager=manager, snapshot_dir=tmp_path / "snapshots")
    with TestClient(app) as client:
        all_res = client.get("/api/v1/ai/events")
        assert all_res.status_code == 200
        all_events = all_res.json()
        assert len(all_events) == 2

        # Filter by cameraId
        cam1_res = client.get("/api/v1/ai/events", params={"cameraId": "CAM-01"})
        assert cam1_res.status_code == 200
        cam1_events = cam1_res.json()
        assert len(cam1_events) == 1
        ev = cam1_events[0]
        assert ev["cameraId"] == "CAM-01"
        assert ev["eventType"] == "PREDATOR_DETECTED"
        assert ev["class"] == "snake"
        assert ev["snapshot"].startswith("/api/v1/ai/snapshots/CAM-01_snake_")
        assert ":\\" not in ev["snapshot"]  # Never expose raw Windows drive path

        # Limit parameter
        lim_res = client.get("/api/v1/ai/events", params={"limit": 1})
        assert lim_res.status_code == 200
        assert len(lim_res.json()) == 1

        # Lookup by eventId
        by_id_res = client.get(f"/api/v1/ai/events/{ev['eventId']}")
        assert by_id_res.status_code == 200
        assert by_id_res.json() == ev

        # Unknown eventId -> 404 EVENT_NOT_FOUND
        missing_res = client.get("/api/v1/ai/events/evt_ai_nonexistent")
        assert missing_res.status_code == 404
        assert missing_res.json()["detail"]["code"] == "EVENT_NOT_FOUND"


# ---------------------------------------------------------------------------
# REST 13-14: Snapshot serving & path traversal security
# ---------------------------------------------------------------------------
def test_13_and_14_snapshot_serving_and_path_traversal_rejection(tmp_path: Path):
    manager = _make_synthetic_manager(tmp_path)
    _register_and_run_scripted_camera(manager, camera_id="CAM-01")

    # Create a secret file outside snapshots directory to test traversal protection
    secret_file = tmp_path / "secret.jpg"
    secret_file.write_bytes(b"top-secret")

    app = create_app(runtime_manager=manager, snapshot_dir=tmp_path / "snapshots")
    with TestClient(app) as client:
        events = client.get("/api/v1/ai/events").json()
        snapshot_url = events[0]["snapshot"]
        assert snapshot_url.startswith("/api/v1/ai/snapshots/")

        # 13. Valid snapshot serves JPEG bytes
        snap_res = client.get(snapshot_url)
        assert snap_res.status_code == 200
        assert snap_res.headers["content-type"] == "image/jpeg"
        assert snap_res.content.startswith(b"\xff\xd8")  # JPEG SOI marker

        # Missing valid snapshot filename -> 404 SNAPSHOT_NOT_FOUND
        missing = client.get("/api/v1/ai/snapshots/missing_file_123.jpg")
        assert missing.status_code == 404
        assert missing.json()["detail"]["code"] == "SNAPSHOT_NOT_FOUND"

        # 14. Path traversal & arbitrary path attempts -> rejected (400 INVALID_SNAPSHOT_PATH)
        traversal_attempts = [
            "/api/v1/ai/snapshots/..%2Fsecret.jpg",
            "/api/v1/ai/snapshots/..%5Csecret.jpg",
            "/api/v1/ai/snapshots/..%2f..%2fsecret.jpg",
            "/api/v1/ai/snapshots/subdir/file.jpg",
            "/api/v1/ai/snapshots/C:%5CWindows%5Cwin.ini",
        ]
        for bad_url in traversal_attempts:
            bad_res = client.get(bad_url)
            assert bad_res.status_code in (400, 404), f"Unexpected {bad_res.status_code} for {bad_url}"
            if bad_res.status_code == 400:
                assert bad_res.json()["detail"]["code"] == "INVALID_SNAPSHOT_PATH"


# ---------------------------------------------------------------------------
# WebSocket 15-22 & 25: Realtime broadcasts, payload equality, multi-client,
# failing client resilience, and worker-thread -> async bridge
# ---------------------------------------------------------------------------
def test_15_to_21_and_25_websocket_broadcast_from_worker_thread_and_rest_equality(tmp_path: Path):
    manager = _make_synthetic_manager(tmp_path)
    ws_manager = AIWebSocketManager()
    app = create_app(
        runtime_manager=manager,
        ws_manager=ws_manager,
        snapshot_dir=tmp_path / "snapshots",
    )

    with TestClient(app) as client:
        with (
            client.websocket_connect("/ws/ai") as ws_all,
            client.websocket_connect("/ws/ai?cameraId=CAM-01") as ws_cam1,
            client.websocket_connect("/ws/ai?cameraId=CAM-OTHER") as ws_other,
        ):
            assert ws_manager.active_count == 3

            # Run CameraPipeline synchronously on a separate worker thread
            # to prove thread-safe RuntimeEventSink -> asyncio WebSocket bridging!
            worker_errors: List[Exception] = []

            def worker():
                try:
                    _register_and_run_scripted_camera(manager, camera_id="CAM-01")
                except Exception as exc:
                    worker_errors.append(exc)

            t = threading.Thread(target=worker)
            t.start()
            t.join(timeout=5.0)
            assert not worker_errors
            ws_manager.flush_sync(timeout=2.0)

            # Collect all 10 messages emitted during the 4-frame run:
            # status(STARTING), status(ONLINE),
            # frame 0: detection, count
            # frame 1: detection
            # frame 2: detection, count(entry=1), ai.event(snake)
            # frame 3: detection
            # close: status(OFFLINE)
            received_all = [ws_all.receive_json() for _ in range(10)]
            received_cam1 = [ws_cam1.receive_json() for _ in range(10)]

            assert received_all == received_cam1
            types_seen = {m["type"] for m in received_all}
            assert types_seen == {
                "detection.updated",
                "count.updated",
                "ai.event",
                "camera.status",
            }
            for msg in received_all:
                assert msg["cameraId"] == "CAM-01"
                assert set(msg.keys()) == {"type", "cameraId", "data"}

            # Verify canonical payload equality with REST responses
            ws_latest_det = [m["data"] for m in received_all if m["type"] == "detection.updated"][-1]
            ws_latest_cnt = [m["data"] for m in received_all if m["type"] == "count.updated"][-1]
            ws_latest_evt = [m["data"] for m in received_all if m["type"] == "ai.event"][-1]
            ws_latest_sts = [m["data"] for m in received_all if m["type"] == "camera.status"][-1]

            rest_det = client.get("/api/v1/ai/cameras/CAM-01/detections/latest").json()
            rest_cnt = client.get("/api/v1/ai/cameras/CAM-01/counts/latest").json()
            rest_evt = client.get("/api/v1/ai/events").json()[0]
            rest_sts = client.get("/api/v1/ai/cameras/CAM-01/status").json()

            assert ws_latest_det == rest_det
            assert ws_latest_cnt == rest_cnt
            assert ws_latest_evt == rest_evt
            assert ws_latest_sts == rest_sts

            # Validate against canonical Pydantic models directly
            DetectionResult(**ws_latest_det)
            CountUpdate(**ws_latest_cnt)
            AIEvent(**ws_latest_evt)
            CameraRuntimeStatus(**ws_latest_sts)

        # After exiting context, clients are disconnected cleanly
        assert ws_manager.active_count == 0


def test_22_failing_websocket_client_does_not_break_runtime_or_healthy_clients(tmp_path: Path):
    manager = _make_synthetic_manager(tmp_path)
    ws_manager = AIWebSocketManager()
    app = create_app(
        runtime_manager=manager,
        ws_manager=ws_manager,
        snapshot_dir=tmp_path / "snapshots",
    )

    class FailingWebSocket:
        async def send_json(self, _data):
            raise RuntimeError("Simulated broken client socket")

    with TestClient(app) as client:
        with client.websocket_connect("/ws/ai") as healthy_ws:
            # Inject a failing client into ws_manager
            with ws_manager._lock:
                ws_manager._clients[FailingWebSocket()] = None  # type: ignore[index]
            assert ws_manager.active_count == 2

            _register_and_run_scripted_camera(manager, camera_id="CAM-01")
            ws_manager.flush_sync(timeout=2.0)

            first_msg = healthy_ws.receive_json()
            assert first_msg["cameraId"] == "CAM-01"
            # Failing client was automatically evicted without interrupting pipeline or healthy_ws
            assert ws_manager.active_count == 1


# ---------------------------------------------------------------------------
# Architecture & OpenAPI 23-24: Dependency direction & OpenAPI schema checks
# ---------------------------------------------------------------------------
def test_23_runtime_modules_do_not_import_fastapi_or_websocket():
    runtime_dir = Path(__file__).resolve().parent.parent / "app" / "runtime"
    forbidden_prefixes = ("fastapi", "starlette", "app.api", "app.websocket")

    for py_file in runtime_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden_prefixes), (
                        f"{py_file.name} imports forbidden module {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(forbidden_prefixes), (
                    f"{py_file.name} imports from forbidden module {node.module}"
                )


def test_24_openapi_and_docs_expose_canonical_v1_schemas(tmp_path: Path):
    manager = _make_synthetic_manager(tmp_path)
    app = create_app(runtime_manager=manager, snapshot_dir=tmp_path / "snapshots")
    with TestClient(app) as client:
        docs_res = client.get("/docs")
        assert docs_res.status_code == 200

        openapi_res = client.get("/openapi.json")
        assert openapi_res.status_code == 200
        spec = openapi_res.json()

        paths = spec["paths"]
        assert "/health" in paths
        assert "/api/v1/ai/cameras" in paths
        assert "/api/v1/ai/cameras/{cameraId}/status" in paths
        assert "/api/v1/ai/cameras/{cameraId}/detections/latest" in paths
        assert "/api/v1/ai/cameras/{cameraId}/counts/latest" in paths
        assert "/api/v1/ai/events" in paths
        assert "/api/v1/ai/events/{eventId}" in paths
        assert "/api/v1/ai/snapshots/{filename}" in paths

        schemas = spec["components"]["schemas"]
        for required_schema in (
            "DetectionResult",
            "Detection",
            "BoundingBox",
            "FrameInfo",
            "CountUpdate",
            "AIEvent",
            "CameraRuntimeStatus",
            "ErrorResponse",
        ):
            assert required_schema in schemas, f"Missing {required_schema} in OpenAPI schemas"
