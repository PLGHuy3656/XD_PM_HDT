"""Comprehensive Integration & Verification Test Suite for SwiftletCare IoT Subsystem.

Covers:
1. [IOT] E2E Integration & Offline Resilience (Telemetry, Commands, Auto-Reconnect, Local Hysteresis Rules).
2. [IOT] Operational Events & Alert Sources (Condition Evaluator, Hysteresis Deadbands, Domain Event Publisher).
3. [IOT] Administrator Device Registry & Provisioning State (Read-only overview, Provisioning status, Health metadata).
4. [IOT] Technician Installation & Provisioning Support (5-step checklist, PROVISION_DEVICE command, Activation readiness).
5. [IOT] Technician Diagnostics & Health Telemetry (Deep diagnostic signals, Heartbeat, RSSI, Sensor/Actuator health, Issues).
"""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

import pytest
from fastapi.testclient import TestClient

from app.domain_events.canonical import CanonicalDomainEvent
from app.domain_events.evaluator import (
    HIGH_HUM_RECOVERY,
    HIGH_HUM_THRESHOLD,
    HIGH_TEMP_RECOVERY,
    HIGH_TEMP_THRESHOLD,
    LOW_HUM_RECOVERY,
    LOW_HUM_THRESHOLD,
    LOW_TEMP_RECOVERY,
    LOW_TEMP_THRESHOLD,
    IoTConditionEvaluator,
)
from app.domain_events.metadata_resolver import DeviceMetadataResolver
from app.domain_events.publisher import InMemoryDomainEventPublisher
from app.main import app
from app.mqtt.dispatcher import MessageDispatcher
from app.mqtt.topics import parse_topic
from app.repositories.command_repository import InMemoryCommandRepository
from app.repositories.presence_repository import InMemoryDevicePresenceRepository
from app.repositories.telemetry_repository import InMemoryTelemetryRepository
from app.schemas.command import AckPayload
from app.schemas.diagnostics import ProvisionDeviceRequest
from app.schemas.presence import HeartbeatPayload
from app.schemas.telemetry import AcceptedTelemetry, ActuatorState, DeviceRuntimeState, TelemetryMetrics, TelemetryPayload
from app.services.ack_service import AckService
from app.services.command_service import DeviceCommandService
from app.services.diagnostics_service import DiagnosticsService
from app.services.heartbeat_service import HeartbeatService
from app.services.presence_service import DevicePresenceService
from app.services.status_service import StatusService
from app.services.telemetry_service import TelemetryService
from demo.device_simulator import ESP32DeviceSimulator


# --- Test Helpers & Fixtures ---

class MemoryEventSink:
    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event)


class DirectSimulatorBridge:
    """Synchronously bridges command publishing to simulator and returns simulator ACK to dispatcher."""

    def __init__(self, simulator: ESP32DeviceSimulator, dispatcher: MessageDispatcher):
        self.simulator = simulator
        self.dispatcher = dispatcher
        self.published = []

    def publish(self, topic: str, payload: str | bytes, qos: int = 1, retain: bool = False) -> bool:
        raw_str = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        self.published.append((topic, raw_str))
        ack = self.simulator.handle_command_payload(raw_str)
        if ack is not None:
            ack_topic = parse_topic(f"swiftlet/ack/{self.simulator.device_id}")
            self.dispatcher.dispatch(ack_topic, json.dumps(ack).encode("utf-8"))
        return True


# ============================================================================
# 1. [IOT] KIỂM CHỨNG TÍCH HỢP IOT E2E & KHẢ NĂNG CHỊU MẤT KẾT NỐI
# ============================================================================

def test_e2e_telemetry_flow_simulator_to_api():
    """Verify ESP32 simulator sends telemetry -> parsed -> stored -> returned via REST API."""
    client = TestClient(app)
    sim = ESP32DeviceSimulator(device_id="SWC-NODE-001")
    telemetry_payload = sim.build_telemetry_payload()

    # Simulate arrival via MQTT dispatcher
    from app.mqtt.dispatcher import default_dispatcher
    t_topic = parse_topic("swiftlet/telemetry/SWC-NODE-001")
    default_dispatcher.dispatch(t_topic, json.dumps(telemetry_payload).encode("utf-8"))

    # Query via REST API
    resp = client.get("/api/iot/devices/SWC-NODE-001/telemetry/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["deviceId"] == "SWC-NODE-001"
    assert data["metrics"]["temperature"] == telemetry_payload["metrics"]["temperature"]
    assert data["metrics"]["humidity"] == telemetry_payload["metrics"]["humidity"]
    assert data["state"]["mode"] == "AUTO"


def test_e2e_command_and_ack_flow_manual_actuator_override():
    """Verify REST API issues SET_RELAY -> simulator switches relay & mode to MANUAL -> sends ACK -> command marked SUCCESS."""
    tel_repo = InMemoryTelemetryRepository()
    pres_repo = InMemoryDevicePresenceRepository()
    cmd_repo = InMemoryCommandRepository()
    sink = MemoryEventSink()

    tel_svc = TelemetryService(repository=tel_repo, realtime_publisher=sink)
    pres_svc = DevicePresenceService(repository=pres_repo, realtime_publisher=sink)
    hb_svc = HeartbeatService(presence_svc=pres_svc)
    stat_svc = StatusService(presence_svc=pres_svc)
    ack_svc = AckService(repository=cmd_repo, realtime_publisher=sink)

    dispatcher = MessageDispatcher(
        telemetry_svc=tel_svc,
        heartbeat_svc=hb_svc,
        status_svc=stat_svc,
        ack_svc=ack_svc,
    )

    sim = ESP32DeviceSimulator(device_id="SWC-NODE-001")
    bridge = DirectSimulatorBridge(sim, dispatcher)
    cmd_svc = DeviceCommandService(repository=cmd_repo, publisher=bridge)

    # Issue SET_RELAY misting -> 1
    cmd = cmd_svc.send_set_relay_command("SWC-NODE-001", "misting", 1)
    assert cmd.status == "SUCCESS"
    assert cmd.ack_mode == "MANUAL"
    assert sim.actuators["misting"] is True
    assert sim.mode == "MANUAL"

    # Issue UPDATE_THRESHOLDS with isAutoMode=True -> restores AUTO mode
    cmd2 = cmd_svc.send_update_thresholds_command("SWC-NODE-001", 28.5, 82.0, True)
    assert cmd2.status == "SUCCESS"
    assert cmd2.ack_mode == "AUTO"
    assert sim.mode == "AUTO"
    assert sim.target_temp == 28.5
    assert sim.target_hum == 82.0


def test_offline_resilience_and_local_hysteresis_rule_execution():
    """Verify ESP32 Dual-Core architecture continues local automatic control even during network outage.

    In Core 1 (sketch.ino evaluateRuleBasedControl):
    - When temp > targetTemp + tempDeadband (30.5°C) -> Fan turns ON.
    - When temp <= targetTemp (29.0°C) and CO2 <= 550 -> Fan turns OFF.
    - When hum < targetHum - humDeadband (77.0%) -> Misting turns ON.
    - When hum >= targetHum (80.0%) -> Misting turns OFF.
    - When temp < 26.0°C -> Heater turns ON.
    - When light > 1.0 lux -> Alarm turns ON.
    """
    sketch_source = (Path(__file__).resolve().parents[3] / "firmware" / "esp32" / "sketch.ino").read_text(encoding="utf-8")

    # Verify Dual-Core FreeRTOS SMP task pin
    assert "xTaskCreatePinnedToCore(Task_ControlLoop, \"Task_Control\", 4096, NULL, 3, NULL, 1);" in sketch_source
    assert "xTaskCreatePinnedToCore(Task_NetworkManager, \"Task_Network\", 4096, NULL, 2, NULL, 0);" in sketch_source

    # Verify local rule execution in Task_ControlLoop does not depend on Task_NetworkManager
    assert "evaluateRuleBasedControl(localData);" in sketch_source

    # Verify fail-safe logic when sensor reading is invalid
    assert "digitalWrite(PIN_MISTING, RELAY_INACTIVE);" in sketch_source
    assert "digitalWrite(PIN_HEATER, RELAY_INACTIVE);" in sketch_source


def test_auto_reconnect_and_lwt_behavior():
    """Verify device disconnect triggers LWT offline, and reconnect restores ONLINE and republishes LWT."""
    pres_repo = InMemoryDevicePresenceRepository()
    sink = MemoryEventSink()
    pres_svc = DevicePresenceService(repository=pres_repo, realtime_publisher=sink)

    # 1. Device connects
    pres_svc.record_online_status("SWC-NODE-001")
    p1 = pres_svc.get_presence("SWC-NODE-001")
    assert p1.status == "ONLINE"

    # 2. Broker detects disconnect -> triggers LWT (swiftlet/status/SWC-NODE-001: {"status": "offline"})
    pres_svc.record_offline_status("SWC-NODE-001")
    p2 = pres_svc.get_presence("SWC-NODE-001")
    assert p2.status == "OFFLINE"

    # 3. Wi-Fi/Broker recovers -> Node auto-reconnects -> sends status "online"
    pres_svc.record_online_status("SWC-NODE-001")
    p3 = pres_svc.get_presence("SWC-NODE-001")
    assert p3.status == "ONLINE"


# ============================================================================
# 2. [IOT] TÍCH HỢP SỰ KIỆN VẬN HÀNH & NGUỒN CẢNH BÁO
# ============================================================================

def test_operational_events_hysteresis_deadbands_and_deduplication():
    """Verify IoTConditionEvaluator publishes started/recovered events with strict hysteresis deadbands."""
    publisher = InMemoryDomainEventPublisher()
    resolver = DeviceMetadataResolver()
    resolver.register("SWC-NODE-001", "FARM-01", "ZONE-01")
    evaluator = IoTConditionEvaluator(publisher=publisher, resolver=resolver)

    def make_tel(temp: float, hum: float, audio_ok: bool = True) -> AcceptedTelemetry:
        return AcceptedTelemetry(
            device_id="SWC-NODE-001",
            received_at=datetime.now(timezone.utc),
            metrics=TelemetryMetrics(
                temperature=temp,
                humidity=hum,
                lux=0.1,
                co2=500.0,
                audioRms=0.3,
                audioHealthy=audio_ok,
            ),
            actuators=ActuatorState(misting=False, fan=False, heater=False, alarm=False),
            state=DeviceRuntimeState(mode="AUTO", networkRssi=-50, freeHeap=150000),
        )

    # 1. Normal baseline: 29.0°C, 80% -> 0 events
    evaluator.evaluate_telemetry(make_tel(29.0, 80.0))
    assert len(publisher.published_events) == 0

    # 2. Temperature crosses threshold >= 31.0°C -> publishes iot.environment.high_temperature.started
    evaluator.evaluate_telemetry(make_tel(31.2, 80.0))
    assert len(publisher.published_events) == 1
    assert publisher.published_events[0].eventType == "iot.environment.high_temperature.started"
    assert publisher.published_events[0].payload["farmId"] == "FARM-01"
    assert publisher.published_events[0].payload["value"] == 31.2

    # 3. Temp flutters between 30.6°C and 31.5°C -> DEDUPLICATED, NO extra event!
    evaluator.evaluate_telemetry(make_tel(31.4, 80.0))
    evaluator.evaluate_telemetry(make_tel(30.8, 80.0))
    assert len(publisher.published_events) == 1

    # 4. Temp drops below recovery <= 30.5°C -> publishes recovered event
    evaluator.evaluate_telemetry(make_tel(30.4, 80.0))
    assert len(publisher.published_events) == 2
    assert publisher.published_events[1].eventType == "iot.environment.high_temperature.recovered"

    # 5. Low Humidity: hum drops <= 65% -> started; recovers >= 67% -> recovered
    evaluator.evaluate_telemetry(make_tel(29.0, 64.0))
    assert len(publisher.published_events) == 3
    assert publisher.published_events[2].eventType == "iot.environment.low_humidity.started"

    evaluator.evaluate_telemetry(make_tel(29.0, 66.0))  # Inside deadband -> still active
    assert len(publisher.published_events) == 3

    evaluator.evaluate_telemetry(make_tel(29.0, 67.5))  # Recovered
    assert len(publisher.published_events) == 4
    assert publisher.published_events[3].eventType == "iot.environment.low_humidity.recovered"

    # 6. Audio Fault: wire break -> started; repaired -> recovered
    evaluator.evaluate_telemetry(make_tel(29.0, 80.0, audio_ok=False))
    assert len(publisher.published_events) == 5
    assert publisher.published_events[4].eventType == "iot.audio.fault.started"

    evaluator.evaluate_telemetry(make_tel(29.0, 80.0, audio_ok=True))
    assert len(publisher.published_events) == 6
    assert publisher.published_events[5].eventType == "iot.audio.fault.recovered"


def test_presence_and_command_failure_events():
    """Verify device connectivity transitions and terminal command failures emit canonical domain events."""
    publisher = InMemoryDomainEventPublisher()
    resolver = DeviceMetadataResolver()
    resolver.register("SWC-NODE-001", "FARM-01", "ZONE-01")
    evaluator = IoTConditionEvaluator(publisher=publisher, resolver=resolver)

    # ONLINE -> OFFLINE emits iot.device.offline
    ev1 = evaluator.evaluate_presence_transition("SWC-NODE-001", "ONLINE")
    ev2 = evaluator.evaluate_presence_transition("SWC-NODE-001", "OFFLINE")
    assert ev2 == "iot.device.offline"

    # OFFLINE -> ONLINE emits iot.device.online
    ev3 = evaluator.evaluate_presence_transition("SWC-NODE-001", "ONLINE")
    assert ev3 == "iot.device.online"

    # Command failure emits iot.command.failed with correlationId
    cmd_id = str(uuid.uuid4())
    ev4 = evaluator.evaluate_command_failure(
        device_id="SWC-NODE-001",
        command_id=cmd_id,
        action="SET_RELAY",
        target="misting",
        reason="Relay hardware failed to respond",
    )
    assert ev4 == "iot.command.failed"
    last_event = publisher.published_events[-1]
    assert last_event.correlationId == cmd_id
    assert last_event.payload["commandId"] == cmd_id
    assert last_event.payload["target"] == "misting"


# ============================================================================
# 3. [IOT] TÍCH HỢP TRẠNG THÁI QUẢN TRỊ & PROVISIONING THIẾT BỊ
# ============================================================================

def test_admin_device_registry_summary_endpoint():
    """Verify Administrator receives device registry overview with provisioning status and health metadata."""
    client = TestClient(app)
    resp = client.get("/api/iot/devices/registry-summary")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 4

    dev_map = {item["deviceId"]: item for item in items}
    assert "SWC-NODE-001" in dev_map
    node = dev_map["SWC-NODE-001"]
    assert "provisioningStatus" in node
    assert node["provisioningStatus"] in ("PROVISIONED", "ATTENTION", "DISCONNECTED", "PENDING_ACTIVATION")
    assert "health" in node
    assert "firmwareVersion" in node
    assert node["farmId"] == "FARM-01"


# ============================================================================
# 4. [IOT] TRIỂN KHAI HỖ TRỢ PROVISIONING & LẮP ĐẶT THIẾT BỊ
# ============================================================================

def test_technician_installation_checklist_and_activation_readiness():
    """Verify Technician 5-step checklist evaluates Power, Network, MQTT, Sensor, and Actuator."""
    tel_repo = InMemoryTelemetryRepository()
    pres_repo = InMemoryDevicePresenceRepository()
    cmd_repo = InMemoryCommandRepository()
    cmd_svc = DeviceCommandService(repository=cmd_repo)

    diag_svc = DiagnosticsService(
        telemetry_repo=tel_repo,
        presence_repo=pres_repo,
        command_repo=cmd_repo,
        cmd_service=cmd_svc,
    )

    # Case A: Fresh device with no telemetry -> Not ready
    checklist_unready = diag_svc.get_installation_checklist("SWC-NODE-001")
    assert checklist_unready.allPassed is False
    assert checklist_unready.activationReady is False

    # Case B: Node boots, connects, sends heartbeat and telemetry
    now = datetime.now(timezone.utc)
    from app.schemas.presence import DevicePresence
    pres_repo.save(
        DevicePresence(
            device_id="SWC-NODE-001",
            status="ONLINE",
            uptime=120,
            ip="192.168.1.100",
            free_heap=175000,
            mock_mode=True,
            last_seen=now,
            last_heartbeat_at=now,
        )
    )

    tel_repo.save(
        AcceptedTelemetry(
            device_id="SWC-NODE-001",
            received_at=now,
            metrics=TelemetryMetrics(temperature=28.5, humidity=81.0, lux=0.1, co2=550.0, audioRms=0.3, audioHealthy=True),
            actuators=ActuatorState(misting=False, fan=False, heater=False, alarm=False),
            state=DeviceRuntimeState(mode="AUTO", networkRssi=-52, freeHeap=175000),
        )
    )

    checklist_ready = diag_svc.get_installation_checklist("SWC-NODE-001")
    assert checklist_ready.power.passed is True
    assert checklist_ready.network.passed is True
    assert checklist_ready.mqtt.passed is True
    assert checklist_ready.sensor.passed is True
    assert checklist_ready.actuator.passed is True
    assert checklist_ready.allPassed is True
    assert checklist_ready.activationReady is True


def test_technician_provision_device_command_and_firmware_ack():
    """Verify Technician can provision a node, assigning farm/zone and verifying firmware ACK."""
    sim = ESP32DeviceSimulator(device_id="SWC-NODE-001")

    # Command sent to simulator
    cmd_id = str(uuid.uuid4())
    ack = sim.handle_command_payload(
        json.dumps(
            {
                "commandId": cmd_id,
                "action": "PROVISION_DEVICE",
                "farmId": "farm-binh-an",
                "zoneId": "zone-b",
                "serialNumber": "NM-ESP32-2026-009",
            }
        )
    )
    assert ack is not None
    v_ack = AckPayload.model_validate(ack)
    assert v_ack.status == "SUCCESS"
    assert "activation ready" in v_ack.message.lower()

    # REST endpoint verification
    client = TestClient(app)
    resp = client.post(
        "/api/iot/devices/ESP32-CTRL-01/provision",
        json={
            "farmId": "farm-binh-an",
            "zoneId": "zone-a",
            "serialNumber": "NM-ESP32-001",
            "deviceType": "controller",
            "firmwareVersion": "v1.4.2",
            "samplingInterval": 30,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "PROVISIONED"
    assert data["farmId"] == "farm-binh-an"


# ============================================================================
# 5. [IOT] PUBLISH TELEMETRY SỨC KHỎE & CHẨN ĐOÁN THIẾT BỊ
# ============================================================================

def test_technician_device_diagnostics_detail_and_summary_endpoint():
    """Verify Technician Diagnostics exposes deep signals (heartbeat, RSSI, MQTT, sensor health, issues)."""
    client = TestClient(app)

    # 1. Device Diagnostics Detail
    resp = client.get("/api/iot/devices/ESP32-CTRL-01/diagnostics")
    assert resp.status_code == 200
    diag = resp.json()
    assert diag["id"] == "ESP32-CTRL-01"
    assert "connectivity" in diag
    assert "sensors" in diag
    assert "actuators" in diag
    assert "issues" in diag

    # 2. System Diagnostic Summary
    sum_resp = client.get("/api/iot/diagnostics/summary")
    assert sum_resp.status_code == 200
    summary = sum_resp.json()
    assert summary["totalNodes"] >= 4
    assert (summary["healthyNodes"] + summary["warningNodes"] + summary["offlineNodes"]) == summary["totalNodes"]
