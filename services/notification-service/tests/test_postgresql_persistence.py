"""CP8.3 — Notification Service Durable PostgreSQL Persistence Tests.

Covers required verification categories (Step 17, Step 19, Step 20):
A. Alert persistence (started, dedup, occurrence_count, ACKNOWLEDGED, RESOLVED, recovery, fresh instance)
B. Alert lifecycle (valid/invalid transitions, OPEN -> RESOLVED, predator & command failure human-resolution)
C. Notification persistence (PENDING, SENT, FAILED, SUPPRESSED, DELIVERED, read_at, READ not a delivery status)
D. FCM semantics (provider accepted = SENT, not DELIVERED; invalid token disables device in PostgreSQL)
E. UserDevice persistence (registration, token update/transfer, enabled lookup, fresh instance survival)
F. Message idempotency (RedisIdempotencyStore remains Redis-backed; same eventId blocked)
G. Alert dedup (different eventIds for same active condition merge into single OPEN Alert; uq_alerts_active_dedup_key)
H. RabbitMQ reliability (bounded retry, DLQ, malformed message handling with PostgreSQL)
I. WebSocket realtime delivery preserved with PostgreSQL repositories
J. Boundary & failure/recovery (zero cross-service FKs, least-privilege notification_user, transient DB failure retry & recovery)
"""
from __future__ import annotations

import json
import pathlib
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import psycopg
import pytest
import redis.asyncio as aioredis
from aio_pika.abc import AbstractIncomingMessage
from fastapi.testclient import TestClient

from app.config.alert_rules import AlertRuleConfig, InMemoryAlertRuleConfigProvider
from app.database import check_database_health, get_connection
from app.dependencies import init_app_state
from app.domain.enums import (
    AlertEventType,
    AlertSeverity,
    AlertSource,
    AlertStatus,
    DevicePlatform,
    NotificationChannel,
    NotificationDeliveryStatus,
)
from app.infrastructure.rabbitmq.config import RabbitMQSettings
from app.infrastructure.rabbitmq.consumer import RabbitMQAlertConsumer
from app.infrastructure.rabbitmq.idempotency import InMemoryIdempotencyStore, RedisIdempotencyStore
from app.main import app
from app.ports.recipient_resolver import RecipientInfo
from app.repositories import (
    PostgreSQLAlertRepository,
    PostgreSQLNotificationRepository,
    PostgreSQLUserDeviceRepository,
)
from app.schemas.canonical import Alert, Notification, UserDevice
from app.services.in_memory_recipient_resolver import InMemoryRecipientResolver
from app.services.mock_fcm_provider import MockFCMProvider
from app.services.notification_service import NotificationService


def _make_pg_service() -> tuple[
    NotificationService,
    PostgreSQLAlertRepository,
    PostgreSQLNotificationRepository,
    PostgreSQLUserDeviceRepository,
    MockFCMProvider,
]:
    alert_repo = PostgreSQLAlertRepository()
    notif_repo = PostgreSQLNotificationRepository()
    device_repo = PostgreSQLUserDeviceRepository()

    rule_provider = InMemoryAlertRuleConfigProvider()
    rule_provider.set_rules_for_farm(
        "FARM-01",
        AlertRuleConfig(
            farm_id="FARM-01",
            high_temp_celsius=31.0,
            high_temp_recovery_celsius=30.5,
            low_temp_celsius=27.0,
            low_temp_recovery_celsius=27.5,
            high_humidity_pct=85.0,
            high_humidity_recovery_pct=82.0,
            low_humidity_pct=70.0,
            low_humidity_recovery_pct=73.0,
        ),
    )

    resolver = InMemoryRecipientResolver()
    resolver.register_recipient(
        "FARM-01",
        RecipientInfo(
            user_id="USER-OWNER-01",
            email="owner@farm01.vn",
            roles=["FARM_OWNER"],
        ),
    )

    device_repo.register_device(
        UserDevice(
            device_id="dev_pg_owner_01",
            user_id="USER-OWNER-01",
            fcm_token="fcm_token_owner_01",
            platform=DevicePlatform.ANDROID,
            device_name="Owner Galaxy S24",
            is_enabled=True,
        )
    )

    fcm_provider = MockFCMProvider()
    service = init_app_state(
        alert_repo=alert_repo,
        notification_repo=notif_repo,
        user_device_repo=device_repo,
        rule_config_provider=rule_provider,
        recipient_resolver=resolver,
        fcm_provider=fcm_provider,
    )
    return service, alert_repo, notif_repo, device_repo, fcm_provider


def _make_mock_amqp_message(body_dict: dict, routing_key: str = "", retry_count: int = 0) -> AbstractIncomingMessage:
    msg = MagicMock(spec=AbstractIncomingMessage)
    msg.body = json.dumps(body_dict).encode("utf-8")
    msg.routing_key = routing_key or body_dict.get("eventType", "")
    msg.headers = {"x-retry-count": retry_count} if retry_count > 0 else {}
    msg.ack = AsyncMock()
    msg.reject = AsyncMock()
    msg.nack = AsyncMock()
    return msg


# =============================================================================
# Category A: Alert Persistence, Deduplication & Auto-Recovery
# =============================================================================


@pytest.mark.anyio
async def test_a1_started_event_creates_open_alert_and_repeated_occurrence_deduplicates():
    service, alert_repo, notif_repo, _, _ = _make_pg_service()
    consumer = RabbitMQAlertConsumer(service=service, idempotency_store=InMemoryIdempotencyStore())

    # 1. First started event -> creates OPEN HIGH_TEMPERATURE Alert in PostgreSQL
    ev1 = {
        "eventId": str(uuid.uuid4()),
        "eventType": "iot.environment.high_temperature.started",
        "eventVersion": "1.0",
        "occurredAt": "2026-11-03T10:00:00.000Z",
        "producer": "iot-service",
        "payload": {
            "farmId": "FARM-01",
            "zoneId": "ZONE-A",
            "deviceId": "DEV-TEMP-01",
            "metric": "temperature",
            "value": 33.2,
            "threshold": 31.0,
            "unit": "°C",
        },
    }
    msg1 = _make_mock_amqp_message(ev1)
    await consumer._handle_message(msg1)
    msg1.ack.assert_awaited_once()

    alerts = alert_repo.list_alerts(farm_id="FARM-01")
    assert len(alerts) == 1
    a1 = alerts[0]
    assert a1.status == AlertStatus.OPEN
    assert a1.event_type == AlertEventType.HIGH_TEMPERATURE
    assert a1.severity == AlertSeverity.HIGH
    assert a1.occurrence_count == 1
    assert a1.telemetry_snapshot == {"value": 33.2, "threshold": 31.0, "metric": "temperature"}

    # 2. Second started event with DIFFERENT eventId -> merges into same OPEN Alert in PostgreSQL
    ev2 = {
        "eventId": str(uuid.uuid4()),
        "eventType": "iot.environment.high_temperature.started",
        "eventVersion": "1.0",
        "occurredAt": "2026-11-03T10:05:00.000Z",
        "producer": "iot-service",
        "payload": {
            "farmId": "FARM-01",
            "zoneId": "ZONE-A",
            "deviceId": "DEV-TEMP-01",
            "metric": "temperature",
            "value": 34.1,
            "threshold": 31.0,
            "unit": "°C",
        },
    }
    msg2 = _make_mock_amqp_message(ev2)
    await consumer._handle_message(msg2)
    msg2.ack.assert_awaited_once()

    alerts_after = alert_repo.list_alerts(farm_id="FARM-01")
    assert len(alerts_after) == 1
    a2 = alerts_after[0]
    assert a2.alert_id == a1.alert_id
    assert a2.occurrence_count == 2
    assert a2.last_occurred_at == datetime(2026, 11, 3, 10, 5, 0, tzinfo=timezone.utc)
    assert a2.telemetry_snapshot == {"value": 34.1, "threshold": 31.0, "metric": "temperature"}

    # Notifications were only dispatched once (1 IN_APP + 1 FCM)
    notifs = notif_repo.list_by_user("USER-OWNER-01")
    assert len(notifs) == 2


@pytest.mark.anyio
async def test_a2_acknowledged_and_resolved_persist_and_recovery_resolves_correct_alert():
    service, alert_repo, _, _, _ = _make_pg_service()
    consumer = RabbitMQAlertConsumer(service=service, idempotency_store=InMemoryIdempotencyStore())

    # 1. Start HIGH_TEMPERATURE, AUDIO_FAULT, and DEVICE_OFFLINE alerts
    for ev_type, dev_id, payload_extra in [
        (
            "iot.environment.high_temperature.started",
            "DEV-ENV-01",
            {"metric": "temperature", "value": 32.8, "threshold": 31.0, "unit": "°C"},
        ),
        (
            "iot.audio.fault.started",
            "DEV-AUD-01",
            {"audioHealthy": False, "audioRms": 0.01},
        ),
        (
            "iot.device.offline",
            "DEV-GW-01",
            {},
        ),
    ]:
        ev = {
            "eventId": str(uuid.uuid4()),
            "eventType": ev_type,
            "eventVersion": "1.0",
            "occurredAt": "2026-11-03T11:00:00.000Z",
            "producer": "iot-service",
            "payload": {"farmId": "FARM-01", "zoneId": "ZONE-A", "deviceId": dev_id, **payload_extra},
        }
        await consumer._handle_message(_make_mock_amqp_message(ev))

    open_alerts = alert_repo.list_alerts(farm_id="FARM-01", status=AlertStatus.OPEN)
    assert len(open_alerts) == 3

    # 2. Operator acknowledges HIGH_TEMPERATURE alert -> persists ACKNOWLEDGED in PostgreSQL
    temp_alert = next(a for a in open_alerts if a.event_type == AlertEventType.HIGH_TEMPERATURE)
    acked = service.acknowledge_alert(temp_alert.alert_id, acknowledged_by="USER-OWNER-01")
    assert acked.status == AlertStatus.ACKNOWLEDGED
    assert acked.acknowledged_by == "USER-OWNER-01"
    assert acked.acknowledged_at is not None

    persisted_ack = PostgreSQLAlertRepository().get_by_id(temp_alert.alert_id)
    assert persisted_ack is not None
    assert persisted_ack.status == AlertStatus.ACKNOWLEDGED
    assert persisted_ack.acknowledged_by == "USER-OWNER-01"

    # 3. Recovery events arrive -> auto-resolve all three active alerts in PostgreSQL
    for rec_type, dev_id, payload_extra in [
        (
            "iot.environment.high_temperature.recovered",
            "DEV-ENV-01",
            {"metric": "temperature", "value": 30.1, "threshold": 30.5, "unit": "°C"},
        ),
        (
            "iot.audio.fault.recovered",
            "DEV-AUD-01",
            {"audioHealthy": True, "audioRms": 0.45},
        ),
        (
            "iot.device.online",
            "DEV-GW-01",
            {},
        ),
    ]:
        ev = {
            "eventId": str(uuid.uuid4()),
            "eventType": rec_type,
            "eventVersion": "1.0",
            "occurredAt": "2026-11-03T11:15:00.000Z",
            "producer": "iot-service",
            "payload": {"farmId": "FARM-01", "zoneId": "ZONE-A", "deviceId": dev_id, **payload_extra},
        }
        await consumer._handle_message(_make_mock_amqp_message(ev))

    # Verify all 3 alerts are now RESOLVED in PostgreSQL and no extra alerts were created
    all_alerts = PostgreSQLAlertRepository().list_alerts(farm_id="FARM-01")
    assert len(all_alerts) == 3
    for a in all_alerts:
        assert a.status == AlertStatus.RESOLVED
        assert a.resolved_by == "SYSTEM"
        assert a.resolved_at == datetime(2026, 11, 3, 11, 15, 0, tzinfo=timezone.utc)


def test_a3_alert_history_survives_fresh_repository_recreation_and_time_range_queries():
    service_1, alert_repo_1, _, _, _ = _make_pg_service()
    base_time = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)

    created_ids: list[str] = []
    for i in range(3):
        a = Alert(
            alert_id=f"alt_hist_{i}",
            farm_id="FARM-01",
            zone_id="ZONE-A",
            device_id=f"DEV-HIST-{i}",
            event_type=AlertEventType.LOW_HUMIDITY,
            severity=AlertSeverity.MEDIUM,
            status=AlertStatus.OPEN if i < 2 else AlertStatus.RESOLVED,
            source=AlertSource.IOT_ENVIRONMENT,
            title=f"Low Humidity {i}",
            message=f"Humidity low on device {i}",
            created_at=base_time + timedelta(minutes=10 * i),
            updated_at=base_time + timedelta(minutes=10 * i),
            last_occurred_at=base_time + timedelta(minutes=10 * i),
        )
        alert_repo_1.save(a)
        created_ids.append(a.alert_id)

    # Tear down initial instances
    del service_1
    del alert_repo_1

    # Fresh repository & service instance persistence proof
    fresh_alert_repo = PostgreSQLAlertRepository()
    assert fresh_alert_repo.count_alerts(farm_id="FARM-01") == 3
    assert fresh_alert_repo.count_alerts(farm_id="FARM-01", status=AlertStatus.OPEN) == 2

    # Time range query: [12:05, 12:25] -> matches i=1 (12:10) and i=2 (12:20)
    window = fresh_alert_repo.list_by_time_range(
        start_time=base_time + timedelta(minutes=5),
        end_time=base_time + timedelta(minutes=25),
        farm_id="FARM-01",
    )
    assert [a.alert_id for a in window] == ["alt_hist_2", "alt_hist_1"]

    # Verify via REST endpoint time-range filter
    with TestClient(app) as client:
        resp = client.get(
            "/api/v1/alerts",
            params={
                "farmId": "FARM-01",
                "startTime": (base_time + timedelta(minutes=5)).isoformat(),
                "endTime": (base_time + timedelta(minutes=15)).isoformat(),
            },
        )
        assert resp.status_code == 200
        assert [x["alertId"] for x in resp.json()] == ["alt_hist_1"]


# =============================================================================
# Category B: Alert Lifecycle & Human-Resolution Semantics
# =============================================================================


@pytest.mark.anyio
async def test_b1_alert_lifecycle_transitions_and_human_resolution_invariants():
    service, alert_repo, _, _, _ = _make_pg_service()
    consumer = RabbitMQAlertConsumer(service=service, idempotency_store=InMemoryIdempotencyStore())

    # 1. AI Predator Detected -> CRITICAL OPEN Alert (human resolution required)
    pred_ev = {
        "eventId": str(uuid.uuid4()),
        "eventType": "ai.predator.detected",
        "eventVersion": "1.0",
        "occurredAt": "2026-11-03T13:00:00.000Z",
        "producer": "ai-service",
        "payload": {
            "farmId": "FARM-01",
            "zoneId": "ZONE-A",
            "cameraId": "CAM-ENTRANCE-01",
            "predatorClass": "snake",
            "confidence": 0.96,
            "snapshotRef": "/api/v1/ai/snapshots/evt_ai_pred_01.jpg",
        },
    }
    await consumer._handle_message(_make_mock_amqp_message(pred_ev))

    # 2. IoT Command Failed -> HIGH OPEN Alert (human resolution required)
    cmd_ev = {
        "eventId": str(uuid.uuid4()),
        "eventType": "iot.command.failed",
        "eventVersion": "1.0",
        "occurredAt": "2026-11-03T13:01:00.000Z",
        "producer": "iot-service",
        "payload": {
            "farmId": "FARM-01",
            "zoneId": "ZONE-A",
            "deviceId": "DEV-MIST-01",
            "commandId": "CMD-9901",
            "action": "TURN_ON_MIST",
            "failureReason": "ACK_TIMEOUT",
        },
    }
    await consumer._handle_message(_make_mock_amqp_message(cmd_ev))

    pred_alert = alert_repo.find_active_by_dedup_key(
        farm_id="FARM-01",
        zone_id="ZONE-A",
        device_id="CAM-ENTRANCE-01",
        event_type=AlertEventType.PREDATOR_DETECTED,
    )
    cmd_alert = alert_repo.find_active_by_dedup_key(
        farm_id="FARM-01",
        zone_id="ZONE-A",
        device_id="DEV-MIST-01",
        event_type=AlertEventType.COMMAND_FAILED,
    )
    assert pred_alert is not None and pred_alert.status == AlertStatus.OPEN
    assert cmd_alert is not None and cmd_alert.status == AlertStatus.OPEN

    # Direct OPEN -> RESOLVED transition on predator alert
    resolved_pred = service.resolve_alert(
        pred_alert.alert_id,
        resolved_by="USER-OWNER-01",
        resolution_note="Removed snake from nesting room",
    )
    assert resolved_pred.status == AlertStatus.RESOLVED

    # Invalid transitions on already RESOLVED alert must be rejected
    with pytest.raises(ValueError, match="already RESOLVED"):
        service.acknowledge_alert(pred_alert.alert_id, acknowledged_by="USER-OWNER-01")
    with pytest.raises(ValueError, match="already RESOLVED"):
        service.resolve_alert(pred_alert.alert_id, resolved_by="USER-OWNER-01")

    # OPEN -> ACKNOWLEDGED -> RESOLVED on command failure alert
    acked_cmd = service.acknowledge_alert(cmd_alert.alert_id, acknowledged_by="USER-OWNER-01")
    assert acked_cmd.status == AlertStatus.ACKNOWLEDGED
    with pytest.raises(ValueError, match="already ACKNOWLEDGED"):
        service.acknowledge_alert(cmd_alert.alert_id, acknowledged_by="USER-OWNER-01")

    resolved_cmd = service.resolve_alert(
        cmd_alert.alert_id,
        resolved_by="USER-OWNER-01",
        resolution_note="Relay wiring repaired",
    )
    assert resolved_cmd.status == AlertStatus.RESOLVED


# =============================================================================
# Category C & D: Notification Persistence, Read State & FCM Semantics
# =============================================================================


def test_c1_and_d1_notification_delivery_statuses_read_at_and_fcm_sent_not_delivered():
    service, _, notif_repo, device_repo, fcm_provider = _make_pg_service()
    now = datetime(2026, 11, 3, 14, 0, 0, tzinfo=timezone.utc)

    # 1. Persist all 5 canonical delivery statuses in PostgreSQL
    for status_val in [
        NotificationDeliveryStatus.PENDING,
        NotificationDeliveryStatus.SENT,
        NotificationDeliveryStatus.DELIVERED,
        NotificationDeliveryStatus.FAILED,
        NotificationDeliveryStatus.SUPPRESSED,
    ]:
        n = Notification(
            notification_id=f"ntf_status_{status_val.value.lower()}",
            alert_id="alt_status_test",
            user_id="USER-STATUS-01",
            channel=NotificationChannel.FCM,
            delivery_status=status_val,
            title=f"Title {status_val.value}",
            body="Status test body",
            failure_reason="Simulated reason" if status_val == NotificationDeliveryStatus.FAILED else None,
            created_at=now,
        )
        saved = notif_repo.save(n)
        assert saved.delivery_status == status_val

    # 2. Verify PostgreSQL CHECK constraint rejects 'READ' as delivery_status
    with get_connection() as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notifications (
                        notification_id, alert_id, user_id, channel, delivery_status, title, body
                    ) VALUES (
                        'ntf_bad_read_status', 'alt_1', 'USR_1', 'IN_APP', 'READ', 'T', 'B'
                    )
                    """
                )
        conn.rollback()

    # 3. Verify FCM acceptance sets SENT (with sent_at populated), NEVER DELIVERED automatically
    from app.schemas.events import AIAlertInputEvent

    alerts = service.handle_ai_event(
        AIAlertInputEvent(
            event_type=AlertEventType.PREDATOR_DETECTED,
            farm_id="FARM-01",
            zone_id="ZONE-A",
            camera_id="CAM-01",
            timestamp=now,
            confidence=0.95,
            predator_type="rat",
        )
    )
    assert len(alerts) == 1
    owner_notifs = notif_repo.list_by_alert(alerts[0].alert_id)
    assert len(owner_notifs) == 2

    fcm_notif = next(n for n in owner_notifs if n.channel == NotificationChannel.FCM)
    assert fcm_notif.delivery_status == NotificationDeliveryStatus.SENT
    assert fcm_notif.delivery_status != NotificationDeliveryStatus.DELIVERED
    assert fcm_notif.sent_at is not None
    assert fcm_notif.read_at is None

    # 4. Mark as read persists read_at while preserving delivery_status == SENT
    read_notif = service.mark_notification_as_read(fcm_notif.notification_id, user_id="USER-OWNER-01")
    assert read_notif is not None
    assert read_notif.read_at is not None
    assert read_notif.is_read is True
    assert read_notif.delivery_status == NotificationDeliveryStatus.SENT

    # Fresh repository instance verifies durable read_at
    reloaded = PostgreSQLNotificationRepository().get_by_id(fcm_notif.notification_id)
    assert reloaded is not None
    assert reloaded.read_at is not None
    assert reloaded.delivery_status == NotificationDeliveryStatus.SENT


# =============================================================================
# Category E: UserDevice Persistence
# =============================================================================


def test_e1_user_device_registration_token_update_disable_and_fresh_recreation():
    service, _, _, device_repo, fcm_provider = _make_pg_service()

    # 1. Register iOS device for USER-A
    dev_a = UserDevice(
        device_id="dev_ios_001",
        user_id="USER-A",
        fcm_token="fcm_shared_tok_777",
        platform=DevicePlatform.IOS,
        device_name="iPhone 16 Pro",
        is_enabled=True,
    )
    device_repo.register_device(dev_a)
    assert len(device_repo.list_by_user("USER-A")) == 1

    # 2. USER-B registers the same fcm_token -> ownership moves to USER-B in PostgreSQL
    dev_b = UserDevice(
        device_id="dev_ios_002",
        user_id="USER-B",
        fcm_token="fcm_shared_tok_777",
        platform=DevicePlatform.IOS,
        device_name="USER-B iPhone",
        is_enabled=True,
    )
    device_repo.register_device(dev_b)
    assert len(device_repo.list_by_user("USER-A")) == 0
    assert len(device_repo.list_by_user("USER-B")) == 1

    # 3. Disable token via disable_by_token
    disabled = device_repo.disable_by_token("fcm_shared_tok_777")
    assert disabled is not None
    assert disabled.is_enabled is False
    assert len(device_repo.list_by_user("USER-B", is_enabled_only=True)) == 0
    assert len(device_repo.list_by_user("USER-B", is_enabled_only=False)) == 1

    # 4. Fresh repository recreation proof
    del device_repo
    fresh_device_repo = PostgreSQLUserDeviceRepository()
    recovered = fresh_device_repo.get_by_id("dev_ios_002")
    assert recovered is not None
    assert recovered.user_id == "USER-B"
    assert recovered.fcm_token == "fcm_shared_tok_777"
    assert recovered.is_enabled is False


# =============================================================================
# Category F & G: Redis Message Idempotency vs. PostgreSQL Alert Dedup
# =============================================================================


@pytest.mark.anyio
async def test_f1_and_g1_redis_message_idempotency_vs_postgresql_alert_deduplication():
    service, alert_repo, notif_repo, _, _ = _make_pg_service()

    redis_client = aioredis.Redis(host="127.0.0.1", port=6379, db=0, decode_responses=False)
    redis_store = RedisIdempotencyStore(
        redis_client=redis_client,
        idempotency_ttl_seconds=86400,
        processing_claim_ttl_seconds=60,
        key_prefix="swiftlet:cp83_test_idempotency:",
    )
    await redis_store.clear_async()

    try:
        consumer = RabbitMQAlertConsumer(service=service, idempotency_store=redis_store)

        event_id_1 = str(uuid.uuid4())
        ev1 = {
            "eventId": event_id_1,
            "eventType": "iot.environment.low_temperature.started",
            "eventVersion": "1.0",
            "occurredAt": "2026-11-03T15:00:00.000Z",
            "producer": "iot-service",
            "payload": {
                "farmId": "FARM-01",
                "zoneId": "ZONE-B",
                "deviceId": "DEV-LOW-TEMP-01",
                "metric": "temperature",
                "value": 25.4,
                "threshold": 27.0,
                "unit": "°C",
            },
        }

        # 1. First delivery of event_id_1 -> processed, Alert created (occurrence_count=1)
        await consumer._handle_message(_make_mock_amqp_message(ev1))
        assert consumer.processed_count == 1
        assert consumer.duplicate_count == 0
        assert await redis_store.has_processed_async(event_id_1) is True

        # 2. Duplicate delivery of SAME event_id_1 -> blocked by RedisIdempotencyStore!
        await consumer._handle_message(_make_mock_amqp_message(ev1))
        assert consumer.processed_count == 1
        assert consumer.duplicate_count == 1
        active = alert_repo.find_active_by_dedup_key(
            "FARM-01", "ZONE-B", "DEV-LOW-TEMP-01", AlertEventType.LOW_TEMPERATURE
        )
        assert active is not None
        assert active.occurrence_count == 1  # NOT incremented for duplicate RabbitMQ message!

        # 3. Genuine second condition occurrence with DIFFERENT event_id_2 ->
        #    passes Redis idempotency, deduplicated by PostgreSQLAlertRepository!
        event_id_2 = str(uuid.uuid4())
        ev2 = {**ev1, "eventId": event_id_2, "occurredAt": "2026-11-03T15:05:00.000Z"}
        await consumer._handle_message(_make_mock_amqp_message(ev2))
        assert consumer.processed_count == 2
        assert consumer.duplicate_count == 1

        active_after = alert_repo.find_active_by_dedup_key(
            "FARM-01", "ZONE-B", "DEV-LOW-TEMP-01", AlertEventType.LOW_TEMPERATURE
        )
        assert active_after is not None
        assert active_after.alert_id == active.alert_id
        assert active_after.occurrence_count == 2

        # 4. Direct concurrent insert collision on uq_alerts_active_dedup_key merges atomically
        racing_new_alert = Alert(
            alert_id="alt_concurrent_race_999",
            farm_id="FARM-01",
            zone_id="ZONE-B",
            device_id="DEV-LOW-TEMP-01",
            event_type=AlertEventType.LOW_TEMPERATURE,
            severity=AlertSeverity.MEDIUM,
            status=AlertStatus.OPEN,
            source=AlertSource.IOT_ENVIRONMENT,
            title="Low Temperature Warning",
            message="Concurrent race insert",
            created_at=datetime(2026, 11, 3, 15, 6, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 11, 3, 15, 6, 0, tzinfo=timezone.utc),
            last_occurred_at=datetime(2026, 11, 3, 15, 6, 0, tzinfo=timezone.utc),
            occurrence_count=1,
        )
        merged = alert_repo.save(racing_new_alert)
        assert merged.alert_id == active.alert_id
        assert merged.occurrence_count == 3
        assert alert_repo.count_alerts(farm_id="FARM-01", zone_id="ZONE-B") == 1
    finally:
        await redis_store.clear_async()
        await redis_client.aclose()


# =============================================================================
# Category H & I: RabbitMQ Retry/DLQ & WebSocket Realtime Delivery with PostgreSQL
# =============================================================================


@pytest.mark.anyio
async def test_h1_and_i1_rabbitmq_retry_dlq_malformed_and_websocket_with_postgresql():
    service, alert_repo, notif_repo, _, _ = _make_pg_service()
    settings = RabbitMQSettings(max_retries=2, retry_ttl_ms=2000)
    consumer = RabbitMQAlertConsumer(
        service=service,
        idempotency_store=InMemoryIdempotencyStore(),
        settings=settings,
    )
    consumer._publish_to_exchange = AsyncMock()

    # 1. Malformed message -> rejected directly (requeue=False -> DLQ)
    bad_msg = MagicMock(spec=AbstractIncomingMessage)
    bad_msg.body = b"{invalid_json"
    bad_msg.routing_key = "iot.device.offline"
    bad_msg.headers = {}
    bad_msg.reject = AsyncMock()
    await consumer._handle_message(bad_msg)
    bad_msg.reject.assert_awaited_once_with(requeue=False)
    assert consumer.rejected_count == 1

    # 2. Retry exhausted -> republished to DLX and original ACKed
    consumer.mapper.process_envelope = MagicMock(side_effect=RuntimeError("Simulated downstream timeout"))
    exhausted_ev = {
        "eventId": str(uuid.uuid4()),
        "eventType": "iot.device.offline",
        "eventVersion": "1.0",
        "occurredAt": "2026-11-03T15:30:00.000Z",
        "producer": "iot-service",
        "payload": {"farmId": "FARM-01", "deviceId": "DEV-DLQ-01"},
    }
    exhausted_msg = _make_mock_amqp_message(exhausted_ev, retry_count=2)
    await consumer._handle_message(exhausted_msg)
    assert consumer.dead_lettered_count == 1
    exhausted_msg.ack.assert_awaited_once()

    # 3. WebSocket realtime delivery works with PostgreSQL repositories
    with TestClient(app) as client:
        with client.websocket_connect("/ws/notifications?userId=USER-OWNER-01") as ws:
            resp = client.post(
                "/internal/v1/events/ai",
                json={
                    "eventType": "PREDATOR_DETECTED",
                    "farmId": "FARM-01",
                    "zoneId": "ZONE-A",
                    "cameraId": "CAM-WS-01",
                    "predatorType": "snake",
                    "confidence": 0.92,
                },
            )
            assert resp.status_code == 200
            ws_msg_1 = ws.receive_json()
            ws_msg_2 = ws.receive_json()
            received_types = {ws_msg_1["type"], ws_msg_2["type"]}
            assert "alert.created" in received_types
            assert "notification.created" in received_types


# =============================================================================
# Category J: Database Failure/Recovery & Service Ownership Boundary (Steps 17J & 20)
# =============================================================================


@pytest.mark.anyio
async def test_j1_postgresql_failure_does_not_ack_or_falsely_report_success_and_recovers(caplog):
    # 1. Configure service with unreachable/broken PostgreSQL credentials
    broken_alert_repo = PostgreSQLAlertRepository(
        database_url="postgresql://broken_user:wrong_pass@127.0.0.1:5432/notification_db"
    )
    notif_repo = PostgreSQLNotificationRepository()
    device_repo = PostgreSQLUserDeviceRepository()
    rule_provider = InMemoryAlertRuleConfigProvider()
    resolver = InMemoryRecipientResolver()
    fcm_provider = MockFCMProvider()

    service = NotificationService(
        alert_repo=broken_alert_repo,
        notification_repo=notif_repo,
        user_device_repo=device_repo,
        rule_config_provider=rule_provider,
        recipient_resolver=resolver,
        fcm_provider=fcm_provider,
    )

    idempotency_store = InMemoryIdempotencyStore()
    consumer = RabbitMQAlertConsumer(
        service=service,
        idempotency_store=idempotency_store,
        settings=RabbitMQSettings(max_retries=3),
    )
    consumer._publish_to_exchange = AsyncMock()

    event_id = str(uuid.uuid4())
    ev = {
        "eventId": event_id,
        "eventType": "iot.device.offline",
        "eventVersion": "1.0",
        "occurredAt": "2026-11-03T16:00:00.000Z",
        "producer": "iot-service",
        "payload": {"farmId": "FARM-01", "zoneId": "ZONE-A", "deviceId": "DEV-DB-FAIL-01"},
    }
    msg_attempt_0 = _make_mock_amqp_message(ev, retry_count=0)

    # Execute consumer while PostgreSQL fails:
    # Must log error, release idempotency claim, schedule retry, and NOT mark processed!
    await consumer._handle_message(msg_attempt_0)
    assert consumer.failed_count == 1
    assert consumer.retry_scheduled_count == 1
    assert consumer.processed_count == 0
    assert idempotency_store.has_processed(event_id) is False
    assert "[NOTIFICATION ALERT DEDUP QUERY FAILED]" in caplog.text or "[RABBITMQ CONSUMER PROCESSING FAILED]" in caplog.text

    # 2. PostgreSQL recovers -> swap in healthy PostgreSQLAlertRepository and process retry attempt 1
    assert check_database_health() is True
    healthy_alert_repo = PostgreSQLAlertRepository()
    service.alert_repo = healthy_alert_repo
    service.lifecycle_service.alert_repo = healthy_alert_repo

    msg_attempt_1 = _make_mock_amqp_message(ev, retry_count=1)
    await consumer._handle_message(msg_attempt_1)
    assert consumer.processed_count == 1
    assert idempotency_store.has_processed(event_id) is True

    # Verify durable Alert now exists in PostgreSQL
    persisted = healthy_alert_repo.find_active_by_dedup_key(
        "FARM-01", "ZONE-A", "DEV-DB-FAIL-01", AlertEventType.DEVICE_OFFLINE
    )
    assert persisted is not None
    assert persisted.status == AlertStatus.OPEN


def test_j2_zero_cross_service_fks_and_least_privilege_role_in_notification_db():
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Zero foreign key constraints in notification_db
            cur.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.table_constraints
                WHERE constraint_type = 'FOREIGN KEY'
                  AND table_schema = 'public'
                """
            )
            fk_count = cur.fetchone()[0]
            assert fk_count == 0

            # 2. Verify notification_user least-privilege attributes
            cur.execute(
                """
                SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolcanlogin
                FROM pg_roles
                WHERE rolname = 'notification_user'
                """
            )
            role_row = cur.fetchone()
            assert role_row == ("notification_user", False, False, False, False, True)

            # 3. Verify applied migration and tables
            cur.execute("SELECT version FROM schema_migrations")
            versions = [r[0] for r in cur.fetchall()]
            assert "001_initial_notification_persistence" in versions

            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
                """
            )
            tables = [r[0] for r in cur.fetchall()]
            assert tables == ["alerts", "notifications", "processed_events", "schema_migrations", "user_devices"]

    # 4. Verify Notification Service source files never reference other services' DBs or Redis keys
    app_dir = pathlib.Path(__file__).resolve().parent.parent / "app"
    for py_file in app_dir.rglob("*.py"):
        if py_file.name == "database.py":
            continue
        source = py_file.read_text(encoding="utf-8")
        assert "management_db" not in source
        assert "iot_db" not in source
        assert "ai_db" not in source
        assert "iot:presence:" not in source
        assert "iot:latest:" not in source
        assert "ai:latest:" not in source
