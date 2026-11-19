"""Tests verifying Step 6 (v3): RabbitMQRuntimeSink traffic segregation & dynamic camera provisioning."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import create_app
from app.runtime.manager import AIRuntimeManager
from app.runtime.rabbitmq_sink import RabbitMQRuntimeSink
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
from swiftletcare_ai.tracker import CentroidTracker


def _sample_event(camera_id: str = "CAM-01") -> AIEvent:
    return AIEvent(
        eventId="evt_rmq_001",
        eventType="PREDATOR_DETECTED",
        cameraId=camera_id,
        farmId=None,
        zoneId=None,
        frameId=42,
        detectedAt="2026-10-27T14:00:00.000Z",
        cls="snake",
        confidence=0.93,
        bbox=BoundingBox.from_xyxy([10, 20, 50, 60]),
        snapshot="outputs/snapshots/CAM-01_snake_1000.jpg",
    )


def _sample_count(camera_id: str = "CAM-01") -> CountUpdate:
    return CountUpdate(
        cameraId=camera_id,
        farmId=None,
        zoneId=None,
        frameId=100,
        windowStartedAt="2026-10-27T14:00:00.000Z",
        recordedAt="2026-10-27T14:00:05.000Z",
        entryCount=12,
        exitCount=5,
        netChange=7,
        deltaEntry=2,
        deltaExit=1,
    )


def _sample_status(camera_id: str = "CAM-01") -> CameraRuntimeStatus:
    return CameraRuntimeStatus(
        cameraId=camera_id,
        farmId=None,
        zoneId=None,
        status="ONLINE",
        sourceConnected=True,
        inferenceStatus="RUNNING",
        fps=18.5,
        processedFrames=100,
        modelVersion="best",
        trackerType="bytetrack",
        updatedAt="2026-10-27T14:00:05.000Z",
    )


def _sample_detection_result(camera_id: str = "CAM-01") -> DetectionResult:
    return DetectionResult(
        cameraId=camera_id,
        frameId=1,
        capturedAt="2026-10-27T14:00:00.000Z",
        frame=FrameInfo(width=640, height=480),
        detections=[
            Detection(cls="swiftlet", confidence=0.88, bbox=BoundingBox.from_xyxy([10, 10, 30, 30]))
        ],
    )


def test_rabbitmq_sink_publishes_predator_event_with_correct_routing_key():
    """Verify on_event(AIEvent) publishes to exchange swiftletcare.ai with routing key ai.predator.detected."""
    published: List[Tuple[str, str, Dict[str, Any], Dict[str, Any]]] = []

    def fake_publish(exchange: str, routing_key: str, payload: Dict[str, Any], props: Dict[str, Any]) -> None:
        published.append((exchange, routing_key, payload, props))

    sink = RabbitMQRuntimeSink(
        exchange="swiftletcare.ai",
        enabled=True,
        publish_fn=fake_publish,
    )

    ev = _sample_event("CAM-01")
    sink.on_event(ev)
    sink.flush(timeout=1.0)
    sink.close()

    assert len(published) == 1
    exchange, routing_key, payload, props = published[0]
    assert exchange == "swiftletcare.ai"
    assert routing_key == "ai.predator.detected"
    assert payload["eventId"] == "evt_rmq_001"
    assert payload["eventType"] == "PREDATOR_DETECTED"
    assert payload["cameraId"] == "CAM-01"
    assert payload["farmId"] is None
    assert payload["zoneId"] is None
    assert payload["class"] == "snake"
    assert payload["snapshot"] == "/api/v1/ai/snapshots/CAM-01_snake_1000.jpg"
    assert props["content_type"] == "application/json"
    assert props["delivery_mode"] == 2
    assert props["headers"]["eventType"] == "PREDATOR_DETECTED"
    assert props["headers"]["cameraId"] == "CAM-01"


def test_rabbitmq_sink_publishes_count_update_and_skips_detection_and_status_by_default():
    """Verify traffic segregation: DetectionResult is NO-OP, Status is NO-OP by default, CountUpdate uses ai.count.updated."""
    published: List[Tuple[str, str, Dict[str, Any], Dict[str, Any]]] = []

    def fake_publish(exchange: str, routing_key: str, payload: Dict[str, Any], props: Dict[str, Any]) -> None:
        published.append((exchange, routing_key, payload, props))

    # 1. Default mode: publish_counts=True, publish_status=False
    sink = RabbitMQRuntimeSink(
        enabled=True,
        publish_counts=True,
        publish_status=False,
        publish_fn=fake_publish,
    )

    sink.on_detection(_sample_detection_result())  # Must be strict NO-OP
    sink.on_status(_sample_status())               # Must be NO-OP when publish_status=False
    sink.on_count(_sample_count())                 # Must publish to ai.count.updated
    sink.flush(timeout=1.0)
    sink.close()

    assert len(published) == 1
    exchange, routing_key, payload, props = published[0]
    assert exchange == "swiftletcare.ai"
    assert routing_key == "ai.count.updated"
    assert payload["entryCount"] == 12
    assert payload["exitCount"] == 5
    assert payload["netChange"] == 7
    assert props["headers"]["eventType"] == "COUNT_UPDATED"

    # 2. Notification-only mode: publish_counts=False -> on_count becomes NO-OP
    published_notif_only: List[Tuple[str, str, Dict[str, Any], Dict[str, Any]]] = []
    sink_notif_only = RabbitMQRuntimeSink(
        enabled=True,
        publish_counts=False,
        publish_status=False,
        publish_fn=lambda ex, rk, pl, pr: published_notif_only.append((ex, rk, pl, pr)),
    )
    sink_notif_only.on_count(_sample_count())
    sink_notif_only.on_event(_sample_event())
    sink_notif_only.flush(timeout=1.0)
    sink_notif_only.close()

    assert len(published_notif_only) == 1
    assert published_notif_only[0][1] == "ai.predator.detected"


def test_rabbitmq_sink_priority_queue_evicts_count_for_predator_event():
    """Verify high-priority AIEvent (priority=0) evicts lower-priority CountUpdate when queue is full."""
    sink = RabbitMQRuntimeSink(
        enabled=False,  # Keep worker stopped so queue stays full
        max_queue_size=3,
    )
    sink.enabled = True

    sink.on_count(_sample_count("CAM-1"))
    sink.on_count(_sample_count("CAM-2"))
    sink.on_count(_sample_count("CAM-3"))
    assert sink._queue.full()

    # Enqueue urgent predator event (priority=0)
    sink.on_event(_sample_event("CAM-URGENT"))

    assert sink._queue.full()
    top_item = sink._queue.get_nowait()
    assert top_item.priority == 0
    assert top_item.routing_key == "ai.predator.detected"
    assert top_item.payload["cameraId"] == "CAM-URGENT"


def test_rabbitmq_sink_retries_on_failure_and_never_crashes_pipeline(monkeypatch):
    """Verify retry with backoff on transient AMQP failure and safe drop when max_retries is exceeded."""
    attempts = 0
    published_ok: List[str] = []

    def flaky_publish(exchange: str, routing_key: str, payload: Dict[str, Any], props: Dict[str, Any]) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError("AMQP broker socket closed unexpectedly")
        published_ok.append(routing_key)

    sink = RabbitMQRuntimeSink(
        enabled=True,
        max_retries=2,
        publish_fn=flaky_publish,
    )
    sink.on_event(_sample_event())
    sink.flush(timeout=1.5)
    sink.close()

    assert attempts == 2
    assert published_ok == ["ai.predator.detected"]

    # Always failing publisher must never crash caller or manager
    def always_failing_publish(exchange: str, routing_key: str, payload: Dict[str, Any], props: Dict[str, Any]) -> None:
        raise RuntimeError("AMQP broker unreachable")

    sink_fail = RabbitMQRuntimeSink(
        enabled=True,
        max_retries=1,
        publish_fn=always_failing_publish,
    )
    manager = AIRuntimeManager(rabbitmq_sink=sink_fail)
    manager.composite_sink.on_event(_sample_event())
    sink_fail.flush(timeout=1.0)
    manager.close_all()


def test_start_camera_with_dynamic_payload_from_management_service(tmp_path: Path):
    """Verify POST /api/v1/ai/cameras/{cameraId}/start accepts dynamic source & line config from Management Service."""
    img_path = tmp_path / "sample_frame.jpg"
    dummy_img = np.ones((120, 160, 3), dtype=np.uint8) * 120
    cv2.imwrite(str(img_path), dummy_img)

    manager = AIRuntimeManager(
        detector=CallableDetector(
            lambda _img: [TV2Detection(cls="swiftlet", confidence=0.91, bbox=(20.0, 20.0, 50.0, 50.0))]
        ),
        tracker_factory=lambda _cfg: CentroidTracker(),
    )

    app = create_app(runtime_manager=manager, snapshot_dir=tmp_path / "snaps")
    client = TestClient(app)

    res = client.post(
        "/api/v1/ai/cameras/CAM-DYNAMIC-01/start",
        json={
            "source": str(img_path),
            "sourceType": "auto",
            "countingLine": {"start": [0.1, 0.5], "end": [0.9, 0.5]},
            "insideSide": "positive",
            "maxFrames": 1,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["cameraId"] == "CAM-DYNAMIC-01"
    assert body["farmId"] is None
    assert body["zoneId"] is None

    # Wait briefly for the 1-frame background worker to finish
    for _ in range(30):
        st = client.get("/api/v1/ai/cameras/CAM-DYNAMIC-01/status").json()
        if st["processedFrames"] >= 1:
            break
        time.sleep(0.02)

    status_res = client.get("/api/v1/ai/cameras/CAM-DYNAMIC-01/status")
    assert status_res.status_code == 200
    assert status_res.json()["processedFrames"] >= 1

    det_res = client.get("/api/v1/ai/cameras/CAM-DYNAMIC-01/detections/latest")
    assert det_res.status_code == 200
    assert det_res.json()["cameraId"] == "CAM-DYNAMIC-01"
    assert len(det_res.json()["detections"]) == 1

    manager.close_all()

