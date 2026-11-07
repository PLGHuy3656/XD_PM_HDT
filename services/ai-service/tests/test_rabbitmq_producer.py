"""RabbitMQ integration and adapter tests for AI domain event producer (CP7.3 / CP7.3A).

Validates:
1. Unit verification of RabbitMQEventPublisher (publisher confirms, message properties, persistent delivery).
2. Outage resilience and error isolation (broker failures do not crash AI runtime).
3. Pipeline-to-producer integration:
   - Predator detection (rat/snake) triggers canonical DomainEvent.
   - Swiftlet detections trigger 0 domain events.
   - Count updates trigger 0 domain events.
   - Status transitions trigger 0 domain events.
   - Unresolved camera metadata triggers 0 domain events (safe failure policy).
4. Live RabbitMQ E2E test against exchange 'swiftlet.domain.events' and queue 'notification.alert-events.v1'.
5. Negative live routing: swiftlets, counts, status, and unresolved metadata produce 0 queue messages.
6. Real broker outage lifecycle: stop broker -> publish -> restart -> reconnect -> verify message delivery & outage event drop.
"""
from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import time
import uuid
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock
import pytest

import aio_pika
from app.config import settings
from app.domain_events.constants import (
    CANONICAL_EVENT_VERSION,
    CANONICAL_EXCHANGE,
    EVENT_AI_PREDATOR_DETECTED,
    PRODUCER_AI_SERVICE,
)
from app.domain_events.envelope import DomainEvent
from app.domain_events.models import BBoxPayload, PredatorDetectedPayload
from app.infrastructure.rabbitmq.connection import RabbitMQConnectionManager
from app.infrastructure.rabbitmq.publisher import RabbitMQEventPublisher
from app.ports.domain_event_publisher import InMemoryDomainEventPublisher
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
from infrastructure.rabbitmq.declarator import RabbitMQDeclarator


QUEUE_NOTIFICATION = "notification.alert-events.v1"


def rabbitmq_available() -> bool:
    """Checks if RabbitMQ AMQP port is reachable."""
    try:
        with socket.create_connection((settings.rabbitmq_host, settings.rabbitmq_port), timeout=1):
            return True
    except OSError:
        return False


def get_declarator() -> RabbitMQDeclarator:
    return RabbitMQDeclarator(
        base_url=f"http://{settings.rabbitmq_host}:15672",
        username=settings.rabbitmq_user,
        password=settings.rabbitmq_password,
    )


def drain_queue(queue_name: str = QUEUE_NOTIFICATION) -> int:
    """Purges all unconsumed messages from the queue."""
    if not rabbitmq_available():
        return 0
    try:
        d = get_declarator()
        msgs = d.get_messages(queue_name, count=100, ackmode="ack_requeue_false")
        return len(msgs)
    except Exception:
        return 0


def get_queue_messages(queue_name: str = QUEUE_NOTIFICATION, count: int = 10) -> list[dict]:
    """Retrieves messages from the queue without requeueing."""
    if not rabbitmq_available():
        return []
    d = get_declarator()
    return d.get_messages(queue_name, count=count, ackmode="ack_requeue_false")


def _build_sample_predator_event(
    camera_id: str = "CAM-PROD-01",
    farm_id: str = "FARM-01",
    zone_id: str = "ZONE-01",
    predator_cls: str = "rat",
) -> DomainEvent:
    bbox = BBoxPayload(x=50.0, y=80.0, width=100.0, height=45.0)
    payload = PredatorDetectedPayload(
        farmId=farm_id,
        zoneId=zone_id,
        cameraId=camera_id,
        predatorClass=predator_cls,  # type: ignore[arg-type]
        confidence=0.923,
        snapshotRef="snap_rat_01.jpg",
        frameWidth=1920,
        frameHeight=1080,
        bbox=bbox,
    )
    return DomainEvent(
        eventId=str(uuid.uuid4()),
        eventType=EVENT_AI_PREDATOR_DETECTED,
        eventVersion=CANONICAL_EVENT_VERSION,
        occurredAt="2026-10-28T14:35:00.000Z",
        producer=PRODUCER_AI_SERVICE,
        correlationId=None,
        payload=payload.to_dict(),
    )


class TestRabbitMQPublisherUnit:
    """Unit tests for RabbitMQEventPublisher behavior with mocked aio-pika components."""

    @pytest.mark.anyio
    async def test_publisher_confirms_and_persistent_delivery(self) -> None:
        mock_exchange = AsyncMock(spec=aio_pika.abc.AbstractExchange)
        mock_conn_mgr = MagicMock(spec=RabbitMQConnectionManager)
        mock_conn_mgr.is_connected = True
        mock_conn_mgr.get_exchange = AsyncMock(return_value=mock_exchange)

        publisher = RabbitMQEventPublisher(connection_manager=mock_conn_mgr)

        event = _build_sample_predator_event()
        await publisher.publish(event)

        assert publisher.published_count == 1
        assert publisher.failed_count == 0
        assert publisher.last_error is None

        # Verify exchange.publish was called
        mock_exchange.publish.assert_awaited_once()
        call_args = mock_exchange.publish.await_args
        published_msg = call_args[0][0]
        routing_key = call_args[1]["routing_key"]

        # Check routing key matches canonical event type
        assert routing_key == "ai.predator.detected"

        # Check message envelope
        assert published_msg.delivery_mode == aio_pika.DeliveryMode.PERSISTENT
        assert published_msg.content_type == "application/json"
        assert published_msg.message_id == event.event_id
        assert published_msg.type == "ai.predator.detected"

        # Check body JSON deserialization
        body_dict = json.loads(published_msg.body.decode("utf-8"))
        assert body_dict["eventId"] == event.event_id
        assert body_dict["eventType"] == "ai.predator.detected"
        assert body_dict["producer"] == "ai-service"
        assert body_dict["payload"]["predatorClass"] == "rat"
        assert body_dict["payload"]["confidence"] == 0.923

    @pytest.mark.anyio
    async def test_publisher_outage_resilience(self) -> None:
        """Verifies broker errors do not raise unhandled exceptions and crash caller."""
        mock_conn_mgr = MagicMock(spec=RabbitMQConnectionManager)
        mock_conn_mgr.is_connected = True
        mock_conn_mgr.get_exchange = AsyncMock(side_effect=ConnectionResetError("Broker unreachable"))

        publisher = RabbitMQEventPublisher(connection_manager=mock_conn_mgr)

        event = _build_sample_predator_event()
        # Should not raise exception
        await publisher.publish(event)

        assert publisher.published_count == 0
        assert publisher.failed_count == 1
        assert "Broker unreachable" in str(publisher.last_error)


class TestPipelineToPublisherIntegration:
    """Verifies end-to-end integration between AI pipeline events and publisher sink."""

    def test_predator_detection_to_domain_event_flow(self) -> None:
        publisher = InMemoryDomainEventPublisher()
        metadata_resolver = InMemoryCameraMetadataResolver(
            mappings={"CAM-01": ("FARM-ALPHA", "ZONE-NORTH")}
        )
        sink = DomainEventPublisherRuntimeSink(
            publisher=publisher,
            metadata_resolver=metadata_resolver,
        )

        # 1. Status event gives camera frame dimensions
        sink.on_status(
            CameraRuntimeStatus(
                cameraId="CAM-01",
                status="ONLINE",
                sourceConnected=True,
                inferenceStatus="RUNNING",
                fps=25.0,
                width=1920,
                height=1080,
                modelVersion="yolo26",
                trackerType="bytetrack",
                processedFrames=10,
                updatedAt="2026-10-28T14:30:00.000Z",
            )
        )
        assert len(publisher.published_events) == 0

        # 2. Frame with swiftlets (detection result)
        sink.on_detection(
            DetectionResult(
                cameraId="CAM-01",
                farmId="FARM-ALPHA",
                zoneId="ZONE-NORTH",
                frameId=1,
                capturedAt="2026-10-28T14:30:01.000Z",
                frame=FrameInfo(width=1920, height=1080),
                detections=[
                    Detection(
                        trackId=1,
                        cls="swiftlet",
                        confidence=0.96,
                        bbox=BoundingBox(x1=200, y1=300, x2=240, y2=330),
                    )
                ],
            )
        )
        assert len(publisher.published_events) == 0

        # 3. Count update on crossing
        sink.on_count(
            CountUpdate(
                cameraId="CAM-01",
                farmId="FARM-ALPHA",
                zoneId="ZONE-NORTH",
                frameId=1,
                recordedAt="2026-10-28T14:30:01.000Z",
                windowStartedAt="2026-10-28T14:29:00.000Z",
                entryCount=1,
                exitCount=0,
                netChange=1,
                deltaEntry=1,
                deltaExit=0,
            )
        )
        assert len(publisher.published_events) == 0

        # 4. Immediate predator event (e.g. rat detected)
        ai_event = AIEvent(
            eventId="evt_ai_123456",
            eventType="PREDATOR_DETECTED",
            cameraId="CAM-01",
            farmId="FARM-ALPHA",
            zoneId="ZONE-NORTH",
            frameId=2,
            detectedAt="2026-10-28T14:30:02.000Z",
            cls="rat",
            confidence=0.915,
            bbox=BoundingBox(x1=300.0, y1=400.0, x2=380.0, y2=450.0),
            snapshot="C:\\data\\snapshots\\rat_cam01.jpg",
        )
        sink.on_event(ai_event)

        # EXACTLY 1 domain event should have been published
        assert len(publisher.published_events) == 1
        published = publisher.published_events[0]
        assert published.event_type == "ai.predator.detected"
        assert published.payload["farmId"] == "FARM-ALPHA"
        assert published.payload["zoneId"] == "ZONE-NORTH"
        assert published.payload["cameraId"] == "CAM-01"
        assert published.payload["predatorClass"] == "rat"
        assert published.payload["confidence"] == 0.915
        assert published.payload["snapshotRef"] == "rat_cam01.jpg"
        assert published.payload["frameWidth"] == 1920
        assert published.payload["frameHeight"] == 1080
        assert published.payload["bbox"] == {
            "x": 300.0,
            "y": 400.0,
            "width": 80.0,
            "height": 50.0,
        }

    def test_strict_isolation_swiftlets_and_counts_never_publish(self) -> None:
        """Negative test ensuring no telemetry/count/bird detections ever trigger RabbitMQ."""
        publisher = InMemoryDomainEventPublisher()
        sink = DomainEventPublisherRuntimeSink(publisher=publisher)

        # Emit 50 detection frames with swiftlets
        for i in range(50):
            sink.on_detection(
                DetectionResult(
                    cameraId="CAM-01",
                    frameId=i,
                    capturedAt="2026-10-28T14:30:00.000Z",
                    frame=FrameInfo(width=1920, height=1080),
                    detections=[
                        Detection(
                            trackId=i,
                            cls="swiftlet",
                            confidence=0.90,
                            bbox=BoundingBox(x1=10, y1=10, x2=20, y2=20),
                        )
                    ],
                )
            )

        # Emit 20 count updates
        for j in range(20):
            sink.on_count(
                CountUpdate(
                    cameraId="CAM-01",
                    frameId=j,
                    recordedAt="2026-10-28T14:30:00.000Z",
                    windowStartedAt="2026-10-28T14:29:00.000Z",
                    entryCount=j,
                    exitCount=0,
                    netChange=j,
                    deltaEntry=1,
                    deltaExit=0,
                )
            )

        # 0 events in publisher
        assert len(publisher.published_events) == 0

    def test_unresolved_metadata_dropped_without_publishing(self) -> None:
        """Negative test ensuring unmapped cameras never publish fake business IDs."""
        publisher = InMemoryDomainEventPublisher()
        sink = DomainEventPublisherRuntimeSink(
            publisher=publisher,
            metadata_resolver=default_camera_metadata_resolver,
        )

        ai_event = AIEvent(
            eventId="evt_unresolved",
            eventType="PREDATOR_DETECTED",
            cameraId="CAM-UNRESOLVED",
            frameId=1,
            detectedAt="2026-10-28T14:30:00.000Z",
            cls="rat",
            confidence=0.90,
            bbox=BoundingBox(x1=10, y1=10, x2=20, y2=20),
        )
        sink.on_event(ai_event)
        assert len(publisher.published_events) == 0


@pytest.mark.skipif(not rabbitmq_available(), reason="RabbitMQ broker not reachable on port 5672")
class TestRabbitMQLiveBrokerE2E:
    """Live broker E2E tests against swiftlet.domain.events exchange and notification queue."""

    @pytest.mark.anyio
    async def test_live_publish_ai_predator_detected(self) -> None:
        """CP7.3A Item 2: Full live E2E verification of ai.predator.detected entering notification queue."""
        drain_queue(QUEUE_NOTIFICATION)

        conn_mgr = RabbitMQConnectionManager(
            host=settings.rabbitmq_host,
            port=settings.rabbitmq_port,
            user=settings.rabbitmq_user,
            password=settings.rabbitmq_password,
            vhost=settings.rabbitmq_vhost,
            exchange_name=settings.rabbitmq_exchange,
        )
        publisher = RabbitMQEventPublisher(connection_manager=conn_mgr)
        resolver = InMemoryCameraMetadataResolver(
            mappings={"CAM-LIVE-01": ("FARM-LIVE-A", "ZONE-LIVE-01")}
        )
        sink = DomainEventPublisherRuntimeSink(publisher=publisher, metadata_resolver=resolver)

        await publisher.connect()
        assert publisher.is_connected

        # Build confirmed predator AIEvent
        ai_event = AIEvent(
            eventId=f"evt_live_{uuid.uuid4().hex[:8]}",
            eventType="PREDATOR_DETECTED",
            cameraId="CAM-LIVE-01",
            frameId=100,
            detectedAt="2026-10-28T15:05:00.123Z",
            cls="rat",
            confidence=0.945,
            bbox=BoundingBox(x1=150.0, y1=250.0, x2=270.0, y2=320.0),
            snapshot="C:\\data\\snapshots\\live_rat_frame100.jpg",
        )

        # Publish via sink bridge
        sink.on_event(ai_event)

        # Allow async publish task to deliver and receive broker confirm
        await asyncio.sleep(0.5)

        # Retrieve and inspect actual message from notification.alert-events.v1
        messages = get_queue_messages(QUEUE_NOTIFICATION, count=1)
        assert len(messages) == 1, f"Expected 1 message in {QUEUE_NOTIFICATION}, found {len(messages)}"

        msg_data = messages[0]
        routing_key = msg_data.get("routing_key")
        properties = msg_data.get("properties", {})
        payload_str = msg_data.get("payload", "")

        # 1. Routing key validation
        assert routing_key == "ai.predator.detected"

        # 2. AMQP Properties validation
        assert properties.get("delivery_mode") == 2  # Persistent
        assert properties.get("content_type") == "application/json"
        assert properties.get("type") == "ai.predator.detected"

        # 3. Canonical DomainEvent envelope validation
        body = json.loads(payload_str)
        assert uuid.UUID(body["eventId"], version=4)  # Valid UUIDv4
        assert body["eventType"] == "ai.predator.detected"
        assert body["eventVersion"] == "1.0"
        assert body["occurredAt"] == "2026-10-28T15:05:00.123Z"
        assert body["producer"] == "ai-service"
        assert body["correlationId"] is None

        # 4. Payload validation
        p = body["payload"]
        assert p["farmId"] == "FARM-LIVE-A"
        assert p["zoneId"] == "ZONE-LIVE-01"
        assert p["cameraId"] == "CAM-LIVE-01"
        assert p["predatorClass"] == "rat"
        assert p["confidence"] == 0.945
        assert p["snapshotRef"] == "live_rat_frame100.jpg"  # Sanitized!
        assert p["frameWidth"] == 1920
        assert p["frameHeight"] == 1080
        assert p["bbox"] == {
            "x": 150.0,
            "y": 250.0,
            "width": 120.0,
            "height": 70.0,
        }

        await publisher.close()

    @pytest.mark.anyio
    async def test_negative_live_routing(self) -> None:
        """CP7.3A Item 3: Proves detections, counts, status, and unresolved metadata never enter Notification queue."""
        drain_queue(QUEUE_NOTIFICATION)

        conn_mgr = RabbitMQConnectionManager(
            host=settings.rabbitmq_host,
            port=settings.rabbitmq_port,
            user=settings.rabbitmq_user,
            password=settings.rabbitmq_password,
            vhost=settings.rabbitmq_vhost,
            exchange_name=settings.rabbitmq_exchange,
        )
        publisher = RabbitMQEventPublisher(connection_manager=conn_mgr)
        sink = DomainEventPublisherRuntimeSink(
            publisher=publisher,
            metadata_resolver=default_camera_metadata_resolver,
        )

        await publisher.connect()

        # 1. 20 swiftlet detection frames
        for i in range(20):
            sink.on_detection(
                DetectionResult(
                    cameraId="CAM-LIVE-01",
                    farmId="FARM-01",
                    zoneId="ZONE-01",
                    frameId=i,
                    capturedAt="2026-10-28T15:06:00.000Z",
                    frame=FrameInfo(width=1920, height=1080),
                    detections=[
                        Detection(
                            trackId=i,
                            cls="swiftlet",
                            confidence=0.92,
                            bbox=BoundingBox(x1=10, y1=10, x2=30, y2=30),
                        )
                    ],
                )
            )

        # 2. 10 count updates
        for j in range(10):
            sink.on_count(
                CountUpdate(
                    cameraId="CAM-LIVE-01",
                    farmId="FARM-01",
                    zoneId="ZONE-01",
                    frameId=j,
                    recordedAt="2026-10-28T15:06:00.000Z",
                    windowStartedAt="2026-10-28T15:05:00.000Z",
                    entryCount=j,
                    exitCount=0,
                    netChange=j,
                    deltaEntry=1,
                    deltaExit=0,
                )
            )

        # 3. 5 camera runtime status updates
        for s in ["ONLINE", "DEGRADED", "ONLINE"]:
            sink.on_status(
                CameraRuntimeStatus(
                    cameraId="CAM-LIVE-01",
                    status=s,  # type: ignore[arg-type]
                    sourceConnected=True,
                    inferenceStatus="RUNNING",
                    fps=25.0,
                    width=1920,
                    height=1080,
                    modelVersion="yolo26",
                    trackerType="bytetrack",
                    processedFrames=100,
                    updatedAt="2026-10-28T15:06:00.000Z",
                )
            )

        # 4. Predator event on unmapped camera (unresolved metadata)
        unmapped_event = AIEvent(
            eventId="evt_unmapped_live",
            eventType="PREDATOR_DETECTED",
            cameraId="CAM-UNMAPPED-LIVE",
            frameId=999,
            detectedAt="2026-10-28T15:06:00.000Z",
            cls="rat",
            confidence=0.91,
            bbox=BoundingBox(x1=10, y1=10, x2=40, y2=40),
        )
        sink.on_event(unmapped_event)

        # Allow any potential in-flight messages to route
        await asyncio.sleep(0.5)

        # Verify queue remains completely empty
        messages = get_queue_messages(QUEUE_NOTIFICATION, count=10)
        assert len(messages) == 0, f"Expected 0 messages in {QUEUE_NOTIFICATION}, found {len(messages)}"

        await publisher.close()


@pytest.mark.skipif(not rabbitmq_available(), reason="RabbitMQ broker not reachable on port 5672")
class TestBrokerOutageRealLifecycle:
    """CP7.3A Item 7: Proves broker outage behavior, failure isolation, and post-recovery reconnection."""

    @pytest.mark.anyio
    async def test_broker_outage_and_recovery_flow(self) -> None:
        drain_queue(QUEUE_NOTIFICATION)

        conn_mgr = RabbitMQConnectionManager(
            host=settings.rabbitmq_host,
            port=settings.rabbitmq_port,
            user=settings.rabbitmq_user,
            password=settings.rabbitmq_password,
            vhost=settings.rabbitmq_vhost,
            exchange_name=settings.rabbitmq_exchange,
        )
        publisher = RabbitMQEventPublisher(connection_manager=conn_mgr)
        await publisher.connect()
        assert publisher.is_connected

        # 1. Stop RabbitMQ broker
        subprocess.run(["docker", "stop", "swiftletcare-rabbitmq"], check=True, capture_output=True)
        time.sleep(1.0)

        # 2. Attempt to publish confirmed predator event DURING outage
        outage_event = _build_sample_predator_event(camera_id="CAM-OUTAGE-01")
        await publisher.publish(outage_event)

        # Verify failure isolation: failure counter incremented, caller not crashed
        assert publisher.failed_count == 1
        assert publisher.last_error is not None

        # 3. Restart RabbitMQ broker
        subprocess.run(["docker", "start", "swiftletcare-rabbitmq"], check=True, capture_output=True)

        # Wait for broker management API & queue to be completely ready
        start_t = time.time()
        broker_ready = False
        while time.time() - start_t < 35.0:
            time.sleep(1.0)
            try:
                d = get_declarator()
                q_info = d.get_queue_info(QUEUE_NOTIFICATION)
                if q_info and q_info.get("name") == QUEUE_NOTIFICATION:
                    broker_ready = True
                    break
            except Exception:
                pass
        assert broker_ready, "RabbitMQ broker failed to restart within timeout"

        # Brief pause to ensure AMQP port is fully accepting connections
        time.sleep(2.0)

        # 4. Reconnect and publish post-recovery event
        # Create fresh publisher instance to connect to restarted broker
        new_conn_mgr = RabbitMQConnectionManager(
            host=settings.rabbitmq_host,
            port=settings.rabbitmq_port,
            user=settings.rabbitmq_user,
            password=settings.rabbitmq_password,
            vhost=settings.rabbitmq_vhost,
            exchange_name=settings.rabbitmq_exchange,
        )
        recovered_publisher = RabbitMQEventPublisher(connection_manager=new_conn_mgr)
        await recovered_publisher.connect()

        post_event = _build_sample_predator_event(camera_id="CAM-POST-RECOVERY")
        await recovered_publisher.publish(post_event)
        assert recovered_publisher.published_count == 1

        # 5. Inspect queue:
        # Crucial architectural proof:
        # The event emitted DURING outage was DROPPED (no outbox).
        # The post-recovery event was DELIVERED.
        time.sleep(0.5)
        messages = get_queue_messages(QUEUE_NOTIFICATION, count=10)
        assert len(messages) == 1, f"Expected exactly 1 message in queue, found {len(messages)}"

        delivered_body = json.loads(messages[0]["payload"])
        assert delivered_body["eventId"] == post_event.event_id
        assert delivered_body["payload"]["cameraId"] == "CAM-POST-RECOVERY"

        await recovered_publisher.close()
        await publisher.close()
