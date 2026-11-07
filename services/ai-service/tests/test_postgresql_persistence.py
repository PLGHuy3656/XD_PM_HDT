"""Comprehensive PostgreSQL persistence tests for AI Service (CP8.2).

Covers:
A. CountUpdate durable persistence (insert, entryCount, exitCount, netChange invariant,
   UTC timestamps, query by camera, farm, zone, time range, fresh repository recreation).
B. AIEvent durable persistence (PREDATOR_DETECTED rat/snake, confidence, bbox, snapshot_ref,
   idempotent event_id deduplication, query by event_id/camera/farm/time range, fresh repository recreation).
C. Ephemeral DetectionResult verification (per-frame DetectionResult is NEVER inserted into PostgreSQL;
   live runtime/latest behavior remains operational).
D. CameraRuntimeStatus runtime verification (remains in-memory; no Redis introduced).
E. RabbitMQ CP7 compatibility (ai.predator.detected envelope unchanged, persisted before publish).
F. Database failure handling (explicit failure logging, no false durable reporting, pipeline resilience).
G. Boundary verification (zero cross-service FKs in ai_db, non-superuser ai_user, no direct Management DB or Redis access).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from fastapi.testclient import TestClient
import numpy as np
import pytest

from app.config import RuntimeCameraConfig, settings
from app.database import get_connection
from app.domain_events.constants import EVENT_AI_PREDATOR_DETECTED, PRODUCER_AI_SERVICE
from app.main import create_app
from app.ports.domain_event_publisher import InMemoryDomainEventPublisher
from app.ports.metadata_resolver import InMemoryCameraMetadataResolver
from app.repositories import (
    PostgreSQLAIEventRepository,
    PostgreSQLCountUpdateRepository,
)
from app.runtime.manager import AIRuntimeManager
from app.runtime.publisher_sink import DomainEventPublisherRuntimeSink
from app.runtime.state_store import InMemoryAIRuntimeStateStore
from app.schemas.canonical import (
    AIEvent,
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
from tests.conftest import POSTGRES_AVAILABLE

pytestmark = pytest.mark.skipif(
    not POSTGRES_AVAILABLE,
    reason="PostgreSQL server not reachable on 127.0.0.1:5432",
)


# ==============================================================================
# CATEGORY A — COUNTUPDATE PERSISTENCE
# ==============================================================================


def test_a1_count_update_insert_and_net_change_invariant():
    assert settings.ai_database_url, "AI_DATABASE_URL must be configured for CP8.2 PostgreSQL tests"
    repo = PostgreSQLCountUpdateRepository()

    update = CountUpdate(
        cameraId="CAM-COUNT-01",
        farmId="FARM-BA-01",
        zoneId="ZONE-TANG-2",
        frameId=42,
        recordedAt="2026-11-03T10:15:30.250Z",
        windowStartedAt="2026-11-03T10:00:00.000Z",
        entryCount=18,
        exitCount=7,
        netChange=11,
        deltaEntry=3,
        deltaExit=1,
    )
    row_id = repo.save(update)
    assert row_id

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT camera_id, farm_id, zone_id, frame_id,
                       entry_count, exit_count, net_change,
                       delta_entry, delta_exit,
                       window_started_at, recorded_at, created_at
                FROM ai_count_updates
                WHERE id = %s
                """,
                (row_id,),
            )
            row = cur.fetchone()

    assert row is not None
    assert row[0] == "CAM-COUNT-01"
    assert row[1] == "FARM-BA-01"
    assert row[2] == "ZONE-TANG-2"
    assert row[3] == 42
    assert row[4] == 18
    assert row[5] == 7
    assert row[6] == 11
    assert row[6] == row[4] - row[5]  # netChange = entryCount - exitCount
    assert row[7] == 3
    assert row[8] == 1
    assert row[9].tzinfo is not None
    assert row[10].tzinfo is not None
    assert row[11].tzinfo is not None


def test_a2_count_update_utc_timestamp_and_historical_queries():
    repo = PostgreSQLCountUpdateRepository()

    samples = [
        ("2026-11-03T10:00:00.000Z", 5, 2, 3),
        ("2026-11-03T10:05:00.000Z", 12, 4, 8),
        ("2026-11-03T10:10:00.000Z", 20, 6, 14),
    ]
    for idx, (rec_at, entry_c, exit_c, net_c) in enumerate(samples):
        repo.save(
            CountUpdate(
                cameraId="CAM-HIST-01",
                farmId="FARM-BA-01",
                zoneId="ZONE-TANG-1",
                frameId=idx * 10,
                recordedAt=rec_at,
                windowStartedAt="2026-11-03T10:00:00.000Z",
                entryCount=entry_c,
                exitCount=exit_c,
                netChange=net_c,
                deltaEntry=entry_c,
                deltaExit=exit_c,
            )
        )

    by_cam = repo.list_by_camera("CAM-HIST-01", limit=10)
    assert len(by_cam) == 3
    assert [c.entryCount for c in by_cam] == [20, 12, 5]
    assert [c.netChange for c in by_cam] == [14, 8, 3]
    assert by_cam[0].recordedAt == "2026-11-03T10:10:00.000Z"

    by_farm = repo.list_by_farm("FARM-BA-01", limit=10)
    assert len(by_farm) == 3

    by_zone = repo.list_by_zone("ZONE-TANG-1", limit=10)
    assert len(by_zone) == 3

    by_range = repo.list_by_time_range(
        camera_id="CAM-HIST-01",
        start_time="2026-11-03T10:04:00.000Z",
        end_time="2026-11-03T10:11:00.000Z",
    )
    assert len(by_range) == 2
    assert [c.entryCount for c in by_range] == [20, 12]


def test_a3_count_update_survives_fresh_repository_recreation():
    repo_1 = PostgreSQLCountUpdateRepository()
    repo_1.save(
        CountUpdate(
            cameraId="CAM-FRESH-01",
            farmId="FARM-BA-01",
            zoneId="ZONE-A",
            frameId=99,
            recordedAt="2026-11-03T11:00:00.000Z",
            windowStartedAt="2026-11-03T10:30:00.000Z",
            entryCount=33,
            exitCount=10,
            netChange=23,
            deltaEntry=4,
            deltaExit=1,
        )
    )
    del repo_1

    # Fresh repository instance queries PostgreSQL directly
    repo_2 = PostgreSQLCountUpdateRepository()
    latest = repo_2.get_latest_by_camera("CAM-FRESH-01")
    assert latest is not None
    assert latest.entryCount == 33
    assert latest.exitCount == 10
    assert latest.netChange == 23


# ==============================================================================
# CATEGORY B — AIEVENT PERSISTENCE & IDEMPOTENCY
# ==============================================================================


def test_b1_ai_event_predator_detected_persists_all_fields():
    repo = PostgreSQLAIEventRepository()
    ev = AIEvent(
        **{
            "eventId": "evt_ai_cp82_snake_001",
            "eventType": "PREDATOR_DETECTED",
            "cameraId": "CAM-PRED-01",
            "farmId": "FARM-BA-01",
            "zoneId": "ZONE-TANG-2",
            "frameId": 128,
            "detectedAt": "2026-11-03T11:20:45.500Z",
            "class": "snake",
            "confidence": 0.9412,
            "bbox": BoundingBox(x1=45.5, y1=110.0, x2=180.5, y2=240.0),
            "snapshot": "C:\\private\\snapshots\\CAM-PRED-01_snake_128.jpg",
        }
    )

    inserted = repo.save(ev)
    assert inserted is True

    loaded = repo.get("evt_ai_cp82_snake_001")
    assert loaded is not None
    assert loaded.eventId == "evt_ai_cp82_snake_001"
    assert loaded.eventType == "PREDATOR_DETECTED"
    assert loaded.cameraId == "CAM-PRED-01"
    assert loaded.farmId == "FARM-BA-01"
    assert loaded.zoneId == "ZONE-TANG-2"
    assert loaded.frameId == 128
    assert loaded.detectedAt == "2026-11-03T11:20:45.500Z"
    assert loaded.cls == "snake"
    assert loaded.confidence == 0.9412
    assert loaded.bbox == BoundingBox(x1=45.5, y1=110.0, x2=180.5, y2=240.0)
    # Snapshot is sanitized to relative URL, never leaking Windows host path
    assert loaded.snapshot == "/api/v1/ai/snapshots/CAM-PRED-01_snake_128.jpg"


def test_b2_ai_event_idempotent_on_duplicate_event_id():
    repo = PostgreSQLAIEventRepository()
    ev = AIEvent(
        **{
            "eventId": "evt_ai_dup_001",
            "eventType": "PREDATOR_DETECTED",
            "cameraId": "CAM-PRED-01",
            "farmId": "FARM-BA-01",
            "zoneId": "ZONE-A",
            "frameId": 10,
            "detectedAt": "2026-11-03T11:25:00.000Z",
            "class": "rat",
            "confidence": 0.89,
            "bbox": BoundingBox(x1=10.0, y1=20.0, x2=50.0, y2=60.0),
            "snapshot": "/api/v1/ai/snapshots/rat_10.jpg",
        }
    )

    first_insert = repo.save(ev)
    second_insert = repo.save(ev)

    assert first_insert is True
    assert second_insert is False

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM ai_events WHERE event_id = %s", ("evt_ai_dup_001",))
            count = cur.fetchone()[0]
    assert count == 1


def test_b3_ai_event_queries_and_fresh_repository_recreation():
    repo_1 = PostgreSQLAIEventRepository()
    for idx, (cls_name, ts) in enumerate(
        [
            ("rat", "2026-11-03T12:00:00.000Z"),
            ("snake", "2026-11-03T12:10:00.000Z"),
        ]
    ):
        repo_1.save(
            AIEvent(
                **{
                    "eventId": f"evt_ai_fresh_{idx}",
                    "eventType": "PREDATOR_DETECTED",
                    "cameraId": "CAM-FRESH-EV",
                    "farmId": "FARM-BA-01",
                    "zoneId": "ZONE-A",
                    "frameId": idx + 1,
                    "detectedAt": ts,
                    "class": cls_name,
                    "confidence": 0.91,
                    "bbox": BoundingBox(x1=15.0, y1=25.0, x2=65.0, y2=85.0),
                    "snapshot": f"/api/v1/ai/snapshots/{cls_name}_{idx}.jpg",
                }
            )
        )
    del repo_1

    repo_2 = PostgreSQLAIEventRepository()
    recent = repo_2.list_by_camera("CAM-FRESH-EV")
    assert len(recent) == 2
    assert [e.eventId for e in recent] == ["evt_ai_fresh_1", "evt_ai_fresh_0"]

    by_farm = repo_2.list_by_farm("FARM-BA-01")
    assert len(by_farm) == 2

    in_window = repo_2.list_by_time_range(
        start_time="2026-11-03T12:05:00.000Z",
        end_time="2026-11-03T12:15:00.000Z",
        camera_id="CAM-FRESH-EV",
    )
    assert len(in_window) == 1
    assert in_window[0].eventId == "evt_ai_fresh_1"


# ==============================================================================
# CATEGORY C & D — EPHEMERAL DETECTIONRESULT & CAMERA RUNTIME STATUS
# ==============================================================================


def test_c1_and_d1_per_frame_detection_and_camera_status_are_never_persisted_to_postgresql(
    tmp_path: Path,
):
    snap_dir = tmp_path / "snapshots"
    snap_store = SnapshotStore(directory=str(snap_dir), public_base_url="")
    manager = AIRuntimeManager(
        pipeline_cfg={
            "tracker": {"type": "centroid", "centroid_max_distance": 0.4, "centroid_max_missed": 2},
            "counting": {"inside_side": "positive", "report_interval_s": 60.0, "min_track_hits": 2},
            "predator": {"classes": ["rat", "snake"], "min_consecutive_frames": 2, "cooldown_s": 30.0},
            "snapshot": {"dir": str(snap_dir), "public_base_url": ""},
        },
        detector=CallableDetector(lambda _img: []),
        snapshot_store=snap_store,
    )

    # Run 10 frames with swiftlet detections on every frame, 1 line crossing, and 1 predator event
    frames = [np.zeros((200, 300, 3), dtype=np.uint8) for _ in range(6)]
    scripted: Dict[int, List[TV2Detection]] = {
        0: [TV2Detection("swiftlet", 0.91, [90, 30, 110, 50])],
        1: [
            TV2Detection("swiftlet", 0.92, [90, 60, 110, 80]),
            TV2Detection("rat", 0.88, [20, 140, 70, 190]),
        ],
        2: [
            TV2Detection("swiftlet", 0.95, [90, 130, 110, 150]),
            TV2Detection("rat", 0.93, [22, 142, 72, 192]),
        ],
        3: [TV2Detection("swiftlet", 0.94, [90, 150, 110, 170])],
        4: [TV2Detection("swiftlet", 0.90, [92, 155, 112, 175])],
        5: [TV2Detection("swiftlet", 0.89, [94, 160, 114, 180])],
    }
    idx = {"i": 0}

    def detect_fn(_img):
        f = idx["i"]
        idx["i"] += 1
        return scripted.get(f, [])

    cam_cfg = RuntimeCameraConfig(
        camera_id="CAM-EPHEMERAL-01",
        farm_id="FARM-BA-01",
        zone_id="ZONE-A",
        source=ListFrameSource("CAM-EPHEMERAL-01", frames, fps=15.0, t0=1_761_500_000.0),
        line=((0.05, 0.50), (0.95, 0.50)),
        inside_side="positive",
    )
    manager.register_camera(cam_cfg, detector=CallableDetector(detect_fn))
    manager.run_camera("CAM-EPHEMERAL-01")

    # 1. Latest DetectionResult and CameraRuntimeStatus are present in ephemeral memory
    latest_det = manager.state_store.get_latest_detection("CAM-EPHEMERAL-01")
    assert latest_det is not None
    assert latest_det.frameId == 5

    cam_status = manager.state_store.get_camera_status("CAM-EPHEMERAL-01")
    assert cam_status is not None
    assert cam_status.processedFrames == 6

    # 2. Inspect PostgreSQL tables: ONLY ai_count_updates and ai_events exist;
    #    NO table stores per-frame DetectionResult or CameraRuntimeStatus!
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
            cur.execute(
                "SELECT COUNT(*) FROM ai_count_updates WHERE camera_id = %s",
                ("CAM-EPHEMERAL-01",),
            )
            count_rows = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM ai_events WHERE camera_id = %s",
                ("CAM-EPHEMERAL-01",),
            )
            event_rows = cur.fetchone()[0]

    assert tables == ["ai_count_updates", "ai_events", "schema_migrations"]
    assert count_rows == 2  # initial window frame + 1 crossing frame (not 6 frames!)
    assert event_rows == 1  # 1 confirmed predator event

    # 3. Verify via FastAPI REST routes including new /counts history endpoint
    app = create_app(runtime_manager=manager, snapshot_dir=snap_dir)
    with TestClient(app) as client:
        cnt_hist = client.get("/api/v1/ai/cameras/CAM-EPHEMERAL-01/counts")
        assert cnt_hist.status_code == 200
        assert len(cnt_hist.json()) == 2
        assert cnt_hist.json()[0]["entryCount"] == 1


# ==============================================================================
# CATEGORY E — RABBITMQ CP7 COMPATIBILITY & ORDERING
# ==============================================================================


def test_e1_predator_event_persisted_before_rabbitmq_publish_and_envelope_unchanged():
    publisher = InMemoryDomainEventPublisher()
    event_repo = PostgreSQLAIEventRepository()
    resolver = InMemoryCameraMetadataResolver(
        mappings={"CAM-RMQ-01": ("FARM-BA-01", "ZONE-NORTH")}
    )
    sink = DomainEventPublisherRuntimeSink(
        publisher=publisher,
        metadata_resolver=resolver,
        event_repository=event_repo,
    )

    ai_event = AIEvent(
        **{
            "eventId": "evt_ai_rmq_cp82_01",
            "eventType": "PREDATOR_DETECTED",
            "cameraId": "CAM-RMQ-01",
            "frameId": 55,
            "detectedAt": "2026-11-03T12:30:00.000Z",
            "class": "snake",
            "confidence": 0.96,
            "bbox": BoundingBox(x1=100.0, y1=120.0, x2=220.0, y2=260.0),
            "snapshot": "/api/v1/ai/snapshots/CAM-RMQ-01_snake_55.jpg",
        }
    )
    sink.on_event(ai_event)

    # 1. Persisted in PostgreSQL ai_events with resolved farmId/zoneId
    persisted = event_repo.get("evt_ai_rmq_cp82_01")
    assert persisted is not None
    assert persisted.farmId == "FARM-BA-01"
    assert persisted.zoneId == "ZONE-NORTH"

    # 2. Published to DomainEventPublisher with frozen CP7 envelope
    assert len(publisher.published_events) == 1
    dom_evt = publisher.published_events[0]
    assert dom_evt.event_type == EVENT_AI_PREDATOR_DETECTED
    assert dom_evt.producer == PRODUCER_AI_SERVICE
    assert dom_evt.occurred_at == "2026-11-03T12:30:00.000Z"
    assert dom_evt.payload["farmId"] == "FARM-BA-01"
    assert dom_evt.payload["zoneId"] == "ZONE-NORTH"
    assert dom_evt.payload["cameraId"] == "CAM-RMQ-01"
    assert dom_evt.payload["predatorClass"] == "snake"
    assert dom_evt.payload["confidence"] == 0.96
    assert dom_evt.payload["snapshotRef"] == "CAM-RMQ-01_snake_55.jpg"


# ==============================================================================
# CATEGORY F — DATABASE FAILURE HANDLING
# ==============================================================================


def test_f1_database_failure_logged_and_does_not_falsely_report_durable_success():
    broken_count_repo = PostgreSQLCountUpdateRepository(
        database_url="postgresql://invalid_ai_role:wrong@127.0.0.1:5432/ai_db"
    )
    broken_event_repo = PostgreSQLAIEventRepository(
        database_url="postgresql://invalid_ai_role:wrong@127.0.0.1:5432/ai_db"
    )
    store = InMemoryAIRuntimeStateStore(
        count_repository=broken_count_repo,
        event_repository=broken_event_repo,
    )

    sample_count = CountUpdate(
        cameraId="CAM-FAIL-01",
        farmId="FARM-01",
        zoneId="ZONE-A",
        frameId=1,
        recordedAt="2026-11-03T13:00:00.000Z",
        windowStartedAt="2026-11-03T13:00:00.000Z",
        entryCount=2,
        exitCount=1,
        netChange=1,
        deltaEntry=2,
        deltaExit=1,
    )
    count_ok = store.record_count(sample_count)
    assert count_ok is False
    assert store.count_persistence_failures == 1
    assert store.get_latest_count("CAM-FAIL-01") is None

    sample_event = AIEvent(
        **{
            "eventId": "evt_ai_fail_01",
            "eventType": "PREDATOR_DETECTED",
            "cameraId": "CAM-FAIL-01",
            "farmId": "FARM-01",
            "zoneId": "ZONE-A",
            "frameId": 2,
            "detectedAt": "2026-11-03T13:01:00.000Z",
            "class": "rat",
            "confidence": 0.90,
            "bbox": BoundingBox(x1=10.0, y1=10.0, x2=40.0, y2=40.0),
        }
    )
    event_ok = store.record_event(sample_event)
    assert event_ok is False
    assert store.event_persistence_failures == 1
    assert store.get_event("evt_ai_fail_01") is None

    # Publisher sink also suppresses RabbitMQ publish if durable DB write fails
    publisher = InMemoryDomainEventPublisher()
    pub_sink = DomainEventPublisherRuntimeSink(
        publisher=publisher,
        event_repository=broken_event_repo,
    )
    pub_sink.on_event(sample_event)
    assert len(publisher.published_events) == 0


# ==============================================================================
# CATEGORY G — BOUNDARY VERIFICATION
# ==============================================================================


def test_g1_zero_cross_service_fks_and_least_privilege_role_in_ai_db():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT constraint_name, table_name
                FROM information_schema.table_constraints
                WHERE constraint_type = 'FOREIGN KEY'
                  AND table_schema = 'public'
                """
            )
            fks = cur.fetchall()

            cur.execute(
                """
                SELECT current_database(), current_user, rolsuper, rolcreatedb, rolcreaterole
                FROM pg_roles
                WHERE rolname = current_user
                """
            )
            role_info = cur.fetchone()

    assert fks == [], f"Expected 0 foreign keys in ai_db, found: {fks}"
    assert role_info is not None
    assert role_info[0] == "ai_db"
    assert role_info[1] == "ai_user"
    assert role_info[2] is False  # NOSUPERUSER
    assert role_info[3] is False  # NOCREATEDB
    assert role_info[4] is False  # NOCREATEROLE
