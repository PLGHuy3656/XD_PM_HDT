"""Tests verifying Step 3: HttpBackendSink actively pushing canonical AI outputs to Backend via httpx."""
from __future__ import annotations

import json
import queue
import time
from typing import List

import httpx
import pytest

from app.runtime.backend_sink import HttpBackendSink
from app.runtime.manager import AIRuntimeManager
from app.schemas.canonical import (
    AIEvent,
    BoundingBox,
    CameraRuntimeStatus,
    CountUpdate,
    Detection,
    DetectionResult,
    FrameInfo,
)


def _sample_event(camera_id: str = "CAM-01") -> AIEvent:
    return AIEvent(
        eventId="evt_test_001",
        eventType="PREDATOR_DETECTED",
        cameraId=camera_id,
        farmId="FARM-01",
        zoneId="ZONE-A",
        frameId=42,
        detectedAt="2026-10-27T14:00:00.000Z",
        cls="snake",
        confidence=0.92,
        bbox=BoundingBox.from_xyxy([10, 20, 50, 60]),
        snapshot="outputs/snapshots/CAM-01_snake_1000.jpg",
    )


def _sample_count(camera_id: str = "CAM-01") -> CountUpdate:
    return CountUpdate(
        cameraId=camera_id,
        farmId="FARM-01",
        zoneId="ZONE-A",
        frameId=100,
        windowStartedAt="2026-10-27T14:00:00.000Z",
        recordedAt="2026-10-27T14:00:05.000Z",
        entryCount=10,
        exitCount=4,
        netChange=6,
        deltaEntry=2,
        deltaExit=1,
    )


def _sample_status(camera_id: str = "CAM-01") -> CameraRuntimeStatus:
    return CameraRuntimeStatus(
        cameraId=camera_id,
        farmId="FARM-01",
        zoneId="ZONE-A",
        status="ONLINE",
        sourceConnected=True,
        inferenceStatus="RUNNING",
        fps=15.0,
        processedFrames=100,
        modelVersion="yolo26n-best",
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


def test_backend_sink_sends_events_counts_and_ignores_detections():
    """Verify HttpBackendSink pushes AIEvent, CountUpdate, CameraRuntimeStatus and ignores DetectionResult."""
    received_requests: List[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        received_requests.append(request)
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(mock_handler)
    client = httpx.Client(transport=transport)

    sink = HttpBackendSink(
        base_url="http://backend-server:3000",
        paths={"events": "/api/ai/events", "counts": "/api/ai/counts", "status": "/api/ai/status"},
        enabled=True,
        client=client,
        api_key="secret-key-123",
    )

    ev = _sample_event()
    cu = _sample_count()
    st = _sample_status()
    det = _sample_detection_result()

    sink.on_event(ev)
    sink.on_count(cu)
    sink.on_status(st)
    sink.on_detection(det)  # Must be NO-OP

    sink.flush(timeout=1.0)
    sink.close()

    # Total requests must be exactly 3 (events, counts, status) - NO detection request!
    assert len(received_requests) == 3

    urls = [str(r.url) for r in received_requests]
    assert "http://backend-server:3000/api/ai/events" in urls
    assert "http://backend-server:3000/api/ai/counts" in urls
    assert "http://backend-server:3000/api/ai/status" in urls

    # Check headers and payloads
    for r in received_requests:
        assert r.headers["X-API-Key"] == "secret-key-123"
        assert r.headers["Authorization"] == "Bearer secret-key-123"

    event_req = next(r for r in received_requests if r.url.path == "/api/ai/events")
    event_body = json.loads(event_req.content)
    assert event_body["eventType"] == "PREDATOR_DETECTED"
    assert event_body["class"] == "snake"
    # Verify snapshot reference was normalized to safe URL path
    assert event_body["snapshot"] == "/api/v1/ai/snapshots/CAM-01_snake_1000.jpg"

    count_req = next(r for r in received_requests if r.url.path == "/api/ai/counts")
    count_body = json.loads(count_req.content)
    assert count_body["netChange"] == 6
    assert count_body["entryCount"] == 10


def test_backend_sink_retry_on_server_error_500():
    """Verify HttpBackendSink automatically retries on HTTP 500 until successful."""
    call_count = 0

    def flaky_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(500, text="Internal Server Error")
        return httpx.Response(200, json={"received": True})

    transport = httpx.MockTransport(flaky_handler)
    client = httpx.Client(transport=transport)

    sink = HttpBackendSink(
        base_url="http://backend-flaky",
        enabled=True,
        max_retries=2,
        client=client,
    )

    sink.on_event(_sample_event())
    sink.flush(timeout=1.0)
    sink.close()

    assert call_count == 2


def test_backend_sink_network_failure_does_not_crash_or_block():
    """Verify network connection failures are logged and do not raise exceptions."""
    def error_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused by peer", request=request)

    transport = httpx.MockTransport(error_handler)
    client = httpx.Client(transport=transport)

    sink = HttpBackendSink(
        base_url="http://offline-backend",
        enabled=True,
        max_retries=1,
        client=client,
    )

    # Should not raise exception
    sink.on_event(_sample_event())
    sink.on_count(_sample_count())
    sink.flush(timeout=1.0)
    sink.close()


def test_backend_sink_priority_drops_status_or_count_for_event():
    """Verify that when queue reaches maxsize, high-priority AIEvent evicts lower priority count/status."""
    sink = HttpBackendSink(
        base_url="http://backend",
        enabled=False,  # Worker not started so queue stays full
        max_queue_size=3,
    )

    sink.enabled = True  # Enable enqueue without starting worker loop

    # Enqueue 3 count updates (priority 10) -> fills queue of size 3
    sink.on_count(_sample_count("CAM-1"))
    sink.on_count(_sample_count("CAM-2"))
    sink.on_count(_sample_count("CAM-3"))

    assert sink._queue.full()

    # Enqueue 1 high-priority AIEvent (priority 0)
    sink.on_event(_sample_event("CAM-PRED"))

    # Queue must still have size 3, and the top item must be the AIEvent!
    assert sink._queue.full()
    top_item = sink._queue.get_nowait()
    assert top_item.priority == 0
    assert top_item.path == "/api/ai/events"


def test_backend_sink_from_config_and_env_overrides(monkeypatch):
    """Verify from_config reads pipeline.yaml and respects env overrides."""
    cfg = {
        "publisher": {
            "type": "http",
            "http": {
                "base_url": "http://config-host:8000",
                "paths": {"events": "/custom/events"},
                "timeout_s": 4.5,
            },
        }
    }

    sink = HttpBackendSink.from_config(cfg)
    assert sink.enabled is True
    assert sink.base_url == "http://config-host:8000"
    assert sink.paths["events"] == "/custom/events"
    assert sink.timeout_s == 4.5
    sink.close()

    # Override via environment variables
    monkeypatch.setenv("AI_BACKEND_ENABLED", "false")
    monkeypatch.setenv("AI_BACKEND_BASE_URL", "http://env-host:9999")
    monkeypatch.setenv("AI_BACKEND_API_KEY", "env-api-token")

    sink_env = HttpBackendSink.from_config(cfg)
    assert sink_env.enabled is False
    assert sink_env.base_url == "http://env-host:9999"
    assert sink_env.api_key == "env-api-token"
    sink_env.close()


def test_runtime_manager_integrates_backend_sink():
    """Verify AIRuntimeManager attaches backend_sink into composite_sink when enabled."""
    received = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        received.append(request)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(mock_handler)
    client = httpx.Client(transport=transport)

    backend_sink = HttpBackendSink(
        base_url="http://manager-backend:3000",
        enabled=True,
        client=client,
    )

    manager = AIRuntimeManager(backend_sink=backend_sink)
    assert manager.backend_sink is backend_sink

    # Emit event through composite sink
    ev = _sample_event()
    manager.composite_sink.on_event(ev)

    backend_sink.flush(timeout=1.0)
    manager.close_all()

    assert len(received) == 1
    assert received[0].url.path == "/api/ai/events"
