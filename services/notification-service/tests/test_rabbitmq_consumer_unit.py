"""Unit tests for Notification Service RabbitMQ Consumer Adapter (CP7.4 Tasks 26-36)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from app.dependencies import get_alert_repo, get_notification_service, init_app_state
from app.domain.enums import AlertEventType, AlertSeverity, AlertStatus, DevicePlatform
from app.infrastructure.rabbitmq.config import RabbitMQSettings, RedisSettings
from app.infrastructure.rabbitmq.consumer import RabbitMQAlertConsumer
from app.infrastructure.rabbitmq.envelope import (
    CanonicalEnvelope,
    PermanentEnvelopeError,
    ProducerMismatchError,
    UnsupportedVersionError,
)
from app.infrastructure.rabbitmq.idempotency import (
    InMemoryIdempotencyStore,
    RedisIdempotencyStore,
)
from app.infrastructure.rabbitmq.mapper import EventMapper
from app.ports.recipient_resolver import RecipientInfo
from app.repositories.in_memory_alert_repo import InMemoryAlertRepository
from app.repositories.in_memory_notification_repo import InMemoryNotificationRepository
from app.repositories.in_memory_user_device_repo import InMemoryUserDeviceRepository
from app.schemas.canonical import UserDevice
from app.services.in_memory_recipient_resolver import InMemoryRecipientResolver
from app.services.mock_fcm_provider import MockFCMProvider


@pytest.fixture(autouse=True)
def setup_test_env():
    """Initializes clean in-memory app state for each unit test."""
    alert_repo = InMemoryAlertRepository()
    notif_repo = InMemoryNotificationRepository()
    user_device_repo = InMemoryUserDeviceRepository()
    user_device_repo.register_device(
        UserDevice(
            device_id="dev_01",
            user_id="user_admin",
            fcm_token="token_admin",
            platform=DevicePlatform.ANDROID,
            is_enabled=True,
        )
    )
    resolver = InMemoryRecipientResolver()
    resolver.register_recipient(
        "FARM-01",
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


def _make_mock_message(body_dict: dict, routing_key: str = "") -> AbstractIncomingMessage:
    msg = MagicMock(spec=AbstractIncomingMessage)
    msg.body = json.dumps(body_dict).encode("utf-8")
    msg.routing_key = routing_key or body_dict.get("eventType", "")
    msg.headers = {}
    msg.ack = AsyncMock()
    msg.reject = AsyncMock()
    msg.nack = AsyncMock()
    return msg


def _make_canonical_event(
    event_type: str,
    payload: dict,
    producer: str = "iot-service",
    event_id: str | None = None,
    event_version: str = "1.0",
) -> dict:
    return {
        "eventId": event_id or str(uuid.uuid4()),
        "eventType": event_type,
        "eventVersion": event_version,
        "occurredAt": "2026-10-28T16:00:00.000Z",
        "producer": producer,
        "correlationId": None,
        "payload": payload,
    }


class TestUnitEnvironmentMapping:
    """Tasks 26 & 27: Environment Started and Recovered."""

    @pytest.mark.anyio
    async def test_high_temp_started_creates_alert_and_acks(self, setup_test_env) -> None:
        service, alert_repo, notif_repo, fcm_mock = setup_test_env
        idempotency_store = InMemoryIdempotencyStore()
        consumer = RabbitMQAlertConsumer(service=service, idempotency_store=idempotency_store)

        event_body = _make_canonical_event(
            event_type="iot.environment.high_temperature.started",
            payload={
                "farmId": "FARM-01",
                "zoneId": "ZONE-01",
                "deviceId": "DEV-01",
                "metric": "temperature",
                "value": 33.5,
                "threshold": 31.0,
                "unit": "°C",
            },
        )
        msg = _make_mock_message(event_body)

        await consumer._handle_message(msg)

        # 1. ACK after successful processing
        msg.ack.assert_awaited_once()
        msg.reject.assert_not_awaited()

        # 2. Alert created with status OPEN and severity HIGH
        alerts = alert_repo.list_alerts()
        assert len(alerts) == 1
        a = alerts[0]
        assert a.event_type == AlertEventType.HIGH_TEMPERATURE
        assert a.status == AlertStatus.OPEN
        assert a.severity == AlertSeverity.HIGH
        assert a.device_id == "DEV-01"
        assert a.occurrence_count == 1

        # 3. Notification created and dispatched to FCM
        notifs = notif_repo.list_by_user("user_admin")
        assert len(notifs) >= 1
        assert len(fcm_mock.sent_messages) >= 1

    @pytest.mark.anyio
    async def test_high_temp_recovery_resolves_same_alert(self, setup_test_env) -> None:
        service, alert_repo, _, _ = setup_test_env
        consumer = RabbitMQAlertConsumer(service=service)

        # 1. Started event
        start_body = _make_canonical_event(
            event_type="iot.environment.high_temperature.started",
            payload={
                "farmId": "FARM-01",
                "zoneId": "ZONE-01",
                "deviceId": "DEV-01",
                "metric": "temperature",
                "value": 34.0,
                "threshold": 31.0,
                "unit": "°C",
            },
        )
        await consumer._handle_message(_make_mock_message(start_body))

        alerts = alert_repo.list_alerts()
        assert len(alerts) == 1
        assert alerts[0].status == AlertStatus.OPEN

        # 2. Recovery event
        recovery_body = _make_canonical_event(
            event_type="iot.environment.high_temperature.recovered",
            payload={
                "farmId": "FARM-01",
                "zoneId": "ZONE-01",
                "deviceId": "DEV-01",
                "metric": "temperature",
                "value": 30.0,
                "threshold": 30.5,
                "unit": "°C",
            },
        )
        msg_rec = _make_mock_message(recovery_body)
        await consumer._handle_message(msg_rec)

        msg_rec.ack.assert_awaited_once()

        # Must resolve existing alert without creating a second one
        alerts = alert_repo.list_alerts()
        assert len(alerts) == 1
        assert alerts[0].status == AlertStatus.RESOLVED


class TestUnitAudioAndDeviceMapping:
    """Tasks 28 & 29: Audio Fault and Device Presence."""

    @pytest.mark.anyio
    async def test_audio_fault_start_and_recovery(self, setup_test_env) -> None:
        service, alert_repo, _, _ = setup_test_env
        consumer = RabbitMQAlertConsumer(service=service)

        # Fault started
        fault_body = _make_canonical_event(
            event_type="iot.audio.fault.started",
            payload={"farmId": "FARM-01", "zoneId": "ZONE-01", "deviceId": "DEV-01", "audioHealthy": False, "audioRms": 5.0},
        )
        await consumer._handle_message(_make_mock_message(fault_body))
        assert len(alert_repo.list_alerts()) == 1
        assert alert_repo.list_alerts()[0].event_type == AlertEventType.AUDIO_FAULT
        assert alert_repo.list_alerts()[0].status == AlertStatus.OPEN

        # Fault recovered
        rec_body = _make_canonical_event(
            event_type="iot.audio.fault.recovered",
            payload={"farmId": "FARM-01", "zoneId": "ZONE-01", "deviceId": "DEV-01", "audioHealthy": True, "audioRms": 25.0},
        )
        await consumer._handle_message(_make_mock_message(rec_body))
        assert len(alert_repo.list_alerts()) == 1
        assert alert_repo.list_alerts()[0].status == AlertStatus.RESOLVED

    @pytest.mark.anyio
    async def test_device_offline_and_online_recovery(self, setup_test_env) -> None:
        service, alert_repo, _, _ = setup_test_env
        consumer = RabbitMQAlertConsumer(service=service)

        # Offline
        offline_body = _make_canonical_event(
            event_type="iot.device.offline",
            payload={"farmId": "FARM-01", "zoneId": "ZONE-01", "deviceId": "DEV-NODE-99", "status": "OFFLINE"},
        )
        await consumer._handle_message(_make_mock_message(offline_body))
        assert len(alert_repo.list_alerts()) == 1
        assert alert_repo.list_alerts()[0].event_type == AlertEventType.DEVICE_OFFLINE
        assert alert_repo.list_alerts()[0].status == AlertStatus.OPEN

        # Online recovery (must NOT create a DEVICE_ONLINE alert)
        online_body = _make_canonical_event(
            event_type="iot.device.online",
            payload={"farmId": "FARM-01", "zoneId": "ZONE-01", "deviceId": "DEV-NODE-99", "status": "ONLINE"},
        )
        await consumer._handle_message(_make_mock_message(online_body))
        assert len(alert_repo.list_alerts()) == 1
        assert alert_repo.list_alerts()[0].status == AlertStatus.RESOLVED


class TestUnitPredatorAndCommandMapping:
    """Tasks 30 & 31: AI Predator and IoT Command Failed."""

    @pytest.mark.anyio
    async def test_ai_predator_detected_mapping_and_metadata(self, setup_test_env) -> None:
        service, alert_repo, _, _ = setup_test_env
        consumer = RabbitMQAlertConsumer(service=service)

        predator_body = _make_canonical_event(
            event_type="ai.predator.detected",
            producer="ai-service",
            payload={
                "farmId": "FARM-01",
                "zoneId": "ZONE-NORTH",
                "cameraId": "CAM-PRED-01",
                "predatorClass": "snake",
                "confidence": 0.932,
                "snapshotRef": "snake_cam01.jpg",
                "frameWidth": 1920,
                "frameHeight": 1080,
                "bbox": {"x": 50.0, "y": 60.0, "width": 80.0, "height": 40.0},
            },
        )
        msg = _make_mock_message(predator_body)
        await consumer._handle_message(msg)

        msg.ack.assert_awaited_once()
        alerts = alert_repo.list_alerts()
        assert len(alerts) == 1
        a = alerts[0]
        assert a.event_type == AlertEventType.PREDATOR_DETECTED
        assert a.severity == AlertSeverity.CRITICAL
        assert a.camera_id == "CAM-PRED-01"
        assert a.status == AlertStatus.OPEN
        assert a.snapshot_url == "snake_cam01.jpg"

    @pytest.mark.anyio
    async def test_iot_command_failed_mapping(self, setup_test_env) -> None:
        service, alert_repo, _, _ = setup_test_env
        consumer = RabbitMQAlertConsumer(service=service)

        cmd_body = _make_canonical_event(
            event_type="iot.command.failed",
            payload={
                "farmId": "FARM-01",
                "zoneId": "ZONE-01",
                "deviceId": "DEV-01",
                "commandId": "cmd-12345",
                "action": "SET_RELAY",
                "failureReason": "Hardware timeout",
            },
        )
        msg = _make_mock_message(cmd_body)
        await consumer._handle_message(msg)

        msg.ack.assert_awaited_once()
        alerts = alert_repo.list_alerts()
        assert len(alerts) == 1
        a = alerts[0]
        assert a.event_type == AlertEventType.COMMAND_FAILED
        assert a.status == AlertStatus.OPEN


class TestUnitAlertDedupVsMessageIdempotency:
    """Tasks 32 & 33: Dedup occurrence increment vs exact redelivery idempotency."""

    @pytest.mark.anyio
    async def test_alert_dedup_increments_occurrence_for_different_event_ids(self, setup_test_env) -> None:
        """Task 32: Two genuinely different eventIds for the same active condition."""
        service, alert_repo, _, _ = setup_test_env
        consumer = RabbitMQAlertConsumer(service=service)

        # Event A
        evt_a = _make_canonical_event(
            event_id=str(uuid.uuid4()),
            event_type="iot.environment.high_temperature.started",
            payload={"farmId": "FARM-01", "deviceId": "DEV-01", "metric": "temperature", "value": 33.0, "threshold": 31.0, "unit": "°C"},
        )
        await consumer._handle_message(_make_mock_message(evt_a))

        assert len(alert_repo.list_alerts()) == 1
        assert alert_repo.list_alerts()[0].occurrence_count == 1

        # Event B (new eventId, same active condition)
        evt_b = _make_canonical_event(
            event_id=str(uuid.uuid4()),
            event_type="iot.environment.high_temperature.started",
            payload={"farmId": "FARM-01", "deviceId": "DEV-01", "metric": "temperature", "value": 34.0, "threshold": 31.0, "unit": "°C"},
        )
        await consumer._handle_message(_make_mock_message(evt_b))

        # Alert dedup applies: still 1 alert, but occurrence_count becomes 2
        assert len(alert_repo.list_alerts()) == 1
        assert alert_repo.list_alerts()[0].occurrence_count == 2

    @pytest.mark.anyio
    async def test_message_idempotency_discards_exact_same_event_id(self, setup_test_env) -> None:
        """Task 33: Exactly same eventId redelivered MUST NOT increment occurrenceCount or send duplicate notifications."""
        service, alert_repo, notif_repo, fcm_mock = setup_test_env
        idempotency_store = InMemoryIdempotencyStore()
        consumer = RabbitMQAlertConsumer(service=service, idempotency_store=idempotency_store)

        fixed_id = str(uuid.uuid4())
        body = _make_canonical_event(
            event_id=fixed_id,
            event_type="iot.environment.high_temperature.started",
            payload={"farmId": "FARM-01", "deviceId": "DEV-01", "metric": "temperature", "value": 33.0, "threshold": 31.0, "unit": "°C"},
        )

        # Delivery #1
        msg1 = _make_mock_message(body)
        await consumer._handle_message(msg1)
        msg1.ack.assert_awaited_once()

        assert alert_repo.list_alerts()[0].occurrence_count == 1
        notif_count_first = len(notif_repo.list_by_user("user_admin"))
        fcm_count_first = len(fcm_mock.sent_messages)

        # Delivery #2 (redelivery of identical eventId)
        msg2 = _make_mock_message(body)
        await consumer._handle_message(msg2)
        msg2.ack.assert_awaited_once()

        # Idempotency guarantees:
        assert consumer.duplicate_count == 1
        assert alert_repo.list_alerts()[0].occurrence_count == 1  # Unchanged!
        assert len(notif_repo.list_by_user("user_admin")) == notif_count_first  # No new notification!
        assert len(fcm_mock.sent_messages) == fcm_count_first  # No new FCM push!


class TestUnitEnvelopeValidationAndProducerMismatch:
    """Tasks 34 & 35: Rejection of invalid envelopes and mismatched producers."""

    @pytest.mark.anyio
    async def test_invalid_envelope_rejected_with_no_requeue(self, setup_test_env) -> None:
        """Task 34: Missing fields, bad version, or bad JSON rejected with requeue=False (routes to DLQ)."""
        service, alert_repo, _, _ = setup_test_env
        consumer = RabbitMQAlertConsumer(service=service)

        # 1. Missing eventId
        bad_msg1 = _make_mock_message({"eventType": "iot.device.offline", "eventVersion": "1.0", "producer": "iot-service", "payload": {}})
        await consumer._handle_message(bad_msg1)
        bad_msg1.reject.assert_awaited_once_with(requeue=False)

        # 2. Unsupported version
        bad_msg2 = _make_mock_message({
            "eventId": str(uuid.uuid4()),
            "eventType": "iot.device.offline",
            "eventVersion": "2.0",  # Unsupported
            "occurredAt": "2026-10-28T16:00:00.000Z",
            "producer": "iot-service",
            "payload": {},
        })
        await consumer._handle_message(bad_msg2)
        bad_msg2.reject.assert_awaited_once_with(requeue=False)

        # 3. Malformed JSON bytes
        bad_msg3 = MagicMock(spec=AbstractIncomingMessage)
        bad_msg3.body = b"NOT_VALID_JSON{{"
        bad_msg3.reject = AsyncMock()
        await consumer._handle_message(bad_msg3)
        bad_msg3.reject.assert_awaited_once_with(requeue=False)

        assert len(alert_repo.list_alerts()) == 0

    @pytest.mark.anyio
    async def test_producer_mismatch_rejected(self, setup_test_env) -> None:
        """Task 35: producer='ai-service' with 'iot.device.offline' rejected as permanent mismatch."""
        service, alert_repo, _, _ = setup_test_env
        consumer = RabbitMQAlertConsumer(service=service)

        mismatched_msg = _make_mock_message({
            "eventId": str(uuid.uuid4()),
            "eventType": "iot.device.offline",
            "eventVersion": "1.0",
            "occurredAt": "2026-10-28T16:00:00.000Z",
            "producer": "ai-service",  # AI cannot emit IoT events!
            "payload": {"farmId": "FARM-01", "deviceId": "DEV-01"},
        })
        await consumer._handle_message(mismatched_msg)

        mismatched_msg.reject.assert_awaited_once_with(requeue=False)
        assert len(alert_repo.list_alerts()) == 0
        assert consumer.rejected_count == 1


class TestRabbitMQDisabledMode:
    """Task 36: When RABBITMQ_ENABLED=false, service starts and functions without broker."""

    def test_rabbitmq_disabled_settings(self) -> None:
        cfg = RabbitMQSettings.from_env()
        # Default is False
        assert cfg.enabled is False

    @pytest.mark.anyio
    async def test_disabled_consumer_does_not_connect(self, setup_test_env) -> None:
        service, _, _, _ = setup_test_env
        cfg = RabbitMQSettings(enabled=False)
        consumer = RabbitMQAlertConsumer(service=service, settings=cfg)

        assert consumer.is_running is False
        # Stop should execute smoothly
        await consumer.stop()


class TestUnitBoundedRetryAndDLQ:
    """CP7.5 Unit tests for Bounded Retry and Dead Letter Queue."""

    @pytest.mark.anyio
    async def test_temporary_failure_routes_to_retry_queue_and_acks_original(self, setup_test_env) -> None:
        """CP7.5 Section 5, 6, 8, 9: Transient error triggers delayed retry publish with publisher confirm before ACK."""
        service, _, _, _ = setup_test_env
        consumer = RabbitMQAlertConsumer(service=service)

        # Mock mapper to raise a temporary processing exception
        consumer.mapper.process_envelope = MagicMock(side_effect=RuntimeError("Database lock timeout"))
        consumer._publish_to_exchange = AsyncMock()

        event_body = _make_canonical_event(
            event_type="iot.environment.high_temperature.started",
            payload={"farmId": "FARM-01", "deviceId": "DEV-01", "metric": "temperature", "value": 35.0, "threshold": 31.0, "unit": "°C"},
        )
        msg = _make_mock_message(event_body)
        msg.headers = {"x-retry-count": 0}

        await consumer._handle_message(msg)

        # 1. Published to retry exchange with incremented retry count
        consumer._publish_to_exchange.assert_awaited_once()
        call_kwargs = consumer._publish_to_exchange.call_args.kwargs
        assert call_kwargs["exchange_name"] == "swiftlet.notification.retry"
        assert call_kwargs["routing_key"] == "notification.alert-events.v1.retry"
        assert call_kwargs["headers"]["x-retry-count"] == 1
        assert "Database lock timeout" in call_kwargs["headers"]["x-error-message"]

        # 2. Original message acknowledged strictly after publish (publish-then-ack safety)
        msg.ack.assert_awaited_once()
        msg.reject.assert_not_awaited()
        assert consumer.retry_scheduled_count == 1

    @pytest.mark.anyio
    async def test_retry_exhaustion_routes_to_dlx_and_acks_original(self, setup_test_env) -> None:
        """CP7.5 Section 8: When retryCount >= MAX_RETRIES, message routes to DLX."""
        service, _, _, _ = setup_test_env
        cfg = RabbitMQSettings(max_retries=3)
        consumer = RabbitMQAlertConsumer(service=service, settings=cfg)

        consumer.mapper.process_envelope = MagicMock(side_effect=RuntimeError("Persistent downstream error"))
        consumer._publish_to_exchange = AsyncMock()

        event_body = _make_canonical_event(
            event_type="iot.environment.high_temperature.started",
            payload={"farmId": "FARM-01", "deviceId": "DEV-01", "metric": "temperature", "value": 35.0, "threshold": 31.0, "unit": "°C"},
        )
        msg = _make_mock_message(event_body)
        # Current attempt is already at max_retries (3)
        msg.headers = {"x-retry-count": 3}

        await consumer._handle_message(msg)

        # 1. Published to DLX with exhaustion reason
        consumer._publish_to_exchange.assert_awaited_once()
        call_kwargs = consumer._publish_to_exchange.call_args.kwargs
        assert call_kwargs["exchange_name"] == "swiftlet.notification.dlx"
        assert call_kwargs["routing_key"] == "notification.alert-events.v1.dlq"
        assert call_kwargs["headers"]["x-retry-count"] == 3
        assert call_kwargs["headers"]["x-dead-letter-reason"] == "retry_exhausted"

        # 2. Original message acknowledged safely
        msg.ack.assert_awaited_once()
        assert consumer.dead_lettered_count == 1

    @pytest.mark.anyio
    async def test_publish_failure_does_not_ack_original(self, setup_test_env) -> None:
        """CP7.5 Section 9: If publish to retry fails, consumer must NOT ACK original message."""
        service, _, _, _ = setup_test_env
        consumer = RabbitMQAlertConsumer(service=service)

        consumer.mapper.process_envelope = MagicMock(side_effect=RuntimeError("Downstream error"))
        # Broker publisher confirm throws an error
        consumer._publish_to_exchange = AsyncMock(side_effect=aio_pika.exceptions.AMQPError("Broker confirm timeout"))

        event_body = _make_canonical_event(
            event_type="iot.environment.high_temperature.started",
            payload={"farmId": "FARM-01", "deviceId": "DEV-01", "metric": "temperature", "value": 35.0, "threshold": 31.0, "unit": "°C"},
        )
        msg = _make_mock_message(event_body)
        msg.headers = {"x-retry-count": 0}

        await consumer._handle_message(msg)

        # Crucial invariant: msg.ack was NOT called because republish failed
        msg.ack.assert_not_awaited()


class TestUnitDurableIdempotency:
    """CP7.5 Unit tests for Durable Idempotency (Atomic claims, lease release, Redis/InMemory)."""

    def test_in_memory_atomic_claim_and_done(self) -> None:
        store = InMemoryIdempotencyStore()
        eid = "evt_claim_01"

        # First claim succeeds
        assert store.try_claim(eid) is True
        # Second claim fails (duplicate in flight)
        assert store.try_claim(eid) is False

        # Mark done
        store.mark_done(eid)
        assert store.has_processed(eid) is True
        # Third claim still fails (duplicate done)
        assert store.try_claim(eid) is False

    def test_in_memory_release_claim(self) -> None:
        store = InMemoryIdempotencyStore()
        eid = "evt_claim_02"

        assert store.try_claim(eid) is True
        # Failure occurs -> release claim
        store.release_claim(eid)

        # Retry delivery can successfully re-acquire lease
        assert store.try_claim(eid) is True

    @pytest.mark.anyio
    async def test_redis_idempotency_store_atomic_operations(self) -> None:
        """Verifies Redis atomic SET NX EX, mark_done, and Lua script release."""
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.eval = AsyncMock(return_value=1)
        mock_redis.get = AsyncMock(return_value=b"DONE")

        store = RedisIdempotencyStore(
            redis_client=mock_redis,
            idempotency_ttl_seconds=86400,
            processing_claim_ttl_seconds=60,
        )
        eid = "evt_redis_01"

        # 1. try_claim_async executes SET NX EX
        claimed = await store.try_claim_async(eid)
        assert claimed is True
        mock_redis.set.assert_awaited_once_with(
            "swiftlet:idempotency:evt_redis_01",
            "PROCESSING",
            nx=True,
            ex=60,
        )

        # 2. mark_done_async executes SET EX
        mock_redis.set.reset_mock()
        await store.mark_done_async(eid)
        mock_redis.set.assert_awaited_once_with(
            "swiftlet:idempotency:evt_redis_01",
            "DONE",
            ex=86400,
        )

        # 3. release_claim_async executes atomic Lua script
        await store.release_claim_async(eid)
        mock_redis.eval.assert_awaited_once()

        # 4. has_processed_async checks key presence
        assert await store.has_processed_async(eid) is True

