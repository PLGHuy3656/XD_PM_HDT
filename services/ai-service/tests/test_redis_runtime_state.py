"""CP8.4 & CP8.4 Correction Redis Runtime State & Fast Cache tests for AI Service.

Covers:
- Category D: `ai:latest:{cameraId}` bounded latest count & detection summary cache
  * Populates Redis after durable PostgreSQL insert; bounded summary without per-frame history
  * Redis MISS falls back to PostgreSQL `ai_count_updates` and repopulates Redis
  * Malformed JSON fallback & Mocked Redis failure (`FailingRedisClient`) durability
  * Atomic out-of-order rejection (`countVersionTsUs` / `detectionVersionTsUs`)
  * Non-overwriting subfield merge & concurrent multi-threaded count + detection writers
- Category E: `ai:runtime:{cameraId}` live camera runtime status
  * `CameraRuntimeStatus` stored in Redis with TTL
  * Redis flush clears runtime status and NEVER rebuilds camera health from PostgreSQL
  * New runtime status or frame observation reconstructs `ai:runtime:{cameraId}`
  * Malformed JSON & mocked Redis failure handling
- Category F: Coexistence with Notification Service's `swiftlet:idempotency:{eventId}` Redis keys
- Category G: Real Redis container stop/start (`docker stop/start swiftletcare-redis`) verifying
  live PostgreSQL fallback during real Redis outage and automatic reconnection after restart.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import random
import subprocess
import time
from typing import Dict, List

from fastapi.testclient import TestClient
import numpy as np
import pytest
import redis

from app.config import RuntimeCameraConfig, settings
from app.database import get_connection
from app.main import create_app
from app.redis_client import ai_latest_key, ai_runtime_key, get_redis_client
from app.repositories import PostgreSQLCountUpdateRepository
from app.runtime.manager import AIRuntimeManager
from app.runtime.state_store import InMemoryAIRuntimeStateStore
from app.schemas.canonical import (
    BoundingBox,
    CameraRuntimeStatus,
    CountUpdate,
    Detection,
    DetectionResult,
    FrameInfo,
)
from swiftletcare_ai.detector import CallableDetector
from swiftletcare_ai.schemas import Detection as TV2Detection
from swiftletcare_ai.snapshot import SnapshotStore
from swiftletcare_ai.video_source import ListFrameSource
from tests.conftest import POSTGRES_AVAILABLE, REDIS_AVAILABLE

pytestmark = pytest.mark.skipif(
    not (REDIS_AVAILABLE and POSTGRES_AVAILABLE),
    reason="Redis (6379) and/or PostgreSQL (5432) not reachable on localhost",
)


class FailingRedisClient:
    """Deterministic mocked Redis client stub that raises redis.ConnectionError on every operation."""

    def get(self, *_args, **_kwargs):
        raise redis.ConnectionError("Mocked Redis outage on GET")

    def set(self, *_args, **_kwargs):
        raise redis.ConnectionError("Mocked Redis outage on SET")

    def eval(self, *_args, **_kwargs):
        raise redis.ConnectionError("Mocked Redis outage on EVAL")

    def delete(self, *_args, **_kwargs):
        raise redis.ConnectionError("Mocked Redis outage on DEL")

    def keys(self, *_args, **_kwargs):
        raise redis.ConnectionError("Mocked Redis outage on KEYS")

    def exists(self, *_args, **_kwargs):
        raise redis.ConnectionError("Mocked Redis outage on EXISTS")


def _ensure_redis_container_running() -> None:
    """Ensures `swiftletcare-redis` Docker container is running and responsive."""
    r = get_redis_client()
    try:
        if r.ping():
            return
    except Exception:
        pass
    subprocess.run(
        ["docker", "start", "swiftletcare-redis"],
        check=True,
        capture_output=True,
        text=True,
    )
    deadline = time.time() + 15.0
    while time.time() < deadline:
        try:
            if r.ping():
                return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("swiftletcare-redis failed to become ready after docker start")


# ==============================================================================
# CATEGORY D — AI LATEST SUMMARY (`ai:latest:{cameraId}`)
# ==============================================================================


def test_d1_ai_latest_stores_bounded_count_and_detection_summary_without_frame_history(
    tmp_path: Path,
):
    r_client = get_redis_client()
    snap_dir = tmp_path / "snapshots"
    manager = AIRuntimeManager(
        pipeline_cfg={
            "tracker": {"type": "centroid", "centroid_max_distance": 0.4, "centroid_max_missed": 2},
            "counting": {"inside_side": "positive", "report_interval_s": 60.0, "min_track_hits": 2},
            "predator": {"classes": ["rat", "snake"], "min_consecutive_frames": 2, "cooldown_s": 30.0},
            "snapshot": {"dir": str(snap_dir), "public_base_url": ""},
        },
        detector=CallableDetector(lambda _img: []),
        snapshot_store=SnapshotStore(directory=str(snap_dir), public_base_url=""),
    )

    frames = [np.zeros((200, 300, 3), dtype=np.uint8) for _ in range(5)]
    scripted: Dict[int, List[TV2Detection]] = {
        0: [TV2Detection("swiftlet", 0.91, [90, 30, 110, 50])],
        1: [TV2Detection("swiftlet", 0.92, [90, 60, 110, 80])],
        2: [TV2Detection("swiftlet", 0.95, [90, 130, 110, 150])],
        3: [TV2Detection("swiftlet", 0.94, [90, 150, 110, 170])],
        4: [TV2Detection("swiftlet", 0.90, [92, 155, 112, 175])],
    }
    idx = {"i": 0}

    def detect_fn(_img):
        f = idx["i"]
        idx["i"] += 1
        return scripted.get(f, [])

    cam_cfg = RuntimeCameraConfig(
        camera_id="CAM-REDIS-01",
        farm_id="FARM-BA-01",
        zone_id="ZONE-A",
        source=ListFrameSource("CAM-REDIS-01", frames, fps=15.0, t0=1_761_500_000.0),
        line=((0.05, 0.50), (0.95, 0.50)),
        inside_side="positive",
    )
    manager.register_camera(cam_cfg, detector=CallableDetector(detect_fn))
    manager.run_camera("CAM-REDIS-01")

    key = ai_latest_key("CAM-REDIS-01")
    assert key == "ai:latest:CAM-REDIS-01"
    assert r_client.exists(key) == 1
    assert 0 < r_client.ttl(key) <= settings.ai_latest_ttl_seconds

    assert r_client.keys("ai:latest:CAM-REDIS-01*") == [key]

    doc = json.loads(r_client.get(key))
    assert doc["cameraId"] == "CAM-REDIS-01"
    assert doc["farmId"] == "FARM-BA-01"
    assert doc["zoneId"] == "ZONE-A"
    assert doc["latestCount"] is not None
    assert doc["latestCount"]["entryCount"] == 1
    assert doc["latestCount"]["exitCount"] == 0
    assert doc["latestCount"]["netChange"] == 1
    assert doc["latestDetectionSummary"] == {
        "frameId": 4,
        "capturedAt": doc["lastFrameAt"],
        "detectionCount": 1,
        "frame": {"width": 300, "height": 200},
    }
    assert "detections" not in doc
    assert "detections" not in doc["latestDetectionSummary"]


def test_d2_deleting_ai_latest_falls_back_to_postgresql_and_repopulates_redis(tmp_path: Path):
    r_client = get_redis_client()
    count_repo = PostgreSQLCountUpdateRepository()
    store = InMemoryAIRuntimeStateStore(count_repository=count_repo, redis_client=r_client)

    update = CountUpdate(
        cameraId="CAM-FALLBACK-01",
        farmId="FARM-BA-01",
        zoneId="ZONE-B",
        frameId=12,
        recordedAt="2026-11-04T11:20:00.000Z",
        windowStartedAt="2026-11-04T11:00:00.000Z",
        entryCount=9,
        exitCount=4,
        netChange=5,
        deltaEntry=2,
        deltaExit=0,
    )
    assert store.record_count(update) is True

    key = ai_latest_key("CAM-FALLBACK-01")
    assert r_client.exists(key) == 1

    r_client.delete(key)
    assert r_client.exists(key) == 0

    manager = AIRuntimeManager(state_store=store)
    app = create_app(runtime_manager=manager, snapshot_dir=tmp_path / "snapshots")
    with TestClient(app) as client:
        res = client.get("/api/v1/ai/cameras/CAM-FALLBACK-01/counts/latest")
        assert res.status_code == 200
        body = res.json()
        assert body["cameraId"] == "CAM-FALLBACK-01"
        assert body["entryCount"] == 9
        assert body["exitCount"] == 4
        assert body["netChange"] == 5

    assert r_client.exists(key) == 1
    repopulated = json.loads(r_client.get(key))
    assert repopulated["latestCount"]["netChange"] == 5


def test_d3_malformed_json_in_ai_latest_and_mocked_redis_failure_preserve_postgresql_count_durability():
    r_client = get_redis_client()
    count_repo = PostgreSQLCountUpdateRepository()
    store = InMemoryAIRuntimeStateStore(count_repository=count_repo, redis_client=r_client)

    update = CountUpdate(
        cameraId="CAM-CORRUPT-01",
        farmId="FARM-BA-01",
        zoneId="ZONE-A",
        frameId=20,
        recordedAt="2026-11-04T11:25:00.000Z",
        windowStartedAt="2026-11-04T11:00:00.000Z",
        entryCount=14,
        exitCount=6,
        netChange=8,
        deltaEntry=1,
        deltaExit=0,
    )
    assert store.record_count(update) is True

    key = ai_latest_key("CAM-CORRUPT-01")
    r_client.set(key, "{invalid-json", ex=3600)

    recovered = store.get_latest_count("CAM-CORRUPT-01")
    assert recovered is not None
    assert recovered.netChange == 8
    assert json.loads(r_client.get(key))["latestCount"]["netChange"] == 8

    # Mocked Redis outage during record_count still persists to PostgreSQL and allows fallback reads
    outage_store = InMemoryAIRuntimeStateStore(
        count_repository=count_repo,
        redis_client=FailingRedisClient(),
    )
    update2 = CountUpdate(
        cameraId="CAM-OUTAGE-01",
        farmId="FARM-BA-01",
        zoneId="ZONE-A",
        frameId=21,
        recordedAt="2026-11-04T11:26:00.000Z",
        windowStartedAt="2026-11-04T11:00:00.000Z",
        entryCount=15,
        exitCount=6,
        netChange=9,
        deltaEntry=1,
        deltaExit=0,
    )
    assert outage_store.record_count(update2) is True
    recovered_outage = outage_store.get_latest_count("CAM-OUTAGE-01")
    assert recovered_outage is not None
    assert recovered_outage.netChange == 9


def test_d4_out_of_order_count_and_detection_updates_do_not_regress_ai_latest():
    r_client = get_redis_client()
    count_repo = PostgreSQLCountUpdateRepository()
    store = InMemoryAIRuntimeStateStore(count_repository=count_repo, redis_client=r_client)

    # 1. Newer CountUpdate arrives first (frameId=20, 12:10:00Z, netChange=12)
    newer_count = CountUpdate(
        cameraId="CAM-OOO-01",
        farmId="FARM-BA-01",
        zoneId="ZONE-A",
        frameId=20,
        recordedAt="2026-11-04T12:10:00.000Z",
        windowStartedAt="2026-11-04T12:00:00.000Z",
        entryCount=18,
        exitCount=6,
        netChange=12,
        deltaEntry=2,
        deltaExit=0,
    )
    # 2. Older CountUpdate arrives second (frameId=10, 12:05:00Z, netChange=4)
    older_count = CountUpdate(
        cameraId="CAM-OOO-01",
        farmId="FARM-BA-01",
        zoneId="ZONE-A",
        frameId=10,
        recordedAt="2026-11-04T12:05:00.000Z",
        windowStartedAt="2026-11-04T12:00:00.000Z",
        entryCount=8,
        exitCount=4,
        netChange=4,
        deltaEntry=1,
        deltaExit=0,
    )
    assert store.record_count(newer_count) is True
    assert store.record_count(older_count) is True

    # 3. Newer DetectionResult arrives first (frameId=25, 12:12:00Z, 3 detections)
    newer_det = DetectionResult(
        cameraId="CAM-OOO-01",
        farmId="FARM-BA-01",
        zoneId="ZONE-A",
        frameId=25,
        capturedAt="2026-11-04T12:12:00.000Z",
        frame=FrameInfo(width=1280, height=720),
        detections=[
            Detection(**{"class": "swiftlet", "confidence": 0.91, "bbox": BoundingBox(x1=10, y1=10, x2=30, y2=30)}),
            Detection(**{"class": "swiftlet", "confidence": 0.92, "bbox": BoundingBox(x1=40, y1=40, x2=60, y2=60)}),
            Detection(**{"class": "swiftlet", "confidence": 0.93, "bbox": BoundingBox(x1=70, y1=70, x2=90, y2=90)}),
        ],
    )
    # 4. Older DetectionResult arrives second (frameId=15, 12:08:00Z, 1 detection)
    older_det = DetectionResult(
        cameraId="CAM-OOO-01",
        farmId="FARM-BA-01",
        zoneId="ZONE-A",
        frameId=15,
        capturedAt="2026-11-04T12:08:00.000Z",
        frame=FrameInfo(width=1280, height=720),
        detections=[
            Detection(**{"class": "swiftlet", "confidence": 0.85, "bbox": BoundingBox(x1=10, y1=10, x2=30, y2=30)}),
        ],
    )
    store.record_detection(newer_det)
    store.record_detection(older_det)

    # Verify Redis `ai:latest:CAM-OOO-01` retained both newer count (frameId=20, netChange=12)
    # and newer detection summary (frameId=25, detectionCount=3)
    summary = store.get_latest_summary("CAM-OOO-01")
    assert summary is not None
    assert summary["latestCount"]["frameId"] == 20
    assert summary["latestCount"]["netChange"] == 12
    assert summary["latestDetectionSummary"]["frameId"] == 25
    assert summary["latestDetectionSummary"]["detectionCount"] == 3
    assert summary["lastFrameAt"] == "2026-11-04T12:12:00.000Z"
    assert summary["updatedAt"] == "2026-11-04T12:12:00.000Z"


def test_d5_count_and_detection_updates_never_overwrite_each_others_newer_fields_under_concurrency():
    r_client = get_redis_client()
    count_repo = PostgreSQLCountUpdateRepository()
    store = InMemoryAIRuntimeStateStore(count_repository=count_repo, redis_client=r_client)

    # Part 1: Deterministic interleaved check where detection (T=12:20:00Z) is newer than count (T=12:19:55Z)
    store.record_detection(
        DetectionResult(
            cameraId="CAM-INTERLEAVE-01",
            farmId="FARM-BA-01",
            zoneId="ZONE-A",
            frameId=50,
            capturedAt="2026-11-04T12:20:00.000Z",
            frame=FrameInfo(width=1920, height=1080),
            detections=[
                Detection(**{"class": "swiftlet", "confidence": 0.95, "bbox": BoundingBox(x1=10, y1=10, x2=40, y2=40)}),
                Detection(**{"class": "swiftlet", "confidence": 0.90, "bbox": BoundingBox(x1=50, y1=50, x2=80, y2=80)}),
            ],
        )
    )
    store.record_count(
        CountUpdate(
            cameraId="CAM-INTERLEAVE-01",
            farmId="FARM-BA-01",
            zoneId="ZONE-A",
            frameId=48,
            recordedAt="2026-11-04T12:19:55.000Z",
            windowStartedAt="2026-11-04T12:00:00.000Z",
            entryCount=22,
            exitCount=10,
            netChange=12,
            deltaEntry=3,
            deltaExit=1,
        )
    )

    interleaved_doc = store.get_latest_summary("CAM-INTERLEAVE-01")
    assert interleaved_doc is not None
    assert interleaved_doc["latestCount"]["frameId"] == 48
    assert interleaved_doc["latestCount"]["netChange"] == 12
    assert interleaved_doc["latestDetectionSummary"]["frameId"] == 50
    assert interleaved_doc["latestDetectionSummary"]["detectionCount"] == 2
    # Newer detection timestamp (12:20:00.000Z) must NOT be regressed by older count timestamp (12:19:55.000Z)
    assert interleaved_doc["lastFrameAt"] == "2026-11-04T12:20:00.000Z"
    assert interleaved_doc["updatedAt"] == "2026-11-04T12:20:00.000Z"

    # Part 2: Concurrent writers (8 count threads + 8 detection threads racing on `ai:latest:CAM-RACE-01`)
    count_indices = list(range(1, 9))
    det_indices = list(range(1, 9))
    random.Random(99).shuffle(count_indices)
    random.Random(101).shuffle(det_indices)

    def write_count(idx: int) -> None:
        iso_ts = f"2026-11-04T13:00:{idx:02d}.000Z"
        store.record_count(
            CountUpdate(
                cameraId="CAM-RACE-01",
                farmId="FARM-BA-01",
                zoneId="ZONE-A",
                frameId=idx * 10,
                recordedAt=iso_ts,
                windowStartedAt="2026-11-04T13:00:00.000Z",
                entryCount=idx * 3,
                exitCount=idx,
                netChange=idx * 2,
                deltaEntry=3,
                deltaExit=1,
            )
        )

    def write_detection(idx: int) -> None:
        iso_ts = f"2026-11-04T13:01:{idx:02d}.000Z"
        dets = [
            Detection(
                **{
                    "class": "swiftlet",
                    "confidence": 0.90,
                    "bbox": BoundingBox(x1=10.0, y1=10.0, x2=30.0, y2=30.0),
                }
            )
            for _ in range(idx)
        ]
        store.record_detection(
            DetectionResult(
                cameraId="CAM-RACE-01",
                farmId="FARM-BA-01",
                zoneId="ZONE-A",
                frameId=idx * 100,
                capturedAt=iso_ts,
                frame=FrameInfo(width=1280, height=720),
                detections=dets,
            )
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = []
        for c_idx, d_idx in zip(count_indices, det_indices):
            futures.append(pool.submit(write_count, c_idx))
            futures.append(pool.submit(write_detection, d_idx))
        for f in futures:
            f.result()

    race_doc = store.get_latest_summary("CAM-RACE-01")
    assert race_doc is not None
    # Highest count is idx=8 (frameId=80, netChange=16, recordedAt=13:00:08.000Z)
    assert race_doc["latestCount"]["frameId"] == 80
    assert race_doc["latestCount"]["netChange"] == 16
    assert race_doc["latestCount"]["recordedAt"] == "2026-11-04T13:00:08.000Z"
    # Highest detection is idx=8 (frameId=800, detectionCount=8, capturedAt=13:01:08.000Z)
    assert race_doc["latestDetectionSummary"]["frameId"] == 800
    assert race_doc["latestDetectionSummary"]["detectionCount"] == 8
    assert race_doc["latestDetectionSummary"]["capturedAt"] == "2026-11-04T13:01:08.000Z"
    assert race_doc["lastFrameAt"] == "2026-11-04T13:01:08.000Z"
    assert race_doc["updatedAt"] == "2026-11-04T13:01:08.000Z"


# ==============================================================================
# CATEGORY E — AI CAMERA RUNTIME STATUS (`ai:runtime:{cameraId}`)
# ==============================================================================


def test_e1_camera_runtime_status_stored_in_redis_and_never_rebuilt_from_postgresql_after_flush(
    tmp_path: Path,
):
    r_client = get_redis_client()
    count_repo = PostgreSQLCountUpdateRepository()
    store = InMemoryAIRuntimeStateStore(count_repository=count_repo, redis_client=r_client)
    manager = AIRuntimeManager(state_store=store)

    status_online = CameraRuntimeStatus(
        cameraId="CAM-RUNTIME-01",
        farmId="FARM-BA-01",
        zoneId="ZONE-A",
        status="ONLINE",
        sourceConnected=True,
        inferenceStatus="RUNNING",
        fps=14.8,
        width=1280,
        height=720,
        modelVersion="yolo26n-best",
        trackerType="bytetrack",
        processedFrames=42,
        lastFrameAt="2026-11-04T11:30:00.000Z",
        updatedAt="2026-11-04T11:30:00.000Z",
        errorCode=None,
        errorMessage=None,
    )
    store.record_status(status_online)
    store.record_count(
        CountUpdate(
            cameraId="CAM-RUNTIME-01",
            farmId="FARM-BA-01",
            zoneId="ZONE-A",
            frameId=42,
            recordedAt="2026-11-04T11:30:00.000Z",
            windowStartedAt="2026-11-04T11:00:00.000Z",
            entryCount=10,
            exitCount=3,
            netChange=7,
            deltaEntry=1,
            deltaExit=0,
        )
    )

    rt_key = ai_runtime_key("CAM-RUNTIME-01")
    assert rt_key == "ai:runtime:CAM-RUNTIME-01"
    assert r_client.exists(rt_key) == 1
    assert 0 < r_client.ttl(rt_key) <= settings.ai_runtime_ttl_seconds

    rt_doc = json.loads(r_client.get(rt_key))
    assert rt_doc["cameraId"] == "CAM-RUNTIME-01"
    assert rt_doc["status"] == "ONLINE"
    assert rt_doc["fps"] == 14.8
    assert rt_doc["processedFrames"] == 42
    assert rt_doc["lastFrameAt"] == "2026-11-04T11:30:00.000Z"
    assert "lastError" in rt_doc

    app = create_app(runtime_manager=manager, snapshot_dir=tmp_path / "snapshots")
    with TestClient(app) as client:
        res_before = client.get("/api/v1/ai/cameras/CAM-RUNTIME-01/status")
        assert res_before.status_code == 200
        assert res_before.json()["status"] == "ONLINE"

        r_client.delete(rt_key, ai_latest_key("CAM-RUNTIME-01"))

        assert store.get_camera_status("CAM-RUNTIME-01") is None
        assert store.list_camera_statuses() == []
        res_status_after_flush = client.get("/api/v1/ai/cameras/CAM-RUNTIME-01/status")
        assert res_status_after_flush.status_code == 404

        res_count_after_flush = client.get("/api/v1/ai/cameras/CAM-RUNTIME-01/counts/latest")
        assert res_count_after_flush.status_code == 200
        assert res_count_after_flush.json()["netChange"] == 7

        store.record_detection(
            DetectionResult(
                cameraId="CAM-RUNTIME-01",
                farmId="FARM-BA-01",
                zoneId="ZONE-A",
                frameId=43,
                capturedAt="2026-11-04T11:30:01.000Z",
                frame=FrameInfo(width=1280, height=720),
                detections=[
                    Detection(
                        **{
                            "class": "swiftlet",
                            "confidence": 0.93,
                            "bbox": BoundingBox(x1=100.0, y1=120.0, x2=140.0, y2=160.0),
                            "trackId": 1,
                        }
                    )
                ],
            )
        )
        assert r_client.exists(rt_key) == 1
        res_rebuilt = client.get("/api/v1/ai/cameras/CAM-RUNTIME-01/status")
        assert res_rebuilt.status_code == 200
        assert res_rebuilt.json()["status"] == "ONLINE"
        assert res_rebuilt.json()["lastFrameAt"] == "2026-11-04T11:30:01.000Z"


def test_e2_malformed_runtime_json_and_mocked_redis_failure_handled_safely():
    r_client = get_redis_client()
    store = InMemoryAIRuntimeStateStore(redis_client=r_client)

    rt_key = ai_runtime_key("CAM-BAD-RT")
    r_client.set(rt_key, "{corrupt-runtime-json", ex=300)

    assert store.get_camera_status("CAM-BAD-RT") is None
    assert r_client.exists(rt_key) == 0

    outage_store = InMemoryAIRuntimeStateStore(redis_client=FailingRedisClient())
    assert outage_store.get_camera_status("CAM-ANY") is None
    assert outage_store.list_camera_statuses() == []


# ==============================================================================
# CATEGORY F — REDIS KEY NAMESPACE ISOLATION WITH NOTIFICATION IDEMPOTENCY
# ==============================================================================


def test_f1_redis_key_namespaces_coexist_without_collision():
    r_client = get_redis_client()
    store = InMemoryAIRuntimeStateStore(redis_client=r_client)

    idem_key = "swiftlet:idempotency:evt-cp84-coexist-01"
    r_client.set(idem_key, "DONE", ex=86400)

    try:
        store.record_status(
            CameraRuntimeStatus(
                cameraId="CAM-NS-01",
                farmId="FARM-01",
                zoneId="ZONE-A",
                status="ONLINE",
                sourceConnected=True,
                inferenceStatus="RUNNING",
                fps=12.0,
                width=640,
                height=480,
                modelVersion="yolo26n-best",
                trackerType="centroid",
                processedFrames=10,
                lastFrameAt="2026-11-04T11:35:00.000Z",
                updatedAt="2026-11-04T11:35:00.000Z",
            )
        )
        assert r_client.get(idem_key) == "DONE"
        assert store.get_camera_status("CAM-NS-01") is not None

        store.clear_redis_state()
        assert r_client.get(idem_key) == "DONE"
    finally:
        r_client.delete(idem_key)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
                """
            )
            tables = [r[0] for r in cur.fetchall()]
    assert tables == ["ai_count_updates", "ai_events", "schema_migrations"]


# ==============================================================================
# CATEGORY G — REAL REDIS CONTAINER STOP/START & AUTO-RECONNECT
# ==============================================================================


def test_g1_real_redis_container_restart_preserves_postgresql_counts_and_auto_reconnects(
    tmp_path: Path,
):
    """Real Redis container restart test (`docker stop/start swiftletcare-redis`).

    Demonstrates:
    1. Stopping `swiftletcare-redis` causes real TCP connection failure on port 6379.
    2. While Redis container is stopped:
       - `store.record_count()` still commits durably to PostgreSQL `ai_db.ai_count_updates`.
       - `GET /api/v1/ai/cameras/{cameraId}/counts/latest` returns 200 OK via PostgreSQL fallback.
       - `GET /api/v1/ai/cameras/{cameraId}/status` returns 404 without crashing.
    3. Starting `swiftletcare-redis` back up allows the existing `InMemoryAIRuntimeStateStore`
       instance to automatically reconnect without service restart, repopulating `ai:latest:{cameraId}`
       and `ai:runtime:{cameraId}`.
    """
    _ensure_redis_container_running()
    count_repo = PostgreSQLCountUpdateRepository()
    store = InMemoryAIRuntimeStateStore(count_repository=count_repo)
    manager = AIRuntimeManager(state_store=store)
    app = create_app(runtime_manager=manager, snapshot_dir=tmp_path / "snapshots")

    try:
        subprocess.run(
            ["docker", "stop", "swiftletcare-redis"],
            check=True,
            capture_output=True,
            text=True,
        )

        # Write CountUpdate while real Redis container is stopped
        ok = store.record_count(
            CountUpdate(
                cameraId="CAM-REAL-RESTART",
                farmId="FARM-BA-01",
                zoneId="ZONE-A",
                frameId=77,
                recordedAt="2026-11-04T14:00:00.000Z",
                windowStartedAt="2026-11-04T13:45:00.000Z",
                entryCount=30,
                exitCount=12,
                netChange=18,
                deltaEntry=4,
                deltaExit=1,
            )
        )
        assert ok is True

        with TestClient(app) as client:
            res_count_down = client.get("/api/v1/ai/cameras/CAM-REAL-RESTART/counts/latest")
            assert res_count_down.status_code == 200
            assert res_count_down.json()["netChange"] == 18

            res_status_down = client.get("/api/v1/ai/cameras/CAM-REAL-RESTART/status")
            assert res_status_down.status_code == 404
    finally:
        _ensure_redis_container_running()

    r_client = get_redis_client()
    with TestClient(app) as client:
        # Querying latest count after Redis container restart repopulates `ai:latest:CAM-REAL-RESTART`
        res_count_up = client.get("/api/v1/ai/cameras/CAM-REAL-RESTART/counts/latest")
        assert res_count_up.status_code == 200
        assert res_count_up.json()["netChange"] == 18
        assert r_client.exists(ai_latest_key("CAM-REAL-RESTART")) == 1

        # Recording new runtime status after Redis restart repopulates `ai:runtime:CAM-REAL-RESTART`
        store.record_status(
            CameraRuntimeStatus(
                cameraId="CAM-REAL-RESTART",
                farmId="FARM-BA-01",
                zoneId="ZONE-A",
                status="ONLINE",
                sourceConnected=True,
                inferenceStatus="RUNNING",
                fps=15.0,
                width=1280,
                height=720,
                modelVersion="yolo26n-best",
                trackerType="bytetrack",
                processedFrames=78,
                lastFrameAt="2026-11-04T14:00:05.000Z",
                updatedAt="2026-11-04T14:00:05.000Z",
            )
        )
        assert r_client.exists(ai_runtime_key("CAM-REAL-RESTART")) == 1
        res_status_up = client.get("/api/v1/ai/cameras/CAM-REAL-RESTART/status")
        assert res_status_up.status_code == 200
        assert res_status_up.json()["status"] == "ONLINE"
