"""Live RabbitMQ & Redis E2E tests for Notification Service RabbitMQ Consumer Adapter (CP7.5).

Matrix Coverage (CP7.5 Section 38):
A. Valid AI predator -> Alert
B. Valid IoT condition -> Alert
C. Same eventId duplicate -> no duplicate
D. Restart Notification Service -> same eventId still blocked by Redis
E. Temporary failure -> retry delay -> success
F. Persistent temporary failure -> bounded retries -> DLQ verification
G. Malformed event -> direct DLQ
H. Valid event after poison -> processed successfully
I. RabbitMQ restart -> robust recovery
J. Redis restart -> safe recovery and continued duplicate protection
Also verifies: two-consumer concurrency and genuine different eventIds alert dedup.
"""
from __future__ import annotations

import asyncio
import json
import logging
import socket
import subprocess
import time
import uuid
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock
import pytest

import aio_pika
import redis.asyncio as aioredis

from app.dependencies import init_app_state
from app.domain.enums import AlertEventType, AlertSeverity, AlertStatus, DevicePlatform
from app.infrastructure.rabbitmq.config import RabbitMQSettings, RedisSettings
from app.infrastructure.rabbitmq.connection import RabbitMQConnectionManager
from app.infrastructure.rabbitmq.consumer import RabbitMQAlertConsumer
from app.infrastructure.rabbitmq.idempotency import InMemoryIdempotencyStore, RedisIdempotencyStore
from app.ports.recipient_resolver import RecipientInfo
from app.repositories.in_memory_alert_repo import InMemoryAlertRepository
from app.repositories.in_memory_notification_repo import InMemoryNotificationRepository
from app.repositories.in_memory_user_device_repo import InMemoryUserDeviceRepository
from app.schemas.canonical import UserDevice
from app.services.in_memory_recipient_resolver import InMemoryRecipientResolver
from app.services.mock_fcm_provider import MockFCMProvider
from infrastructure.rabbitmq.declarator import RabbitMQDeclarator

QUEUE_NOTIFICATION = "notification.alert-events.v1"
QUEUE_RETRY = "notification.alert-events.v1.retry"
QUEUE_DLQ = "notification.alert-events.v1.dlq"
EXCHANGE_EVENTS = "swiftlet.domain.events"
EXCHANGE_RETRY = "swiftlet.notification.retry"
EXCHANGE_DLX = "swiftlet.notification.dlx"

log = logging.getLogger("test_rabbitmq_consumer_live")


def rabbitmq_available() -> bool:
    """Checks if RabbitMQ AMQP port 5672 is reachable."""
    try:
        with socket.create_connection(("127.0.0.1", 5672), timeout=1.0):
            return True
    except OSError:
        return False


def redis_available() -> bool:
    """Checks if Redis port 6379 is reachable."""
    try:
        with socket.create_connection(("127.0.0.1", 6379), timeout=1.0):
            return True
    except OSError:
        return False


def get_declarator() -> RabbitMQDeclarator:
    return RabbitMQDeclarator(
        base_url="http://127.0.0.1:15672",
        username="swiftlet",
        password="swiftlet123",
    )


def drain_all_queues() -> None:
    """Purges notification queue, retry queue, and DLQ."""
    if not rabbitmq_available():
        return
    declarator = get_declarator()
    for q in (QUEUE_NOTIFICATION, QUEUE_RETRY, QUEUE_DLQ):
        try:
            declarator.purge_queue(q)
        except Exception:
            pass


async def get_clean_redis_store() -> RedisIdempotencyStore:
    """Initializes a connected RedisIdempotencyStore and flushes test keys."""
    client = aioredis.Redis(host="127.0.0.1", port=6379, db=0, decode_responses=False)
    store = RedisIdempotencyStore(
        redis_client=client,
        idempotency_ttl_seconds=86400,
        processing_claim_ttl_seconds=60,
        key_prefix="swiftlet:test_live_idempotency:",
    )
    await store.clear_async()
    return store


@pytest.fixture
def live_env():
    """Sets up clean isolated notification environment for live tests."""
    alert_repo = InMemoryAlertRepository()
    notif_repo = InMemoryNotificationRepository()
    user_device_repo = InMemoryUserDeviceRepository()
    user_device_repo.register_device(
        UserDevice(
            device_id="dev_live_01",
            user_id="user_admin",
            fcm_token="token_admin_live",
            platform=DevicePlatform.ANDROID,
            is_enabled=True,
        )
    )
    resolver = InMemoryRecipientResolver()
    resolver.register_recipient(
        "FARM-LIVE-1",
        RecipientInfo(
            user_id="user_admin",
            email="admin@swiftletcare.com",
            roles=["FARM_OWNER"],
        ),
    )
    fcm_mock = MockFCMProvider()

    service = init_app_state(
        alert_repo=alert_repo,
        notification_repo=notif_repo,
        user_device_repo=user_device_repo,
        recipient_resolver=resolver,
        fcm_provider=fcm_mock,
    )
    return service, alert_repo, notif_repo, fcm_mock


async def publish_raw_amqp(
    routing_key: str,
    payload_dict: dict,
    headers: Optional[dict] = None,
    content_type: str = "application/json",
    exchange_name: str = EXCHANGE_EVENTS,
) -> None:
    """Publishes a raw AMQP message to swiftlet.domain.events (or specified exchange)."""
    conn = await aio_pika.connect_robust("amqp://swiftlet:swiftlet123@127.0.0.1:5672//")
    try:
        channel = await conn.channel()
        exchange = await channel.get_exchange(exchange_name)
        body = json.dumps(payload_dict).encode("utf-8") if isinstance(payload_dict, dict) else payload_dict
        msg = aio_pika.Message(
            body=body,
            content_type=content_type,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            headers=headers or {},
            type=routing_key,
        )
        await exchange.publish(msg, routing_key=routing_key)
    finally:
        await conn.close()


@pytest.mark.skipif(not rabbitmq_available() or not redis_available(), reason="RabbitMQ (5672) or Redis (6379) not available")
class TestRabbitMQConsumerLiveE2E:
    """CP7.5 Live E2E Matrix covering real RabbitMQ, Redis, Bounded Retries, and DLQ."""

    @pytest.mark.anyio
    async def test_live_matrix_a_ai_predator_detected(self, live_env) -> None:
        """Matrix A: Real AI predator event -> Alert PREDATOR_DETECTED created with metadata."""
        drain_all_queues()
        service, alert_repo, notif_repo, fcm_mock = live_env
        redis_store = await get_clean_redis_store()

        settings = RabbitMQSettings(
            host="127.0.0.1",
            port=5672,
            user="swiftlet",
            password="swiftlet123",
            vhost="/",
            exchange=EXCHANGE_EVENTS,
            queue_name=QUEUE_NOTIFICATION,
            prefetch_count=10,
            enabled=True,
        )
        conn_mgr = RabbitMQConnectionManager(settings=settings)
        consumer = RabbitMQAlertConsumer(
            connection_manager=conn_mgr,
            service=service,
            idempotency_store=redis_store,
        )

        await consumer.start()
        try:
            event_id = str(uuid.uuid4())
            predator_event = {
                "eventId": event_id,
                "eventType": "ai.predator.detected",
                "eventVersion": "1.0",
                "occurredAt": "2026-10-28T16:00:00.000Z",
                "producer": "ai-service",
                "correlationId": None,
                "payload": {
                    "farmId": "FARM-LIVE-1",
                    "zoneId": "ZONE-01",
                    "cameraId": "CAM-LIVE-01",
                    "predatorClass": "rat",
                    "confidence": 0.952,
                    "snapshotRef": "snapshots/rat_frame_100.jpg",
                    "frameWidth": 1920,
                    "frameHeight": 1080,
                    "bbox": {"x": 120.0, "y": 240.0, "width": 80.0, "height": 60.0},
                },
            }

            await publish_raw_amqp(routing_key="ai.predator.detected", payload_dict=predator_event)

            for _ in range(50):
                if len(alert_repo.list_alerts()) > 0:
                    break
                await asyncio.sleep(0.1)

            alerts = alert_repo.list_alerts()
            assert len(alerts) == 1
            alert = alerts[0]

            assert alert.farm_id == "FARM-LIVE-1"
            assert alert.zone_id == "ZONE-01"
            assert alert.camera_id == "CAM-LIVE-01"
            assert alert.event_type == AlertEventType.PREDATOR_DETECTED
            assert alert.status == AlertStatus.OPEN
            assert alert.severity == AlertSeverity.CRITICAL
            assert "rat" in alert.title.lower() or "rat" in alert.message.lower()
            assert alert.snapshot_url == "snapshots/rat_frame_100.jpg"
            assert alert.occurrence_count == 1

            # Verify notification created and FCM dispatched
            user_notifs = notif_repo.list_by_user("user_admin")
            assert len(user_notifs) == 2
            assert len(fcm_mock.sent_messages) >= 1

            # Verify state recorded in Redis as DONE
            assert await redis_store.has_processed_async(event_id) is True
        finally:
            await consumer.stop()

    @pytest.mark.anyio
    async def test_live_matrix_b_iot_environment_lifecycle(self, live_env) -> None:
        """Matrix B: iot.environment.high_temperature.started creates alert, recovered resolves same alert."""
        drain_all_queues()
        service, alert_repo, _, _ = live_env
        redis_store = await get_clean_redis_store()

        settings = RabbitMQSettings(
            host="127.0.0.1",
            port=5672,
            user="swiftlet",
            password="swiftlet123",
            vhost="/",
            exchange=EXCHANGE_EVENTS,
            queue_name=QUEUE_NOTIFICATION,
            prefetch_count=10,
            enabled=True,
        )
        conn_mgr = RabbitMQConnectionManager(settings=settings)
        consumer = RabbitMQAlertConsumer(
            connection_manager=conn_mgr,
            service=service,
            idempotency_store=redis_store,
        )

        await consumer.start()
        try:
            # 1. High Temperature Started
            start_event = {
                "eventId": str(uuid.uuid4()),
                "eventType": "iot.environment.high_temperature.started",
                "eventVersion": "1.0",
                "occurredAt": "2026-10-28T16:05:00.000Z",
                "producer": "iot-service",
                "correlationId": None,
                "payload": {
                    "farmId": "FARM-LIVE-1",
                    "zoneId": "ZONE-01",
                    "deviceId": "DEV-TEMP-01",
                    "metric": "temperature",
                    "value": 34.2,
                    "threshold": 31.0,
                    "unit": "°C",
                },
            }
            await publish_raw_amqp(routing_key="iot.environment.high_temperature.started", payload_dict=start_event)

            for _ in range(50):
                if len(alert_repo.list_alerts()) > 0:
                    break
                await asyncio.sleep(0.1)

            alerts = alert_repo.list_alerts()
            assert len(alerts) == 1
            alert = alerts[0]
            assert alert.event_type == AlertEventType.HIGH_TEMPERATURE
            assert alert.status == AlertStatus.OPEN
            assert alert.severity == AlertSeverity.HIGH
            assert alert.telemetry_snapshot.get("value") == 34.2

            # 2. High Temperature Recovered
            recovery_event = {
                "eventId": str(uuid.uuid4()),
                "eventType": "iot.environment.high_temperature.recovered",
                "eventVersion": "1.0",
                "occurredAt": "2026-10-28T16:10:00.000Z",
                "producer": "iot-service",
                "correlationId": None,
                "payload": {
                    "farmId": "FARM-LIVE-1",
                    "zoneId": "ZONE-01",
                    "deviceId": "DEV-TEMP-01",
                    "metric": "temperature",
                    "value": 30.2,
                    "threshold": 30.5,
                    "unit": "°C",
                },
            }
            await publish_raw_amqp(routing_key="iot.environment.high_temperature.recovered", payload_dict=recovery_event)

            for _ in range(50):
                refreshed = alert_repo.get_by_id(alert.alert_id)
                if refreshed and refreshed.status == AlertStatus.RESOLVED:
                    break
                await asyncio.sleep(0.1)

            resolved = alert_repo.get_by_id(alert.alert_id)
            assert resolved is not None
            assert resolved.status == AlertStatus.RESOLVED
            assert resolved.resolved_at is not None
            assert len(alert_repo.list_alerts()) == 1
        finally:
            await consumer.stop()

    @pytest.mark.anyio
    async def test_live_matrix_c_message_idempotency_duplicate(self, live_env) -> None:
        """Matrix C: Redelivery of exact same eventId produces zero duplicate side-effects."""
        drain_all_queues()
        service, alert_repo, notif_repo, _ = live_env
        redis_store = await get_clean_redis_store()

        settings = RabbitMQSettings(
            host="127.0.0.1",
            port=5672,
            user="swiftlet",
            password="swiftlet123",
            vhost="/",
            exchange=EXCHANGE_EVENTS,
            queue_name=QUEUE_NOTIFICATION,
            prefetch_count=10,
            enabled=True,
        )
        conn_mgr = RabbitMQConnectionManager(settings=settings)
        consumer = RabbitMQAlertConsumer(
            connection_manager=conn_mgr,
            service=service,
            idempotency_store=redis_store,
        )

        await consumer.start()
        try:
            duplicate_event_id = str(uuid.uuid4())
            event_body = {
                "eventId": duplicate_event_id,
                "eventType": "iot.environment.high_temperature.started",
                "eventVersion": "1.0",
                "occurredAt": "2026-10-28T16:25:00.000Z",
                "producer": "iot-service",
                "payload": {
                    "farmId": "FARM-LIVE-1",
                    "zoneId": "ZONE-01",
                    "deviceId": "DEV-DUP-01",
                    "metric": "temperature",
                    "value": 34.0,
                    "threshold": 31.0,
                    "unit": "°C",
                },
            }

            # First delivery
            await publish_raw_amqp(routing_key="iot.environment.high_temperature.started", payload_dict=event_body)

            for _ in range(50):
                if len(alert_repo.list_alerts()) > 0:
                    break
                await asyncio.sleep(0.1)

            assert len(alert_repo.list_alerts()) == 1
            alert = alert_repo.list_alerts()[0]
            assert alert.occurrence_count == 1
            notif_count_before = len(notif_repo.list_by_user("user_admin"))

            # Second delivery with EXACT same eventId
            await publish_raw_amqp(routing_key="iot.environment.high_temperature.started", payload_dict=event_body)
            await asyncio.sleep(0.6)

            # State unchanged: occurrence_count remains 1, notification count unchanged!
            refreshed = alert_repo.get_by_id(alert.alert_id)
            assert refreshed is not None
            assert refreshed.occurrence_count == 1
            assert len(notif_repo.list_by_user("user_admin")) == notif_count_before
            assert consumer.duplicate_count == 1
        finally:
            await consumer.stop()

    @pytest.mark.anyio
    async def test_live_matrix_d_redis_durable_idempotency_across_restart(self, live_env) -> None:
        """Matrix D: Duplicate protection survives Notification consumer restart thanks to Redis."""
        drain_all_queues()
        service, alert_repo, notif_repo, _ = live_env
        redis_store = await get_clean_redis_store()

        settings = RabbitMQSettings(
            host="127.0.0.1",
            port=5672,
            user="swiftlet",
            password="swiftlet123",
            vhost="/",
            exchange=EXCHANGE_EVENTS,
            queue_name=QUEUE_NOTIFICATION,
            prefetch_count=10,
            enabled=True,
        )

        # 1. Run consumer #1
        conn_mgr1 = RabbitMQConnectionManager(settings=settings)
        consumer1 = RabbitMQAlertConsumer(
            connection_manager=conn_mgr1,
            service=service,
            idempotency_store=redis_store,
        )
        await consumer1.start()

        event_id = str(uuid.uuid4())
        event = {
            "eventId": event_id,
            "eventType": "iot.audio.fault.started",
            "eventVersion": "1.0",
            "occurredAt": "2026-10-28T16:35:00.000Z",
            "producer": "iot-service",
            "payload": {
                "farmId": "FARM-LIVE-1",
                "deviceId": "SPEAKER-01",
                "faultType": "amplifier_disconnected",
            },
        }
        await publish_raw_amqp(routing_key="iot.audio.fault.started", payload_dict=event)

        for _ in range(50):
            if len(alert_repo.list_alerts()) > 0:
                break
            await asyncio.sleep(0.1)

        assert len(alert_repo.list_alerts()) == 1
        assert alert_repo.list_alerts()[0].occurrence_count == 1
        notif_count_before = len(notif_repo.list_by_user("user_admin"))

        # Stop consumer #1 (simulates process crash / restart)
        await consumer1.stop()
        assert not consumer1.is_running

        # 2. Run consumer #2 (fresh process instance, sharing same Redis store)
        conn_mgr2 = RabbitMQConnectionManager(settings=settings)
        consumer2 = RabbitMQAlertConsumer(
            connection_manager=conn_mgr2,
            service=service,
            idempotency_store=redis_store,
        )
        await consumer2.start()
        try:
            # Publish identical eventId to consumer #2
            await publish_raw_amqp(routing_key="iot.audio.fault.started", payload_dict=event)
            await asyncio.sleep(0.6)

            # Redis-backed idempotency prevented reprocessing even after consumer restart!
            assert len(alert_repo.list_alerts()) == 1
            assert alert_repo.list_alerts()[0].occurrence_count == 1
            assert len(notif_repo.list_by_user("user_admin")) == notif_count_before
            assert consumer2.duplicate_count == 1
        finally:
            await consumer2.stop()

    @pytest.mark.anyio
    async def test_live_two_consumers_concurrent_claim(self, live_env) -> None:
        """Section 21: Two concurrent consumers sharing Redis; duplicate delivery processed exactly once."""
        drain_all_queues()
        service, alert_repo, _, _ = live_env
        redis_store = await get_clean_redis_store()

        settings = RabbitMQSettings(
            host="127.0.0.1",
            port=5672,
            user="swiftlet",
            password="swiftlet123",
            vhost="/",
            exchange=EXCHANGE_EVENTS,
            queue_name=QUEUE_NOTIFICATION,
            prefetch_count=5,
            enabled=True,
        )

        conn_mgr1 = RabbitMQConnectionManager(settings=settings)
        consumer1 = RabbitMQAlertConsumer(connection_manager=conn_mgr1, service=service, idempotency_store=redis_store)
        conn_mgr2 = RabbitMQConnectionManager(settings=settings)
        consumer2 = RabbitMQAlertConsumer(connection_manager=conn_mgr2, service=service, idempotency_store=redis_store)

        await consumer1.start()
        await consumer2.start()
        try:
            event_id = str(uuid.uuid4())
            event = {
                "eventId": event_id,
                "eventType": "iot.device.offline",
                "eventVersion": "1.0",
                "occurredAt": "2026-10-28T16:38:00.000Z",
                "producer": "iot-service",
                "payload": {"farmId": "FARM-LIVE-1", "deviceId": "NODE-GW-01"},
            }

            # Publish same message twice rapidly
            await publish_raw_amqp(routing_key="iot.device.offline", payload_dict=event)
            await publish_raw_amqp(routing_key="iot.device.offline", payload_dict=event)

            await asyncio.sleep(0.8)

            assert len(alert_repo.list_alerts()) == 1
            assert alert_repo.list_alerts()[0].event_type == AlertEventType.DEVICE_OFFLINE
            # Total processed across both consumers is 1; total duplicates is 1
            total_processed = consumer1.processed_count + consumer2.processed_count
            total_duplicate = consumer1.duplicate_count + consumer2.duplicate_count
            assert total_processed == 1
            assert total_duplicate == 1
        finally:
            await consumer1.stop()
            await consumer2.stop()

    @pytest.mark.anyio
    async def test_live_genuine_different_event_ids_trigger_domain_dedup(self, live_env) -> None:
        """Section 22: Different eventIds for same active condition increment occurrence_count (Alert Dedup != Message Idempotency)."""
        drain_all_queues()
        service, alert_repo, _, _ = live_env
        redis_store = await get_clean_redis_store()

        settings = RabbitMQSettings(
            host="127.0.0.1",
            port=5672,
            user="swiftlet",
            password="swiftlet123",
            vhost="/",
            exchange=EXCHANGE_EVENTS,
            queue_name=QUEUE_NOTIFICATION,
            prefetch_count=10,
            enabled=True,
        )
        conn_mgr = RabbitMQConnectionManager(settings=settings)
        consumer = RabbitMQAlertConsumer(connection_manager=conn_mgr, service=service, idempotency_store=redis_store)

        await consumer.start()
        try:
            # Genuine Event A
            event_a = {
                "eventId": str(uuid.uuid4()),
                "eventType": "iot.environment.high_temperature.started",
                "eventVersion": "1.0",
                "occurredAt": "2026-10-28T16:40:00.000Z",
                "producer": "iot-service",
                "payload": {"farmId": "FARM-LIVE-1", "zoneId": "ZONE-01", "deviceId": "SENSOR-01", "metric": "temperature", "value": 33.0, "threshold": 31.0, "unit": "°C"},
            }
            await publish_raw_amqp(routing_key="iot.environment.high_temperature.started", payload_dict=event_a)

            for _ in range(50):
                if len(alert_repo.list_alerts()) > 0:
                    break
                await asyncio.sleep(0.1)

            assert len(alert_repo.list_alerts()) == 1
            assert alert_repo.list_alerts()[0].occurrence_count == 1

            # Genuine Event B (different eventId, same sensor breached)
            event_b = {
                "eventId": str(uuid.uuid4()),
                "eventType": "iot.environment.high_temperature.started",
                "eventVersion": "1.0",
                "occurredAt": "2026-10-28T16:41:00.000Z",
                "producer": "iot-service",
                "payload": {"farmId": "FARM-LIVE-1", "zoneId": "ZONE-01", "deviceId": "SENSOR-01", "metric": "temperature", "value": 34.5, "threshold": 31.0, "unit": "°C"},
            }
            await publish_raw_amqp(routing_key="iot.environment.high_temperature.started", payload_dict=event_b)

            for _ in range(50):
                if alert_repo.list_alerts()[0].occurrence_count > 1:
                    break
                await asyncio.sleep(0.1)

            # Both genuine events were accepted by idempotency store; domain layer incremented occurrence_count!
            assert len(alert_repo.list_alerts()) == 1
            assert alert_repo.list_alerts()[0].occurrence_count == 2
            assert consumer.processed_count == 2
            assert consumer.duplicate_count == 0
        finally:
            await consumer.stop()

    @pytest.mark.anyio
    async def test_live_matrix_e_temporary_failure_delayed_retry_and_recovery(self, live_env) -> None:
        """Matrix E: Transient application error publishes to retry queue; after TTL return, second attempt succeeds."""
        drain_all_queues()
        service, alert_repo, _, _ = live_env
        redis_store = await get_clean_redis_store()

        settings = RabbitMQSettings(
            host="127.0.0.1",
            port=5672,
            user="swiftlet",
            password="swiftlet123",
            vhost="/",
            exchange=EXCHANGE_EVENTS,
            queue_name=QUEUE_NOTIFICATION,
            prefetch_count=10,
            max_retries=3,
            retry_ttl_ms=2000,
            enabled=True,
        )
        conn_mgr = RabbitMQConnectionManager(settings=settings)
        consumer = RabbitMQAlertConsumer(connection_manager=conn_mgr, service=service, idempotency_store=redis_store, settings=settings)

        # Injected transient failure: fail on attempt 0 (retryCount == 0), succeed on attempt 1 (retryCount > 0)
        original_process = consumer.mapper.process_envelope
        def flaky_mapper(envelope):
            # Check if this is the first attempt
            if consumer.retry_scheduled_count == 0:
                raise RuntimeError("Transient database lock timeout")
            original_process(envelope)

        consumer.mapper.process_envelope = flaky_mapper

        await consumer.start()
        try:
            event_id = str(uuid.uuid4())
            event = {
                "eventId": event_id,
                "eventType": "iot.device.offline",
                "eventVersion": "1.0",
                "occurredAt": "2026-10-28T16:45:00.000Z",
                "producer": "iot-service",
                "payload": {"farmId": "FARM-LIVE-1", "deviceId": "GATEWAY-RETRY-01"},
            }
            await publish_raw_amqp(routing_key="iot.device.offline", payload_dict=event)

            # Wait for consumer to schedule retry (attempt 0 -> retry queue)
            for _ in range(50):
                if consumer.retry_scheduled_count > 0:
                    break
                await asyncio.sleep(0.1)

            assert consumer.retry_scheduled_count == 1
            assert len(alert_repo.list_alerts()) == 0  # Not processed yet

            # Wait for message to return from retry queue after TTL (2000ms + broker dispatch)
            for _ in range(80):
                if len(alert_repo.list_alerts()) > 0:
                    break
                await asyncio.sleep(0.1)

            # Second attempt succeeded!
            alerts = alert_repo.list_alerts()
            assert len(alerts) == 1
            assert alerts[0].device_id == "GATEWAY-RETRY-01"
            assert consumer.processed_count == 1
        finally:
            await consumer.stop()

    @pytest.mark.anyio
    async def test_live_matrix_f_retry_exhaustion_routes_to_dlq(self, live_env) -> None:
        """Matrix F: When retries exceed MAX_RETRIES, message routes cleanly to notification.alert-events.v1.dlq."""
        drain_all_queues()
        service, alert_repo, _, _ = live_env
        declarator = get_declarator()

        settings = RabbitMQSettings(
            host="127.0.0.1",
            port=5672,
            user="swiftlet",
            password="swiftlet123",
            vhost="/",
            exchange=EXCHANGE_EVENTS,
            queue_name=QUEUE_NOTIFICATION,
            prefetch_count=10,
            max_retries=2,
            enabled=True,
        )
        conn_mgr = RabbitMQConnectionManager(settings=settings)
        consumer = RabbitMQAlertConsumer(connection_manager=conn_mgr, service=service, settings=settings)

        # Injected persistent failure
        consumer.mapper.process_envelope = MagicMock(side_effect=RuntimeError("Permanent unrecoverable logic bug"))

        await consumer.start()
        try:
            event_id = str(uuid.uuid4())
            exhausted_event = {
                "eventId": event_id,
                "eventType": "iot.command.failed",
                "eventVersion": "1.0",
                "occurredAt": "2026-10-28T16:50:00.000Z",
                "producer": "iot-service",
                "payload": {"farmId": "FARM-LIVE-1", "deviceId": "DEV-01", "commandId": "CMD-EXH", "action": "FAN", "failureReason": "test"},
            }

            # Deliver with x-retry-count already at max_retries (2)
            await publish_raw_amqp(
                routing_key="iot.command.failed",
                payload_dict=exhausted_event,
                headers={"x-retry-count": 2},
            )

            # Wait for consumer to route to DLX
            for _ in range(50):
                if consumer.dead_lettered_count > 0:
                    break
                await asyncio.sleep(0.1)

            assert consumer.dead_lettered_count == 1
            assert len(alert_repo.list_alerts()) == 0

            # Verify message exists in real DLQ
            dlq_msgs = declarator.get_messages(QUEUE_DLQ, count=1, ackmode="ack_requeue_false")
            assert len(dlq_msgs) == 1, f"Expected message in {QUEUE_DLQ}, found {len(dlq_msgs)}"
            dlq_body = json.loads(dlq_msgs[0].get("payload", "{}"))
            assert dlq_body.get("eventId") == event_id
            dlq_props = dlq_msgs[0].get("properties", {})
            dlq_headers = dlq_props.get("headers", {})
            assert dlq_headers.get("x-dead-letter-reason") == "retry_exhausted"
            assert dlq_headers.get("x-retry-count") == 2
        finally:
            await consumer.stop()

    @pytest.mark.anyio
    async def test_live_matrix_g_and_h_malformed_event_dlq_and_valid_resilience(self, live_env) -> None:
        """Matrix G & H: Malformed event routes straight to DLQ (0 retries); subsequent valid event succeeds."""
        drain_all_queues()
        service, alert_repo, _, _ = live_env
        declarator = get_declarator()

        settings = RabbitMQSettings(
            host="127.0.0.1",
            port=5672,
            user="swiftlet",
            password="swiftlet123",
            vhost="/",
            exchange=EXCHANGE_EVENTS,
            queue_name=QUEUE_NOTIFICATION,
            prefetch_count=10,
            enabled=True,
        )
        conn_mgr = RabbitMQConnectionManager(settings=settings)
        consumer = RabbitMQAlertConsumer(connection_manager=conn_mgr, service=service, settings=settings)

        await consumer.start()
        try:
            # 1. Publish malformed message (missing mandatory eventId & occurredAt)
            bad_message = {
                "eventType": "iot.environment.high_temperature.started",
                "producer": "iot-service",
                "payload": {"farmId": "FARM-LIVE-1"},
            }
            await publish_raw_amqp(routing_key="iot.environment.high_temperature.started", payload_dict=bad_message)

            # Wait for message to be rejected requeue=False and dead-lettered to DLQ
            for _ in range(50):
                dlq_info = declarator.get_queue_info(QUEUE_DLQ)
                if dlq_info.get("messages", 0) > 0:
                    break
                await asyncio.sleep(0.1)

            dlq_msgs = declarator.get_messages(QUEUE_DLQ, count=1, ackmode="ack_requeue_false")
            assert len(dlq_msgs) == 1, f"Expected malformed message in {QUEUE_DLQ}, found {len(dlq_msgs)}"
            dlq_body = json.loads(dlq_msgs[0].get("payload", "{}"))
            assert dlq_body.get("eventType") == "iot.environment.high_temperature.started"

            # 2. Consumer remains healthy (Matrix H): valid event processes immediately
            valid_event = {
                "eventId": str(uuid.uuid4()),
                "eventType": "iot.command.failed",
                "eventVersion": "1.0",
                "occurredAt": "2026-10-28T16:55:00.000Z",
                "producer": "iot-service",
                "payload": {
                    "farmId": "FARM-LIVE-1",
                    "deviceId": "DEV-CTRL-01",
                    "commandId": "CMD-001",
                    "action": "SET_HUMIDIFIER",
                    "failureReason": "relay_hardware_error",
                },
            }
            await publish_raw_amqp(routing_key="iot.command.failed", payload_dict=valid_event)

            for _ in range(50):
                if len(alert_repo.list_alerts()) > 0:
                    break
                await asyncio.sleep(0.1)

            alerts = alert_repo.list_alerts()
            assert len(alerts) == 1
            assert alerts[0].event_type == AlertEventType.COMMAND_FAILED
            assert alerts[0].status == AlertStatus.OPEN
        finally:
            await consumer.stop()

    @pytest.mark.anyio
    async def test_live_matrix_i_broker_restart_resilience(self, live_env) -> None:
        """Matrix I: RabbitMQ broker restart -> connection recovers robustly and processes post-restart events."""
        drain_all_queues()
        service, alert_repo, _, _ = live_env

        settings = RabbitMQSettings(
            host="127.0.0.1",
            port=5672,
            user="swiftlet",
            password="swiftlet123",
            vhost="/",
            exchange=EXCHANGE_EVENTS,
            queue_name=QUEUE_NOTIFICATION,
            prefetch_count=10,
            enabled=True,
        )
        conn_mgr = RabbitMQConnectionManager(settings=settings)
        consumer = RabbitMQAlertConsumer(connection_manager=conn_mgr, service=service)

        await consumer.start()
        try:
            assert consumer.is_running

            # Restart RabbitMQ broker container
            res = subprocess.run(
                ["docker", "restart", "swiftletcare-rabbitmq"],
                capture_output=True,
                text=True,
                check=False,
            )
            assert res.returncode == 0

            # Wait for broker and management API to become ready
            declarator = get_declarator()
            for _ in range(60):
                if rabbitmq_available():
                    try:
                        declarator.get_queue_info(QUEUE_NOTIFICATION)
                        break
                    except Exception:
                        pass
                await asyncio.sleep(0.5)

            # Wait for aio-pika robust connection to recover
            await asyncio.sleep(2.0)

            post_restart_event = {
                "eventId": str(uuid.uuid4()),
                "eventType": "iot.environment.low_humidity.started",
                "eventVersion": "1.0",
                "occurredAt": "2026-10-28T17:00:00.000Z",
                "producer": "iot-service",
                "payload": {
                    "farmId": "FARM-LIVE-1",
                    "zoneId": "ZONE-01",
                    "deviceId": "DEV-HUMID-01",
                    "metric": "humidity",
                    "value": 55.0,
                    "threshold": 70.0,
                    "unit": "%",
                },
            }
            await publish_raw_amqp(routing_key="iot.environment.low_humidity.started", payload_dict=post_restart_event)

            for _ in range(50):
                if len(alert_repo.list_alerts()) > 0:
                    break
                await asyncio.sleep(0.2)

            alerts = alert_repo.list_alerts()
            assert len(alerts) == 1, f"Expected 1 alert post-restart, got {len(alerts)}"
            assert alerts[0].event_type == AlertEventType.LOW_HUMIDITY
            assert alerts[0].status == AlertStatus.OPEN
            assert alerts[0].severity == AlertSeverity.MEDIUM
        finally:
            await consumer.stop()

    @pytest.mark.anyio
    async def test_live_matrix_j_redis_restart_resilience(self, live_env) -> None:
        """Matrix J: Redis restart -> reconnects and maintains duplicate protection."""
        drain_all_queues()
        service, alert_repo, _, _ = live_env
        redis_store = await get_clean_redis_store()

        settings = RabbitMQSettings(
            host="127.0.0.1",
            port=5672,
            user="swiftlet",
            password="swiftlet123",
            vhost="/",
            exchange=EXCHANGE_EVENTS,
            queue_name=QUEUE_NOTIFICATION,
            prefetch_count=10,
            enabled=True,
        )
        conn_mgr = RabbitMQConnectionManager(settings=settings)
        consumer = RabbitMQAlertConsumer(connection_manager=conn_mgr, service=service, idempotency_store=redis_store)

        await consumer.start()
        try:
            event_id = str(uuid.uuid4())
            event = {
                "eventId": event_id,
                "eventType": "iot.device.online",
                "eventVersion": "1.0",
                "occurredAt": "2026-10-28T17:05:00.000Z",
                "producer": "iot-service",
                "payload": {"farmId": "FARM-LIVE-1", "deviceId": "NODE-REDIS-01"},
            }

            # 1. Process event before restart
            await publish_raw_amqp(routing_key="iot.device.online", payload_dict=event)
            await asyncio.sleep(0.5)

            # 2. Restart Redis container
            res = subprocess.run(
                ["docker", "restart", "swiftletcare-redis"],
                capture_output=True,
                text=True,
                check=False,
            )
            assert res.returncode == 0

            # Wait for Redis to be reachable again
            for _ in range(30):
                if redis_available():
                    break
                await asyncio.sleep(0.2)
            await asyncio.sleep(0.5)

            # 3. Publish identical eventId post-restart
            await publish_raw_amqp(routing_key="iot.device.online", payload_dict=event)
            await asyncio.sleep(0.5)

            # Duplicate detected safely post-restart
            assert consumer.duplicate_count == 1
        finally:
            await consumer.stop()
