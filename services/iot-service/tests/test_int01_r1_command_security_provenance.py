"""INT01-R1 regression tests: server-side command TIMEOUT, terminal states, late/duplicate/
wrong-device ACKs, IoT internal API authentication, forged device targets and data provenance.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.domain_events.evaluator import IoTConditionEvaluator
from app.domain_events.metadata_resolver import DeviceMetadataResolver
from app.domain_events.publisher import InMemoryDomainEventPublisher
from app.main import app
from app.repositories.command_repository import InMemoryCommandRepository
from app.schemas.api import CommandResponse, TelemetryResponse
from app.schemas.telemetry import AcceptedTelemetry, TelemetryPayload
from app.services.ack_service import AckService
from app.services.command_service import DeviceCommandService

DEVICE = "SWC-NODE-001"
KEY = "int01-r1-test-internal-service-key-32chars!!"


class StubPublisher:
    def __init__(self, succeed: bool = True):
        self.succeed = succeed
        self.published: list[tuple[str, str]] = []

    def publish(self, topic, payload, qos=1, retain=False):
        self.published.append((topic, payload if isinstance(payload, str) else payload.decode()))
        return self.succeed


def _services(succeed: bool = True):
    repo = InMemoryCommandRepository()
    pub = InMemoryDomainEventPublisher()
    evaluator = IoTConditionEvaluator(publisher=pub, resolver=DeviceMetadataResolver())
    publisher = StubPublisher(succeed)
    cmd_svc = DeviceCommandService(repository=repo, publisher=publisher, condition_evaluator=evaluator)
    ack_svc = AckService(repository=repo, condition_evaluator=evaluator)
    return repo, cmd_svc, ack_svc, publisher, pub


def _ack(cmd_id: str, status: str = "SUCCESS", device: str = DEVICE) -> str:
    return json.dumps({"commandId": cmd_id, "deviceId": device, "status": status, "mode": "MANUAL", "message": f"sim {status}"})


# ---------------------------------------------------------------- command lifecycle
class TestCommandLifecycle:
    def test_published_command_carries_server_deadline_and_expires_at(self):
        _, cmd_svc, _, publisher, _ = _services()
        cmd = cmd_svc.send_set_relay_command(DEVICE, "misting", 1)
        assert cmd.status == "PUBLISHED"
        assert cmd.expires_at is not None
        delta = (cmd.expires_at - cmd.created_at).total_seconds()
        assert delta == pytest.approx(settings.command_ack_timeout_seconds, abs=1)
        topic, raw = publisher.published[-1]
        sent = json.loads(raw)
        assert topic == f"swiftlet/command/{DEVICE}"
        assert sent["expiresAt"].endswith("Z")
        assert sent["commandId"] == cmd.command_id

    @pytest.mark.parametrize("status", ["SUCCESS", "FAILED", "ERROR"])
    def test_each_ack_status_is_terminal_and_reported(self, status):
        _, cmd_svc, ack_svc, _, _ = _services()
        cmd = cmd_svc.send_set_relay_command(DEVICE, "fan", 1)
        res = ack_svc.process_message(DEVICE, _ack(cmd.command_id, status))
        assert res.success is True
        final = cmd_svc.get_command(cmd.command_id)
        assert final.status == status
        assert CommandResponse.from_domain(final).isTerminal is True
        # a terminal state never times out later
        assert cmd_svc.evaluate_command_timeouts(now=final.created_at + timedelta(hours=1)) == []
        assert cmd_svc.get_command(cmd.command_id).status == status

    def test_runtime_timeout_uses_server_deadline_without_explicit_timeout(self):
        _, cmd_svc, _, _, events = _services()
        cmd = cmd_svc.send_set_relay_command(DEVICE, "heater", 1)
        assert cmd_svc.evaluate_command_timeouts(now=cmd.expires_at - timedelta(seconds=1)) == []
        timed_out = cmd_svc.evaluate_command_timeouts(now=cmd.expires_at + timedelta(seconds=1))
        assert [c.command_id for c in timed_out] == [cmd.command_id]
        final = cmd_svc.get_command(cmd.command_id)
        assert final.status == "TIMEOUT"
        assert CommandResponse.from_domain(final).isTerminal is True
        assert "iot.command.failed" in events.event_types

    def test_get_command_lazily_expires_overdue_command(self, monkeypatch):
        _, cmd_svc, _, _, _ = _services()
        cmd = cmd_svc.send_set_relay_command(DEVICE, "fan", 0)
        future = cmd.expires_at + timedelta(seconds=2)

        class _FrozenDT(datetime):
            @classmethod
            def now(cls, tz=None):
                return future

        import importlib

        mod = importlib.import_module("app.services.command_service")
        monkeypatch.setattr(mod, "datetime", _FrozenDT)
        assert cmd_svc.get_command(cmd.command_id).status == "TIMEOUT"

    def test_late_ack_after_timeout_is_recorded_but_never_success(self):
        _, cmd_svc, ack_svc, _, _ = _services()
        cmd = cmd_svc.send_set_relay_command(DEVICE, "misting", 1)
        cmd_svc.evaluate_command_timeouts(now=cmd.expires_at + timedelta(seconds=1))
        res = ack_svc.process_message(DEVICE, _ack(cmd.command_id, "SUCCESS"))
        assert res.success is False and "Late ACK" in res.error
        final = cmd_svc.get_command(cmd.command_id)
        assert final.status == "TIMEOUT"
        assert final.late_ack_status == "SUCCESS"
        assert final.late_ack_at is not None
        body = CommandResponse.from_domain(final)
        assert body.status == "TIMEOUT" and body.lateAckStatus == "SUCCESS"
        # a second late ACK does not overwrite the first record
        ack_svc.process_message(DEVICE, _ack(cmd.command_id, "FAILED"))
        assert cmd_svc.get_command(cmd.command_id).late_ack_status == "SUCCESS"

    def test_ack_arriving_after_deadline_before_sweep_is_late(self):
        repo, cmd_svc, ack_svc, _, _ = _services()
        cmd = cmd_svc.send_set_relay_command(DEVICE, "fan", 1)
        # simulate sweeper lag: deadline already passed, status still PUBLISHED
        repo.update(cmd.model_copy(update={"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}))
        res = ack_svc.process_message(DEVICE, _ack(cmd.command_id, "SUCCESS"))
        assert res.success is False
        assert repo.get(cmd.command_id).status == "TIMEOUT"
        assert repo.get(cmd.command_id).late_ack_status == "SUCCESS"

    def test_duplicate_ack_is_idempotent(self):
        _, cmd_svc, ack_svc, _, _ = _services()
        cmd = cmd_svc.send_set_relay_command(DEVICE, "fan", 1)
        assert ack_svc.process_message(DEVICE, _ack(cmd.command_id, "SUCCESS")).success
        first = cmd_svc.get_command(cmd.command_id)
        dup = ack_svc.process_message(DEVICE, _ack(cmd.command_id, "FAILED"))
        assert dup.success is True
        again = cmd_svc.get_command(cmd.command_id)
        assert again.status == "SUCCESS" and again.acknowledged_at == first.acknowledged_at

    def test_wrong_device_and_topic_mismatch_ack_rejected(self):
        _, cmd_svc, ack_svc, _, _ = _services()
        cmd = cmd_svc.send_set_relay_command(DEVICE, "fan", 1)
        # payload deviceId != topic device
        assert ack_svc.process_message(DEVICE, _ack(cmd.command_id, "SUCCESS", device="SWC-NODE-999")).success is False
        # ACK from another device for this command
        assert ack_svc.process_message("SWC-NODE-999", _ack(cmd.command_id, "SUCCESS", device="SWC-NODE-999")).success is False
        assert cmd_svc.get_command(cmd.command_id).status == "PUBLISHED"

    def test_offline_publish_failure_is_terminal_failed_not_success(self):
        _, cmd_svc, ack_svc, _, _ = _services(succeed=False)
        cmd = cmd_svc.send_set_relay_command(DEVICE, "fan", 1)
        assert cmd.status == "FAILED"
        ack_svc.process_message(DEVICE, _ack(cmd.command_id, "SUCCESS"))
        assert cmd_svc.get_command(cmd.command_id).status == "FAILED"

    def test_offline_device_publish_ok_stays_published_then_timeout_and_reconnect_cannot_resurrect(self):
        _, cmd_svc, ack_svc, _, _ = _services()
        cmd = cmd_svc.send_set_relay_command(DEVICE, "misting", 1)
        assert cmd.status == "PUBLISHED"  # broker accepted, device offline -> no ACK
        cmd_svc.evaluate_command_timeouts(now=cmd.expires_at + timedelta(seconds=1))
        # device reconnects and (wrongly) executes a replayed copy -> late ACK cannot become SUCCESS
        ack_svc.process_message(DEVICE, _ack(cmd.command_id, "SUCCESS"))
        assert cmd_svc.get_command(cmd.command_id).status == "TIMEOUT"

    def test_service_restart_drops_in_memory_commands_and_rejects_their_acks(self):
        _, cmd_svc, _, _, _ = _services()
        cmd = cmd_svc.send_set_relay_command(DEVICE, "fan", 1)
        # restart == fresh in-memory repository (documented limitation)
        fresh_repo = InMemoryCommandRepository()
        fresh_ack = AckService(repository=fresh_repo)
        res = fresh_ack.process_message(DEVICE, _ack(cmd.command_id, "SUCCESS"))
        assert res.success is False and "Unknown commandId" in res.error
        assert fresh_repo.get(cmd.command_id) is None

    def test_concurrent_ack_and_timeout_never_end_in_success_after_timeout(self):
        for _ in range(50):
            repo, cmd_svc, ack_svc, _, _ = _services()
            cmd = cmd_svc.send_set_relay_command(DEVICE, "fan", 1)
            overdue = cmd.expires_at + timedelta(seconds=1)
            barrier = threading.Barrier(2)

            def sweep():
                barrier.wait()
                cmd_svc.evaluate_command_timeouts(now=overdue)

            def ack():
                barrier.wait()
                ack_svc.process_message(DEVICE, _ack(cmd.command_id, "SUCCESS"))

            threads = [threading.Thread(target=sweep), threading.Thread(target=ack)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            final = repo.get(cmd.command_id)
            assert final.status in ("SUCCESS", "TIMEOUT")
            if final.status == "TIMEOUT":
                assert final.acknowledged_at is None

    def test_runtime_sweeper_is_started_by_lifespan(self, monkeypatch):
        monkeypatch.setattr(settings, "mqtt_auto_start", False)
        with TestClient(app) as client:
            body = client.get("/health/runtime").json()
            assert body["commandTimeoutSweeper"] == "running"
            assert body["mqtt"] == "disabled"
            assert body["commandAckTimeoutSeconds"] == settings.command_ack_timeout_seconds
            assert client.get("/health").json() == {"status": "ok", "service": "iot-service"}


# ---------------------------------------------------------------- internal API security
@pytest.mark.internal_auth
class TestInternalApiAuthentication:
    PATHS = [
        ("post", f"/api/iot/devices/{DEVICE}/commands/relay", {"target": "fan", "state": 1}),
        ("post", f"/api/iot/devices/{DEVICE}/commands/config", {"targetTemp": 28.0, "targetHum": 80.0, "isAutoMode": True}),
        ("get", f"/api/iot/devices/{DEVICE}/telemetry/latest", None),
        ("get", "/api/iot/devices/presence", None),
        ("get", "/api/iot/commands/00000000-0000-0000-0000-000000000000", None),
    ]

    @pytest.mark.parametrize("method,path,body", PATHS)
    def test_missing_or_wrong_key_is_rejected(self, monkeypatch, method, path, body):
        monkeypatch.setattr(settings, "internal_service_key", KEY)
        client = TestClient(app)
        kw = {"json": body} if body is not None else {}
        assert getattr(client, method)(path, **kw).status_code == 401
        assert getattr(client, method)(path, headers={"X-Internal-Service-Key": "wrong"}, **kw).status_code == 401

    def test_unconfigured_key_fails_closed(self, monkeypatch):
        monkeypatch.setattr(settings, "internal_service_key", "")
        client = TestClient(app)
        r = client.post(f"/api/iot/devices/{DEVICE}/commands/relay", json={"target": "fan", "state": 1},
                        headers={"X-Internal-Service-Key": "anything"})
        assert r.status_code == 503

    def test_valid_key_reaches_business_logic(self, monkeypatch):
        monkeypatch.setattr(settings, "internal_service_key", KEY)
        monkeypatch.setattr(settings, "management_service_url", "")
        client = TestClient(app)
        r = client.get("/api/iot/commands/00000000-0000-0000-0000-000000000000",
                       headers={"X-Internal-Service-Key": KEY})
        assert r.status_code == 404  # authenticated -> real lookup

    def test_health_stays_public(self, monkeypatch):
        monkeypatch.setattr(settings, "internal_service_key", KEY)
        assert TestClient(app).get("/health").status_code == 200

    def test_internal_websocket_requires_key(self, monkeypatch):
        from starlette.websockets import WebSocketDisconnect

        monkeypatch.setattr(settings, "internal_service_key", KEY)
        client = TestClient(app)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/iot") as ws:
                ws.receive_text()


@pytest.mark.internal_auth
class TestForgedDeviceTarget:
    def test_unregistered_node_never_gets_mqtt_command(self, monkeypatch):
        import app.domain_events.metadata_resolver as mr
        from app.routes.dependencies import get_command_service

        monkeypatch.setattr(settings, "internal_service_key", KEY)
        monkeypatch.setattr(settings, "management_service_url", "http://management-service:8001")
        monkeypatch.setattr(mr.default_metadata_resolver, "resolve", lambda device_id: None)
        _, cmd_svc, _, publisher, _ = _services()
        app.dependency_overrides[get_command_service] = lambda: cmd_svc
        try:
            r = TestClient(app).post(
                "/api/iot/devices/FORGED-NODE-01/commands/relay",
                json={"target": "fan", "state": 1},
                headers={"X-Internal-Service-Key": KEY},
            )
        finally:
            app.dependency_overrides.pop(get_command_service, None)
        assert r.status_code == 404
        assert publisher.published == []

    def test_registered_node_is_accepted(self, monkeypatch):
        import app.domain_events.metadata_resolver as mr
        from app.domain_events.metadata_resolver import DeviceLocation
        from app.routes.dependencies import get_command_service

        monkeypatch.setattr(settings, "internal_service_key", KEY)
        monkeypatch.setattr(settings, "management_service_url", "http://management-service:8001")
        monkeypatch.setattr(mr.default_metadata_resolver, "resolve", lambda d: DeviceLocation("farm-a", "zone-a"))
        _, cmd_svc, _, publisher, _ = _services()
        app.dependency_overrides[get_command_service] = lambda: cmd_svc
        try:
            r = TestClient(app).post(
                f"/api/iot/devices/{DEVICE}/commands/relay",
                json={"target": "fan", "state": 1},
                headers={"X-Internal-Service-Key": KEY},
            )
        finally:
            app.dependency_overrides.pop(get_command_service, None)
        assert r.status_code == 202
        assert r.json()["status"] == "PUBLISHED" and r.json()["isTerminal"] is False
        assert len(publisher.published) == 1


# ---------------------------------------------------------------- provenance
def _payload(**overrides):
    base = {
        "deviceId": DEVICE,
        "metrics": {"temperature": 28.5, "humidity": 82.0, "lux": 0.4, "co2": 460.0, "audioRms": 0.4, "audioHealthy": True},
        "actuators": {"misting": False, "fan": False, "heater": False, "alarm": False},
        "state": {"mode": "AUTO", "networkRssi": -62, "freeHeap": 200000},
    }
    base.update(overrides)
    return base


def _response(payload: dict) -> TelemetryResponse:
    p = TelemetryPayload.model_validate(payload)
    accepted = AcceptedTelemetry(device_id=p.deviceId, received_at=datetime.now(timezone.utc), metrics=p.metrics,
                                 actuators=p.actuators, state=p.state, provenance=p.provenance)
    return TelemetryResponse.from_domain(accepted)


class TestProvenance:
    def test_simulator_declaration_labels_every_metric_simulated(self):
        r = _response(_payload(provenance={"source": "SIMULATED", "sensors": {
            "temperature": "SIMULATED", "humidity": "SIMULATED", "co2": "SIMULATED",
            "lux": "SIMULATED", "audio": "SIMULATED", "networkRssi": "SIMULATED"}}))
        assert set(r.metricSources.values()) == {"SIMULATED"}

    def test_physical_dht_only_has_no_co2_lux_values(self):
        payload = _payload(provenance={"source": "PHYSICAL", "sensors": {
            "temperature": "PHYSICAL", "humidity": "PHYSICAL", "co2": "UNAVAILABLE",
            "lux": "UNAVAILABLE", "audio": "UNAVAILABLE", "networkRssi": "PHYSICAL"}})
        payload["metrics"] = {"temperature": 29.1, "humidity": 77.0, "co2": None, "lux": None, "audioRms": None, "audioHealthy": None}
        r = _response(payload)
        assert r.metrics.co2 is None and r.metrics.lux is None
        assert r.metricSources["temperature"] == "PHYSICAL"
        assert r.metricSources["co2"] == "UNAVAILABLE" and r.metricSources["lux"] == "UNAVAILABLE"

    def test_declared_unavailable_value_is_dropped_not_displayed(self):
        r = _response(_payload(provenance={"source": "PHYSICAL", "sensors": {"co2": "UNAVAILABLE", "lux": "UNAVAILABLE"}}))
        assert r.metrics.co2 is None and r.metrics.lux is None
        assert r.metricSources["co2"] == "UNAVAILABLE"

    def test_undeclared_legacy_payload_is_unverified_never_physical(self):
        r = _response(_payload())
        assert "PHYSICAL" not in r.metricSources.values()
        assert r.metricSources["temperature"] == "UNVERIFIED"

    def test_missing_optional_metrics_are_null_not_zero(self):
        payload = _payload()
        payload["metrics"] = {"temperature": 28.0, "humidity": 80.0}
        r = _response(payload)
        assert r.metrics.co2 is None and r.metrics.lux is None and r.metrics.audioHealthy is None
        assert r.metricSources["co2"] == "UNAVAILABLE"

    def test_no_audio_data_never_emits_audio_fault(self):
        pub = InMemoryDomainEventPublisher()
        evaluator = IoTConditionEvaluator(publisher=pub, resolver=DeviceMetadataResolver())
        payload = _payload()
        payload["metrics"] = {"temperature": 28.0, "humidity": 80.0}
        p = TelemetryPayload.model_validate(payload)
        accepted = AcceptedTelemetry(device_id=DEVICE, received_at=datetime.now(timezone.utc), metrics=p.metrics,
                                     actuators=p.actuators, state=p.state)
        evaluator.evaluate_telemetry(accepted)
        assert not any("audio" in e for e in pub.event_types)

    def test_invalid_provenance_label_rejected(self):
        with pytest.raises(Exception):
            TelemetryPayload.model_validate(_payload(provenance={"source": "REAL", "sensors": {}}))
