"""PR #24 Gate 1 remediation, security, status semantics, and negative/edge-case tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.domain_events import publisher as pub_mod
from app.domain_events.evaluator import IoTConditionEvaluator
from app.domain_events.metadata_resolver import DeviceMetadataResolver
from app.domain_events.publisher import InMemoryDomainEventPublisher, RabbitMQEventPublisher
from app.main import app
from app.mqtt.topics import TopicParseError
from app.repositories.command_repository import InMemoryCommandRepository
from app.repositories.presence_repository import InMemoryDevicePresenceRepository
from app.repositories.telemetry_repository import InMemoryTelemetryRepository
from app.schemas.presence import HeartbeatPayload
from app.services.ack_service import AckService
from app.services.command_service import DeviceCommandService
from app.services.diagnostics_service import DiagnosticsService
from app.services.presence_service import DevicePresenceService
from app.services.telemetry_service import TelemetryService


class StubPublisher:
    def __init__(self, succeed: bool = True):
        self.succeed = succeed
        self.published: list[tuple[str, str]] = []

    def publish(self, topic: str, payload: str | bytes, qos: int = 1, retain: bool = False) -> bool:
        raw = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        self.published.append((topic, raw))
        return self.succeed


class TestInvalidIdentityAndPayloads:
    @pytest.mark.parametrize("bad_node_id", ["", "bad/node", "bad#node", "bad+node", "bad node"])
    def test_invalid_node_id_rejected_without_polluting_command_repo(self, bad_node_id):
        repo = InMemoryCommandRepository()
        cmd_svc = DeviceCommandService(repository=repo, publisher=StubPublisher(True))
        with pytest.raises((TopicParseError, ValueError)):
            cmd_svc.send_set_relay_command(bad_node_id, "misting", 1)
        assert repo.list_all() == []

    def test_unknown_device_returns_404_on_telemetry_and_presence(self):
        client = TestClient(app)
        assert client.get("/api/iot/devices/NO-SUCH-NODE-999/telemetry/latest").status_code == 404
        assert client.get("/api/iot/devices/NO-SUCH-NODE-999/presence").status_code == 404

    def test_malformed_json_and_topic_mismatch_and_invalid_bounds_rejected(self):
        tel_repo = InMemoryTelemetryRepository()
        svc = TelemetryService(repository=tel_repo)

        assert svc.process_message("SWC-NODE-001", b"{not-valid-json").success is False
        assert svc.process_message("SWC-NODE-001", b'["array-not-dict"]').success is False

        mismatch = {
            "deviceId": "OTHER-NODE",
            "metrics": {"temperature": 28.5, "humidity": 80.0, "lux": 0.5, "co2": 500.0, "audioRms": 12.0, "audioHealthy": True},
            "actuators": {"misting": False, "fan": False, "heater": False, "alarm": False},
            "state": {"mode": "AUTO"},
        }
        res_mismatch = svc.process_message("SWC-NODE-001", json.dumps(mismatch))
        assert res_mismatch.success is False

        out_of_range = {
            "deviceId": "SWC-NODE-001",
            "metrics": {"temperature": 250.0, "humidity": 150.0, "lux": -5.0, "co2": 500.0, "audioRms": 12.0, "audioHealthy": True},
            "actuators": {"misting": False, "fan": False, "heater": False, "alarm": False},
            "state": {"mode": "AUTO"},
        }
        res_bounds = svc.process_message("SWC-NODE-001", json.dumps(out_of_range))
        assert res_bounds.success is False
        assert tel_repo.get_latest("SWC-NODE-001") is None


class TestStatusSemanticsAndCrossFarmIsolation:
    def test_unregistered_device_diagnostics_does_not_leak_other_farm_or_fake_ip_rssi(self):
        diag_svc = DiagnosticsService(
            telemetry_repo=InMemoryTelemetryRepository(),
            presence_repo=InMemoryDevicePresenceRepository(),
            command_repo=InMemoryCommandRepository(),
        )
        detail = diag_svc.get_device_diagnostics("BRAND-NEW-UNREGISTERED-NODE")
        assert detail is not None
        assert detail.farm == "Chưa phân bổ"
        assert detail.zone == "Chưa phân bổ"
        assert detail.connectivity.ip is None
        assert detail.connectivity.rssi is None

        checklist = diag_svc.get_installation_checklist("BRAND-NEW-UNREGISTERED-NODE")
        assert checklist.power.passed is False
        assert checklist.power.details["uptime"] is None
        assert checklist.mqtt.details["status"] == "UNKNOWN"

    def test_online_node_without_telemetry_or_ip_never_fabricates_rssi_or_ip(self):
        pres_repo = InMemoryDevicePresenceRepository()
        pres_svc = DevicePresenceService(repository=pres_repo)
        pres_svc.record_online_status("SWC-NO-IP-01")

        diag_svc = DiagnosticsService(
            telemetry_repo=InMemoryTelemetryRepository(),
            presence_repo=pres_repo,
            command_repo=InMemoryCommandRepository(),
        )
        detail = diag_svc.get_device_diagnostics("SWC-NO-IP-01")
        assert detail is not None
        assert detail.connectivity.ip is None
        assert detail.connectivity.rssi is None

    def test_stale_and_out_of_order_heartbeat_and_reconnect_lifecycle(self):
        pres_repo = InMemoryDevicePresenceRepository()
        pub = InMemoryDomainEventPublisher()
        resolver = DeviceMetadataResolver()
        evaluator = IoTConditionEvaluator(publisher=pub, resolver=resolver)
        pres_svc = DevicePresenceService(
            repository=pres_repo,
            stale_timeout_seconds=60,
            condition_evaluator=evaluator,
        )

        t0 = datetime(2026, 11, 19, 10, 0, 0, tzinfo=timezone.utc)
        hb1 = HeartbeatPayload(deviceId="SWC-NODE-001", uptime=100, ip="10.0.0.5", freeHeap=40000, mockMode=False)
        pres_svc.record_heartbeat("SWC-NODE-001", hb1, timestamp=t0)
        assert pres_svc.get_presence("SWC-NODE-001").status == "ONLINE"

        # Explicit LWT offline at t0 + 10s
        pres_svc.record_offline_status("SWC-NODE-001", timestamp=t0 + timedelta(seconds=10))
        assert pres_svc.get_presence("SWC-NODE-001").status == "OFFLINE"

        # Older/stale heartbeat arriving out-of-order at t0 + 5s MUST NOT revive OFFLINE device
        pres_svc.record_heartbeat("SWC-NODE-001", hb1, timestamp=t0 + timedelta(seconds=5))
        assert pres_svc.get_presence("SWC-NODE-001").status == "OFFLINE"

        # Fresh heartbeat at t0 + 20s restores ONLINE
        pres_svc.record_heartbeat("SWC-NODE-001", hb1, timestamp=t0 + timedelta(seconds=20))
        assert pres_svc.get_presence("SWC-NODE-001").status == "ONLINE"

        # Timeout past 60s transitions ONLINE -> STALE
        stale = pres_svc.evaluate_stale_devices(now=t0 + timedelta(seconds=120), timeout_seconds=60)
        assert len(stale) == 1
        assert pres_svc.get_presence("SWC-NODE-001").status == "STALE"


class TestCommandTimeoutLateAckAndDeviceZoneChange:
    def test_publish_success_stays_published_until_ack_and_timeout_blocks_late_ack(self):
        cmd_repo = InMemoryCommandRepository()
        pub = InMemoryDomainEventPublisher()
        evaluator = IoTConditionEvaluator(publisher=pub, resolver=DeviceMetadataResolver())
        cmd_svc = DeviceCommandService(
            repository=cmd_repo,
            publisher=StubPublisher(True),
            condition_evaluator=evaluator,
        )
        ack_svc = AckService(repository=cmd_repo, condition_evaluator=evaluator)

        cmd = cmd_svc.send_set_relay_command("SWC-NODE-001", "fan", 1)
        # Never fake SUCCESS on broker publish alone
        assert cmd.status == "PUBLISHED"
        assert cmd.acknowledged_at is None

        # Timeout after 35s
        timed_out = cmd_svc.evaluate_command_timeouts(
            now=cmd.created_at + timedelta(seconds=35),
            timeout_seconds=30,
        )
        assert len(timed_out) == 1
        assert cmd_svc.get_command(cmd.command_id).status == "TIMEOUT"
        assert "iot.command.failed" in pub.event_types

        # Late ACK after TIMEOUT must be rejected and NOT flip status to SUCCESS
        late_ack = json.dumps({
            "commandId": cmd.command_id,
            "deviceId": "SWC-NODE-001",
            "status": "SUCCESS",
            "mode": "MANUAL",
            "message": "Late arrival",
        })
        res = ack_svc.process_message("SWC-NODE-001", late_ack)
        assert res.success is False
        assert cmd_svc.get_command(cmd.command_id).status == "TIMEOUT"

    def test_duplicate_ack_is_idempotent_and_wrong_device_ack_rejected(self):
        cmd_repo = InMemoryCommandRepository()
        cmd_svc = DeviceCommandService(repository=cmd_repo, publisher=StubPublisher(True))
        ack_svc = AckService(repository=cmd_repo)

        cmd = cmd_svc.send_set_relay_command("SWC-NODE-001", "misting", 1)
        wrong_ack = json.dumps({
            "commandId": cmd.command_id,
            "deviceId": "OTHER-NODE",
            "status": "SUCCESS",
            "mode": "MANUAL",
        })
        assert ack_svc.process_message("OTHER-NODE", wrong_ack).success is False
        assert cmd_svc.get_command(cmd.command_id).status == "PUBLISHED"

        good_ack = json.dumps({
            "commandId": cmd.command_id,
            "deviceId": "SWC-NODE-001",
            "status": "SUCCESS",
            "mode": "MANUAL",
        })
        assert ack_svc.process_message("SWC-NODE-001", good_ack).success is True
        assert cmd_svc.get_command(cmd.command_id).status == "SUCCESS"
        # Duplicate ACK returns success idempotently without changing state
        assert ack_svc.process_message("SWC-NODE-001", good_ack).success is True
        assert cmd_svc.get_command(cmd.command_id).status == "SUCCESS"

    def test_device_zone_change_with_same_node_id_routes_events_to_new_zone(self):
        pub = InMemoryDomainEventPublisher()
        resolver = DeviceMetadataResolver()
        evaluator = IoTConditionEvaluator(publisher=pub, resolver=resolver)
        tel_svc = TelemetryService(
            repository=InMemoryTelemetryRepository(),
            condition_evaluator=evaluator,
        )

        resolver.register("NODE-MOVE-01", "FARM-A", "ZONE-OLD")
        payload_hot = {
            "deviceId": "NODE-MOVE-01",
            "metrics": {"temperature": 33.0, "humidity": 80.0, "lux": 0.5, "co2": 500.0, "audioRms": 12.0, "audioHealthy": True},
            "actuators": {"misting": False, "fan": True, "heater": False, "alarm": False},
            "state": {"mode": "AUTO"},
        }
        assert tel_svc.process_message("NODE-MOVE-01", json.dumps(payload_hot)).success is True
        assert pub.published_events[-1].payload["zoneId"] == "ZONE-OLD"

        # Device moved to ZONE-NEW while node_id remains unchanged
        resolver.register("NODE-MOVE-01", "FARM-A", "ZONE-NEW")
        payload_cool = {
            "deviceId": "NODE-MOVE-01",
            "metrics": {"temperature": 29.0, "humidity": 80.0, "lux": 0.5, "co2": 500.0, "audioRms": 12.0, "audioHealthy": True},
            "actuators": {"misting": False, "fan": False, "heater": False, "alarm": False},
            "state": {"mode": "AUTO"},
        }
        assert tel_svc.process_message("NODE-MOVE-01", json.dumps(payload_cool)).success is True
        assert pub.published_events[-1].payload["zoneId"] == "ZONE-NEW"


class TestRabbitMQResilienceAndSecrets:
    def test_no_hardcoded_rabbitmq_password_in_publisher(self):
        src = Path(pub_mod.__file__).read_text(encoding="utf-8")
        assert "swiftlet123" not in src
        p = RabbitMQEventPublisher(host="127.0.0.1", port=59999)
        assert p.password == ""

    def test_telemetry_ingestion_succeeds_even_when_rabbitmq_unreachable(self):
        bad_pub = RabbitMQEventPublisher(host="127.0.0.1", port=59999, password="")
        evaluator = IoTConditionEvaluator(publisher=bad_pub, resolver=DeviceMetadataResolver())
        tel_repo = InMemoryTelemetryRepository()
        tel_svc = TelemetryService(repository=tel_repo, condition_evaluator=evaluator)

        payload_hot = {
            "deviceId": "SWC-NODE-001",
            "metrics": {"temperature": 33.5, "humidity": 80.0, "lux": 0.5, "co2": 500.0, "audioRms": 12.0, "audioHealthy": True},
            "actuators": {"misting": False, "fan": True, "heater": False, "alarm": False},
            "state": {"mode": "AUTO"},
        }
        res = tel_svc.process_message("SWC-NODE-001", json.dumps(payload_hot))
        assert res.success is True
        assert tel_repo.get_latest("SWC-NODE-001") is not None
