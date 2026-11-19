"""Unit tests for AI Service domain event contracts, schemas, and runtime sink (CP7.3 / CP7.3A)."""
from __future__ import annotations

import uuid
from typing import Any
import pytest
from pydantic import ValidationError

from app.domain_events.constants import (
    CANONICAL_EVENT_VERSION,
    CANONICAL_EXCHANGE,
    EVENT_AI_PREDATOR_DETECTED,
    PRODUCER_AI_SERVICE,
    SUPPORTED_PREDATOR_CLASSES,
)
from app.domain_events.envelope import DomainEvent
from app.domain_events.models import BBoxPayload, PredatorDetectedPayload
from app.ports.domain_event_publisher import (
    InMemoryDomainEventPublisher,
    NoOpDomainEventPublisher,
)
from app.ports.metadata_resolver import (
    InMemoryCameraMetadataResolver,
    default_camera_metadata_resolver,
)
from app.runtime.publisher_sink import DomainEventPublisherRuntimeSink
from app.schemas.canonical import (
    AIEvent,
    BoundingBox,
    CameraRuntimeStatus,
    CountUpdate,
    Detection,
    DetectionResult,
    FrameInfo,
)


def _make_sample_ai_event(
    camera_id: str = "CAM-01",
    predator_cls: str = "rat",
    confidence: float = 0.892,
    farm_id: str | None = "FARM-01",
    zone_id: str | None = "ZONE-01",
    snapshot: str | None = "C:\\app\\snapshots\\snap_123.jpg",
) -> AIEvent:
    return AIEvent(
        eventId=f"evt_ai_{uuid.uuid4().hex[:12]}",
        eventType="PREDATOR_DETECTED",
        cameraId=camera_id,
        farmId=farm_id,
        zoneId=zone_id,
        frameId=42,
        detectedAt="2026-10-28T14:30:00.000Z",
        cls=predator_cls,  # type: ignore[arg-type]
        confidence=confidence,
        bbox=BoundingBox(x1=100.0, y1=150.0, x2=220.0, y2=210.0),
        snapshot=snapshot,
    )


class TestDomainEventEnvelopeAndPayload:
    """Verifies CP7 canonical domain event envelope and payload schemas."""

    def test_canonical_envelope_structure(self) -> None:
        event = DomainEvent(
            eventType=EVENT_AI_PREDATOR_DETECTED,
            payload={"testKey": "testVal"},
        )
        data = event.to_dict()

        assert "eventId" in data
        assert uuid.UUID(data["eventId"], version=4)  # Valid UUIDv4
        assert data["eventType"] == "ai.predator.detected"
        assert data["eventVersion"] == "1.0"
        assert data["producer"] == "ai-service"
        assert data["correlationId"] is None
        assert data["occurredAt"].endswith("Z")
        assert data["payload"] == {"testKey": "testVal"}

    def test_predator_payload_valid_rat(self) -> None:
        bbox = BBoxPayload(x=10.0, y=20.0, width=50.0, height=30.0)
        payload = PredatorDetectedPayload(
            farmId="FARM-01",
            zoneId="ZONE-01",
            cameraId="CAM-01",
            predatorClass="rat",
            confidence=0.8876,
            snapshotRef="snap_rat.jpg",
            frameWidth=1920,
            frameHeight=1080,
            bbox=bbox,
        )
        d = payload.to_dict()
        assert d["farmId"] == "FARM-01"
        assert d["zoneId"] == "ZONE-01"
        assert d["cameraId"] == "CAM-01"
        assert d["predatorClass"] == "rat"
        assert d["confidence"] == 0.8876
        assert d["snapshotRef"] == "snap_rat.jpg"
        assert d["frameWidth"] == 1920
        assert d["frameHeight"] == 1080
        assert d["bbox"] == {"x": 10.0, "y": 20.0, "width": 50.0, "height": 30.0}

    def test_predator_payload_valid_snake(self) -> None:
        bbox = BBoxPayload(x=5.5, y=10.2, width=80.0, height=25.0)
        payload = PredatorDetectedPayload(
            farmId="FARM-01",
            zoneId="ZONE-02",
            cameraId="CAM-02",
            predatorClass="snake",
            confidence=0.91,
            snapshotRef=None,
            frameWidth=1280,
            frameHeight=720,
            bbox=bbox,
        )
        assert payload.predator_class == "snake"
        assert payload.snapshot_ref is None

    def test_predator_payload_rejects_unsupported_classes(self) -> None:
        bbox = BBoxPayload(x=0.0, y=0.0, width=10.0, height=10.0)
        for invalid_cls in ["owl", "cat", "dog", "swiftlet", "eagle"]:
            with pytest.raises(ValidationError):
                PredatorDetectedPayload(
                    farmId="FARM-01",
                    zoneId="ZONE-01",
                    cameraId="CAM-01",
                    predatorClass=invalid_cls,  # type: ignore[arg-type]
                    confidence=0.9,
                    frameWidth=1920,
                    frameHeight=1080,
                    bbox=bbox,
                )

    def test_predator_payload_rejects_invalid_confidence(self) -> None:
        bbox = BBoxPayload(x=0.0, y=0.0, width=10.0, height=10.0)
        with pytest.raises(ValidationError):
            PredatorDetectedPayload(
                farmId="FARM-01",
                zoneId="ZONE-01",
                cameraId="CAM-01",
                predatorClass="rat",
                confidence=1.5,
                frameWidth=1920,
                frameHeight=1080,
                bbox=bbox,
            )


class TestPublisherRuntimeSink:
    """Verifies DomainEventPublisherRuntimeSink filtering, mapping, and leak prevention."""

    def test_publishes_rat_event_successfully(self) -> None:
        publisher = InMemoryDomainEventPublisher()
        sink = DomainEventPublisherRuntimeSink(publisher=publisher)

        ai_evt = _make_sample_ai_event(predator_cls="rat")
        sink.on_event(ai_evt)

        assert len(publisher.published_events) == 1
        event = publisher.published_events[0]
        assert event.event_type == "ai.predator.detected"
        assert event.producer == "ai-service"
        assert event.event_version == "1.0"
        assert event.payload["predatorClass"] == "rat"
        assert event.payload["cameraId"] == "CAM-01"
        assert event.payload["farmId"] == "FARM-01"
        assert event.payload["zoneId"] == "ZONE-01"
        assert event.payload["confidence"] == 0.892
        # Derived bbox
        assert event.payload["bbox"]["x"] == 100.0
        assert event.payload["bbox"]["y"] == 150.0
        assert event.payload["bbox"]["width"] == 120.0  # 220.0 - 100.0
        assert event.payload["bbox"]["height"] == 60.0  # 210.0 - 150.0

    def test_publishes_snake_event_successfully(self) -> None:
        publisher = InMemoryDomainEventPublisher()
        sink = DomainEventPublisherRuntimeSink(publisher=publisher)

        ai_evt = _make_sample_ai_event(predator_cls="snake")
        sink.on_event(ai_evt)

        assert len(publisher.published_events) == 1
        assert publisher.published_events[0].payload["predatorClass"] == "snake"

    def test_snapshot_path_sanitization_prevents_leaks(self) -> None:
        publisher = InMemoryDomainEventPublisher()
        sink = DomainEventPublisherRuntimeSink(publisher=publisher)

        # Windows absolute path
        ai_evt = _make_sample_ai_event(snapshot="C:\\Users\\admin\\secret_farm\\cam1_rat.jpg")
        sink.on_event(ai_evt)

        assert len(publisher.published_events) == 1
        # MUST only contain basename, never full absolute path
        assert publisher.published_events[0].payload["snapshotRef"] == "cam1_rat.jpg"
        assert "Users" not in publisher.published_events[0].payload["snapshotRef"]

    def test_unresolved_metadata_safe_failure_no_fake_ids(self) -> None:
        """CP7.3A: Proves unresolved production metadata never fabricates FARM-01/ZONE-01."""
        publisher = InMemoryDomainEventPublisher()
        # Default production resolver with NO default fallback
        resolver = default_camera_metadata_resolver
        sink = DomainEventPublisherRuntimeSink(publisher=publisher, metadata_resolver=resolver)

        # Unmapped camera with missing event metadata
        ai_evt = _make_sample_ai_event(camera_id="CAM-UNCONFIGURED", farm_id=None, zone_id=None)
        sink.on_event(ai_evt)

        # MUST be dropped safely: 0 events published, no fake FARM-01/ZONE-01 alert created
        assert len(publisher.published_events) == 0

    def test_explicit_resolver_mappings_enrich_metadata(self) -> None:
        publisher = InMemoryDomainEventPublisher()
        resolver = InMemoryCameraMetadataResolver(
            mappings={"CAM-99": ("FARM-PROD-ALPHA", "ZONE-PROD-NORTH")}
        )
        sink = DomainEventPublisherRuntimeSink(publisher=publisher, metadata_resolver=resolver)

        ai_evt = _make_sample_ai_event(camera_id="CAM-99", farm_id=None, zone_id=None)
        sink.on_event(ai_evt)

        assert len(publisher.published_events) == 1
        assert publisher.published_events[0].payload["farmId"] == "FARM-PROD-ALPHA"
        assert publisher.published_events[0].payload["zoneId"] == "ZONE-PROD-NORTH"

    def test_explicit_fixture_fallback_allowed_only_when_configured(self) -> None:
        publisher = InMemoryDomainEventPublisher()
        # Test fixture explicitly allowing default fallbacks
        test_resolver = InMemoryCameraMetadataResolver(
            default_farm_id="FARM-TEST-DEF",
            default_zone_id="ZONE-TEST-DEF",
        )
        sink = DomainEventPublisherRuntimeSink(publisher=publisher, metadata_resolver=test_resolver)

        ai_evt = _make_sample_ai_event(camera_id="CAM-UNMAPPED", farm_id="", zone_id="")
        sink.on_event(ai_evt)

        assert len(publisher.published_events) == 1
        assert publisher.published_events[0].payload["farmId"] == "FARM-TEST-DEF"
        assert publisher.published_events[0].payload["zoneId"] == "ZONE-TEST-DEF"

    def test_caches_frame_dimensions_from_status_and_detection(self) -> None:
        publisher = InMemoryDomainEventPublisher()
        sink = DomainEventPublisherRuntimeSink(publisher=publisher)

        # Notify status with 3840x2160 (4K)
        status = CameraRuntimeStatus(
            cameraId="CAM-4K",
            status="ONLINE",
            sourceConnected=True,
            inferenceStatus="RUNNING",
            fps=25.0,
            width=3840,
            height=2160,
            modelVersion="yolo26",
            trackerType="bytetrack",
            processedFrames=100,
            updatedAt="2026-10-28T14:30:00.000Z",
        )
        sink.on_status(status)

        ai_evt = _make_sample_ai_event(camera_id="CAM-4K")
        sink.on_event(ai_evt)

        assert len(publisher.published_events) == 1
        assert publisher.published_events[0].payload["frameWidth"] == 3840
        assert publisher.published_events[0].payload["frameHeight"] == 2160

    def test_strict_negative_no_publish_on_detection(self) -> None:
        publisher = InMemoryDomainEventPublisher()
        sink = DomainEventPublisherRuntimeSink(publisher=publisher)

        det = DetectionResult(
            cameraId="CAM-01",
            frameId=1,
            capturedAt="2026-10-28T14:30:00.000Z",
            frame=FrameInfo(width=1920, height=1080),
            detections=[
                Detection(
                    trackId=1,
                    cls="swiftlet",
                    confidence=0.95,
                    bbox=BoundingBox(x1=10, y1=10, x2=50, y2=50),
                )
            ],
        )
        sink.on_detection(det)
        assert len(publisher.published_events) == 0

    def test_strict_negative_no_publish_on_count_update(self) -> None:
        publisher = InMemoryDomainEventPublisher()
        sink = DomainEventPublisherRuntimeSink(publisher=publisher)

        count_update = CountUpdate(
            cameraId="CAM-01",
            frameId=10,
            recordedAt="2026-10-28T14:30:00.000Z",
            windowStartedAt="2026-10-28T14:29:00.000Z",
            entryCount=15,
            exitCount=5,
            netChange=10,
            deltaEntry=2,
            deltaExit=1,
        )
        sink.on_count(count_update)
        assert len(publisher.published_events) == 0

    def test_strict_negative_no_publish_on_status(self) -> None:
        publisher = InMemoryDomainEventPublisher()
        sink = DomainEventPublisherRuntimeSink(publisher=publisher)

        status = CameraRuntimeStatus(
            cameraId="CAM-01",
            status="ONLINE",
            sourceConnected=True,
            inferenceStatus="RUNNING",
            fps=30.0,
            width=1920,
            height=1080,
            modelVersion="yolo26",
            trackerType="bytetrack",
            processedFrames=50,
            updatedAt="2026-10-28T14:30:00.000Z",
        )
        sink.on_status(status)
        assert len(publisher.published_events) == 0

    def test_separate_predator_episodes_delivered_faithfully(self) -> None:
        """CP7.3A: Proves sink does not swallow legitimate separate AI events emitted after cooldown."""
        publisher = InMemoryDomainEventPublisher()
        sink = DomainEventPublisherRuntimeSink(publisher=publisher)

        # Episode 1: Rat detected at t=0
        ai_evt1 = _make_sample_ai_event(camera_id="CAM-01", predator_cls="rat")
        sink.on_event(ai_evt1)
        assert len(publisher.published_events) == 1

        # Episode 2: Second valid AIEvent emitted by PredatorMonitor (e.g. after cooldown at t=35)
        ai_evt2 = _make_sample_ai_event(camera_id="CAM-01", predator_cls="rat")
        sink.on_event(ai_evt2)

        # Both legitimate domain events are published
        assert len(publisher.published_events) == 2

    def test_noop_publisher_does_not_raise(self) -> None:
        noop = NoOpDomainEventPublisher()
        sink = DomainEventPublisherRuntimeSink(publisher=noop)

        ai_evt = _make_sample_ai_event(predator_cls="rat")
        sink.on_event(ai_evt)  # should execute smoothly with 0 errors
