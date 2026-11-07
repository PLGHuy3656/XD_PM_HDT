"""Automated End-to-End Local Demo for SwiftletCare AI Service V1 (CP5.3 Task 17).

Proves both:
1. Synthetic E2E Demo:
   Synthetic Video Frames -> CameraPipeline (worker thread) -> Canonical Runtime
   -> FastAPI REST V1 (/health, /cameras, /status, /detections/latest, /counts/latest, /events, /snapshots)
   + WebSocket V1 (/ws/ai realtime broadcast)
2. Real-Model E2E Demo:
   TV2 `models/best.pt` (YoloDetector + ByteTrackTracker) -> CameraPipeline (worker thread)
   -> FastAPI REST V1 + WebSocket V1 (/ws/ai)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List

import httpx
import numpy as np
import uvicorn
import websockets

SERVICE_DIR = Path(__file__).resolve().parent.parent
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from app.config import AI_PIPELINE_DIR, RuntimeCameraConfig, settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repositories import InMemoryAIEventRepository, InMemoryCountUpdateRepository  # noqa: E402
import app.runtime.publisher_sink as publisher_sink_mod  # noqa: E402
from app.runtime.manager import AIRuntimeManager  # noqa: E402
from app.runtime.state_store import InMemoryAIRuntimeStateStore  # noqa: E402
from app.websocket.manager import AIWebSocketManager  # noqa: E402
from swiftletcare_ai.detector import CallableDetector, YoloDetector  # noqa: E402
from swiftletcare_ai.schemas import Detection as TV2Detection  # noqa: E402
from swiftletcare_ai.snapshot import SnapshotStore  # noqa: E402
from swiftletcare_ai.video_source import ListFrameSource  # noqa: E402

settings.ai_redis_enabled = False
publisher_sink_mod.default_ai_event_repository = InMemoryAIEventRepository()


async def run_synthetic_e2e_demo(port: int = 18003) -> None:
    print("=" * 72)
    print("[DEMO 1/2] SYNTHETIC END-TO-END DEMO (Worker Thread -> REST + WebSocket)")
    print("=" * 72)

    with tempfile.TemporaryDirectory() as tmp_dir:
        snap_dir = Path(tmp_dir) / "snapshots"
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

        manager = AIRuntimeManager(
            pipeline_cfg=pipeline_cfg,
            state_store=InMemoryAIRuntimeStateStore(
                redis_enabled=False,
                count_repository=InMemoryCountUpdateRepository(),
                event_repository=InMemoryAIEventRepository(),
            ),
            detector=CallableDetector(lambda _img: []),
            snapshot_store=snap_store,
        )
        ws_manager = AIWebSocketManager()
        app = create_app(
            runtime_manager=manager,
            ws_manager=ws_manager,
            snapshot_dir=snap_dir,
        )

        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        server = uvicorn.Server(config)
        server_task = asyncio.create_task(server.serve())
        while not server.started:
            await asyncio.sleep(0.05)
        print(f"[SYNTHETIC] 1. AI Service started on http://127.0.0.1:{port}")

        ws_events: List[Dict[str, Any]] = []
        ws_conn = await websockets.connect(f"ws://127.0.0.1:{port}/ws/ai")

        async def ws_reader() -> None:
            try:
                async for raw_msg in ws_conn:
                    ws_events.append(json.loads(raw_msg))
            except Exception:
                pass

        ws_task = asyncio.create_task(ws_reader())
        print(f"[SYNTHETIC] 2. WebSocket observer connected to ws://127.0.0.1:{port}/ws/ai")

        # Prepare synthetic 4-frame sequence:
        # Bird 1 enters, Bird 2 exits, Snake triggers predator alert + snapshot
        frames = [np.zeros((240, 320, 3), dtype=np.uint8) for _ in range(4)]
        scripted: Dict[int, List[TV2Detection]] = {
            0: [
                TV2Detection("swiftlet", 0.92, [60, 40, 80, 60]),
                TV2Detection("swiftlet", 0.89, [200, 170, 220, 190]),
            ],
            1: [
                TV2Detection("swiftlet", 0.93, [60, 90, 80, 110]),
                TV2Detection("swiftlet", 0.90, [200, 140, 220, 160]),
                TV2Detection("snake", 0.88, [20, 180, 70, 220]),
            ],
            2: [
                TV2Detection("swiftlet", 0.96, [60, 160, 80, 180]),  # ENTRY
                TV2Detection("swiftlet", 0.91, [200, 60, 220, 80]),   # EXIT
                TV2Detection("snake", 0.94, [24, 182, 74, 222]),      # PREDATOR_DETECTED
            ],
            3: [
                TV2Detection("swiftlet", 0.95, [60, 175, 80, 195]),
            ],
        }
        idx = {"i": 0}

        def detect_fn(_img):
            f = idx["i"]
            idx["i"] += 1
            return scripted.get(f, [])

        def run_pipeline_worker() -> None:
            cam_cfg = RuntimeCameraConfig(
                camera_id="CAM-01",
                farm_id="FARM-01",
                zone_id="ZONE-A",
                source=ListFrameSource("CAM-01", frames, fps=10.0, t0=1_761_510_000.0),
                line=((0.05, 0.50), (0.95, 0.50)),
                inside_side="positive",
            )
            manager.register_camera(cam_cfg, detector=CallableDetector(detect_fn))
            manager.run_camera("CAM-01")

        worker = threading.Thread(target=run_pipeline_worker, daemon=True)
        worker.start()
        worker.join(timeout=5.0)
        ws_manager.flush_sync(timeout=2.0)
        await asyncio.sleep(0.2)

        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
            health = (await client.get("/health")).json()
            assert health == {"service": "ai-service", "status": "ok"}
            print(f"[SYNTHETIC] 3. GET /health -> {health}")

            status = (await client.get("/api/v1/ai/cameras/CAM-01/status")).json()
            assert status["status"] == "OFFLINE" and status["processedFrames"] == 4
            print(
                f"[SYNTHETIC] 4. GET /api/v1/ai/cameras/CAM-01/status -> "
                f"status={status['status']}, processedFrames={status['processedFrames']}, "
                f"size={status['width']}x{status['height']}"
            )

            det = (await client.get("/api/v1/ai/cameras/CAM-01/detections/latest")).json()
            assert det["frameId"] == 3 and len(det["detections"]) == 1
            print(
                f"[SYNTHETIC] 5. GET /api/v1/ai/cameras/CAM-01/detections/latest -> "
                f"frameId={det['frameId']}, detections={len(det['detections'])}, "
                f"capturedAt={det['capturedAt']}"
            )

            cnt = (await client.get("/api/v1/ai/cameras/CAM-01/counts/latest")).json()
            assert cnt["entryCount"] == 1 and cnt["exitCount"] == 1 and cnt["netChange"] == 0
            print(
                f"[SYNTHETIC] 6. GET /api/v1/ai/cameras/CAM-01/counts/latest -> "
                f"entryCount={cnt['entryCount']}, exitCount={cnt['exitCount']}, "
                f"netChange={cnt['netChange']}"
            )

            events = (await client.get("/api/v1/ai/events")).json()
            assert len(events) == 1 and events[0]["eventType"] == "PREDATOR_DETECTED"
            ev = events[0]
            print(
                f"[SYNTHETIC] 7. GET /api/v1/ai/events -> "
                f"eventId={ev['eventId']}, class={ev['class']}, "
                f"confidence={ev['confidence']}, snapshot={ev['snapshot']}"
            )

            snap_resp = await client.get(ev["snapshot"])
            assert snap_resp.status_code == 200 and snap_resp.headers["content-type"] == "image/jpeg"
            print(
                f"[SYNTHETIC] 8. GET {ev['snapshot']} -> "
                f"HTTP {snap_resp.status_code} ({len(snap_resp.content)} bytes JPEG)"
            )

        ws_types = sorted({e["type"] for e in ws_events})
        assert ws_types == ["ai.event", "camera.status", "count.updated", "detection.updated"]
        print(
            f"[SYNTHETIC] 9. WebSocket /ws/ai received {len(ws_events)} messages; "
            f"event types={ws_types}"
        )

        await ws_conn.close()
        ws_task.cancel()
        server.should_exit = True
        await server_task
        print("[SYNTHETIC] PASS\n")


async def run_real_model_e2e_demo(port: int = 18004) -> None:
    print("=" * 72)
    print("[DEMO 2/2] REAL-MODEL END-TO-END DEMO (TV2 models/best.pt + ByteTrack)")
    print("=" * 72)

    weights_path = AI_PIPELINE_DIR / "models" / "best.pt"
    if not weights_path.exists():
        raise FileNotFoundError(f"Missing real model weights at {weights_path}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        snap_dir = Path(tmp_dir) / "snapshots"
        detector = YoloDetector(
            model_path=str(weights_path),
            imgsz=640,
            device="cpu",
            min_conf=0.15,
            iou=0.5,
        )
        manager = AIRuntimeManager(
            pipeline_cfg={
                "model": {"path": str(weights_path), "imgsz": 640},
                "tracker": {"type": "bytetrack"},
                "snapshot": {"dir": str(snap_dir), "public_base_url": ""},
            },
            state_store=InMemoryAIRuntimeStateStore(
                redis_enabled=False,
                count_repository=InMemoryCountUpdateRepository(),
                event_repository=InMemoryAIEventRepository(),
            ),
            detector=detector,
            snapshot_store=SnapshotStore(directory=str(snap_dir), public_base_url=""),
        )
        ws_manager = AIWebSocketManager()
        app = create_app(
            runtime_manager=manager,
            ws_manager=ws_manager,
            snapshot_dir=snap_dir,
        )

        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        server = uvicorn.Server(config)
        server_task = asyncio.create_task(server.serve())
        while not server.started:
            await asyncio.sleep(0.05)
        print(f"[REAL-MODEL] 1. AI Service started on http://127.0.0.1:{port} with models/best.pt")

        ws_events: List[Dict[str, Any]] = []
        ws_conn = await websockets.connect(f"ws://127.0.0.1:{port}/ws/ai?cameraId=CAM-REAL-01")

        async def ws_reader() -> None:
            try:
                async for raw_msg in ws_conn:
                    ws_events.append(json.loads(raw_msg))
            except Exception:
                pass

        ws_task = asyncio.create_task(ws_reader())

        import cv2

        pred_dir = AI_PIPELINE_DIR / "data" / "samples" / "predators"
        pred_files = (
            sorted([p for p in pred_dir.iterdir() if p.suffix.lower() in (".jpg", ".png", ".webp")])
            if pred_dir.exists()
            else []
        )
        frames = []
        for p in pred_files[:3]:
            img = cv2.imread(str(p))
            if img is not None:
                frames.append(img)
        if not frames:
            vid_path = AI_PIPELINE_DIR / "data" / "samples" / "38s.mp4"
            if vid_path.exists():
                cap = cv2.VideoCapture(str(vid_path))
                for _ in range(3):
                    ret, fr = cap.read()
                    if ret and fr is not None:
                        frames.append(fr)
                cap.release()
        if not frames:
            frames = [np.zeros((720, 1280, 3), dtype=np.uint8) for _ in range(2)]

        expected_count = len(frames)
        last_h, last_w = frames[-1].shape[:2]

        def run_real_worker() -> None:
            cam_cfg = RuntimeCameraConfig(
                camera_id="CAM-REAL-01",
                farm_id="FARM-01",
                zone_id="ZONE-A",
                source=ListFrameSource("CAM-REAL-01", frames, fps=15.0, t0=1_761_520_000.0),
            )
            manager.register_camera(cam_cfg, detector=detector)
            manager.run_camera("CAM-REAL-01")

        worker = threading.Thread(target=run_real_worker, daemon=True)
        worker.start()
        worker.join(timeout=30.0)
        ws_manager.flush_sync(timeout=2.0)
        await asyncio.sleep(0.2)

        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
            status = (await client.get("/api/v1/ai/cameras/CAM-REAL-01/status")).json()
            assert status["processedFrames"] == expected_count and status["trackerType"] == "bytetrack"
            print(
                f"[REAL-MODEL] 2. GET /api/v1/ai/cameras/CAM-REAL-01/status -> "
                f"modelVersion={status['modelVersion']}, trackerType={status['trackerType']}, "
                f"processedFrames={status['processedFrames']}, frame={status['width']}x{status['height']}"
            )

            det = (await client.get("/api/v1/ai/cameras/CAM-REAL-01/detections/latest")).json()
            assert det["frame"] == {"width": last_w, "height": last_h}
            print(
                f"[REAL-MODEL] 3. GET /api/v1/ai/cameras/CAM-REAL-01/detections/latest -> "
                f"frameId={det['frameId']}, frame={det['frame']}"
            )

        ws_types = sorted({e["type"] for e in ws_events})
        assert "detection.updated" in ws_types and "count.updated" in ws_types and "camera.status" in ws_types
        print(
            f"[REAL-MODEL] 4. WebSocket /ws/ai?cameraId=CAM-REAL-01 received "
            f"{len(ws_events)} messages; types={ws_types}"
        )

        await ws_conn.close()
        ws_task.cancel()
        server.should_exit = True
        await server_task
        print("[REAL-MODEL] PASS\n")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run AI Service V1 E2E Demo")
    parser.add_argument(
        "--mode",
        choices=("synthetic", "real", "both"),
        default="both",
        help="Which E2E demo mode to execute",
    )
    args = parser.parse_args()

    if args.mode in ("synthetic", "both"):
        await run_synthetic_e2e_demo()
    if args.mode in ("real", "both"):
        await run_real_model_e2e_demo()
    print("ALL REQUESTED AI SERVICE V1 E2E DEMOS PASSED!")


if __name__ == "__main__":
    asyncio.run(main())
