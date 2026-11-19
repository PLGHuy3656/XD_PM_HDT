from datetime import datetime, timezone
from app.config.alert_rules import InMemoryAlertRuleConfigProvider
from app.domain.enums import AlertEventType, AlertSeverity, AlertSource, AlertStatus
from app.schemas.canonical import Alert
from app.schemas.events import (
    AIAlertInputEvent,
    IoTTelemetryAlertInputEvent,
    IoTPresenceAlertInputEvent,
    IoTCommandAlertInputEvent,
)
from app.services.alert_rule_engine import AlertRuleEngine


def test_ai_predator_rule(rule_engine: AlertRuleEngine):
    now = datetime(2026, 10, 27, 12, 0, 0, tzinfo=timezone.utc)
    event = AIAlertInputEvent(
        event_type=AlertEventType.PREDATOR_DETECTED,
        farm_id="farm_001",
        zone_id="zone_01",
        camera_id="cam_east_01",
        timestamp=now,
        confidence=0.94,
        predator_type="owl",
        snapshot_url="http://127.0.0.1:8003/api/v1/ai/snapshots/snap_01.jpg",
    )

    triggers = rule_engine.evaluate_ai_event(event)
    assert len(triggers) == 1
    trig = triggers[0]
    assert trig.event_type == AlertEventType.PREDATOR_DETECTED
    assert trig.severity == AlertSeverity.CRITICAL
    assert trig.source == AlertSource.AI
    assert trig.camera_id == "cam_east_01"
    assert trig.snapshot_url == "http://127.0.0.1:8003/api/v1/ai/snapshots/snap_01.jpg"
    assert "owl" in trig.title.lower()


def test_temperature_hysteresis_deadband(rule_engine: AlertRuleEngine):
    # farm_001 configured in conftest: high=31.0, recovery=30.5; low=27.0, recovery=27.5
    now = datetime(2026, 10, 27, 12, 10, 0, tzinfo=timezone.utc)

    # 1. Temperature exceeds 31.0C -> trigger
    t_event1 = IoTTelemetryAlertInputEvent(
        device_id="SWC-NODE-001",
        farm_id="farm_001",
        zone_id="zone_01",
        timestamp=now,
        temperature=31.2,
        humidity=75.0,
        audio_healthy=True,
    )
    trigs, resolves = rule_engine.evaluate_telemetry_event(t_event1, active_alert_lookup=lambda et: None)
    assert len(trigs) == 1
    assert trigs[0].event_type == AlertEventType.HIGH_TEMPERATURE
    assert len(resolves) == 0

    # Simulate active alert exists
    active_high_alert = Alert(
        alert_id="alt_high_temp_01",
        farm_id="farm_001",
        zone_id="zone_01",
        device_id="SWC-NODE-001",
        event_type=AlertEventType.HIGH_TEMPERATURE,
        severity=AlertSeverity.HIGH,
        status=AlertStatus.OPEN,
        source=AlertSource.IOT_ENVIRONMENT,
        title="High Temp",
        message="Temp high",
    )

    def active_lookup(et: AlertEventType):
        if et == AlertEventType.HIGH_TEMPERATURE:
            return active_high_alert
        return None

    # 2. Temperature drops to 30.8C (in deadband: 30.5 < 30.8 < 31.0) -> neither triggers new nor resolves
    t_event2 = IoTTelemetryAlertInputEvent(
        device_id="SWC-NODE-001",
        farm_id="farm_001",
        zone_id="zone_01",
        timestamp=now,
        temperature=30.8,
        humidity=75.0,
        audio_healthy=True,
    )
    trigs2, resolves2 = rule_engine.evaluate_telemetry_event(t_event2, active_alert_lookup=active_lookup)
    assert len(trigs2) == 0
    assert len(resolves2) == 0

    # 3. Temperature drops to 30.4C (<= 30.5 recovery threshold) -> auto-resolves!
    t_event3 = IoTTelemetryAlertInputEvent(
        device_id="SWC-NODE-001",
        farm_id="farm_001",
        zone_id="zone_01",
        timestamp=now,
        temperature=30.4,
        humidity=75.0,
        audio_healthy=True,
    )
    trigs3, resolves3 = rule_engine.evaluate_telemetry_event(t_event3, active_alert_lookup=active_lookup)
    assert len(trigs3) == 0
    assert len(resolves3) == 1
    assert resolves3[0].alert_to_resolve.alert_id == "alt_high_temp_01"
    assert "30.4" in resolves3[0].resolution_note


def test_humidity_hysteresis_deadband(rule_engine: AlertRuleEngine):
    # farm_001 high_humidity=85.0, recovery=82.0
    now = datetime(2026, 10, 27, 12, 15, 0, tzinfo=timezone.utc)

    # Trigger high humidity
    h_event1 = IoTTelemetryAlertInputEvent(
        device_id="SWC-NODE-001",
        farm_id="farm_001",
        zone_id="zone_01",
        timestamp=now,
        temperature=28.0,
        humidity=86.5,
    )
    trigs1, resolves1 = rule_engine.evaluate_telemetry_event(h_event1, active_alert_lookup=lambda et: None)
    assert len(trigs1) == 1
    assert trigs1[0].event_type == AlertEventType.HIGH_HUMIDITY

    active_h_alert = Alert(
        alert_id="alt_high_hum_01",
        farm_id="farm_001",
        zone_id="zone_01",
        device_id="SWC-NODE-001",
        event_type=AlertEventType.HIGH_HUMIDITY,
        severity=AlertSeverity.MEDIUM,
        status=AlertStatus.OPEN,
        source=AlertSource.IOT_ENVIRONMENT,
        title="High Humidity",
        message="Hum high",
    )

    # Deadband check: 83.5%
    h_event2 = IoTTelemetryAlertInputEvent(
        device_id="SWC-NODE-001",
        farm_id="farm_001",
        zone_id="zone_01",
        timestamp=now,
        temperature=28.0,
        humidity=83.5,
    )
    trigs2, resolves2 = rule_engine.evaluate_telemetry_event(
        h_event2, active_alert_lookup=lambda et: active_h_alert if et == AlertEventType.HIGH_HUMIDITY else None
    )
    assert len(trigs2) == 0
    assert len(resolves2) == 0

    # Recovery check: 81.5% <= 82.0%
    h_event3 = IoTTelemetryAlertInputEvent(
        device_id="SWC-NODE-001",
        farm_id="farm_001",
        zone_id="zone_01",
        timestamp=now,
        temperature=28.0,
        humidity=81.5,
    )
    trigs3, resolves3 = rule_engine.evaluate_telemetry_event(
        h_event3, active_alert_lookup=lambda et: active_h_alert if et == AlertEventType.HIGH_HUMIDITY else None
    )
    assert len(trigs3) == 0
    assert len(resolves3) == 1
    assert resolves3[0].alert_to_resolve.alert_id == "alt_high_hum_01"


def test_audio_fault_and_recovery(rule_engine: AlertRuleEngine):
    now = datetime(2026, 10, 27, 12, 20, 0, tzinfo=timezone.utc)

    # 1. Audio fault occurs
    event_fault = IoTTelemetryAlertInputEvent(
        device_id="SWC-NODE-001",
        farm_id="farm_001",
        zone_id="zone_01",
        timestamp=now,
        audio_healthy=False,
    )
    trigs, resolves = rule_engine.evaluate_telemetry_event(event_fault, active_alert_lookup=lambda et: None)
    assert len(trigs) == 1
    assert trigs[0].event_type == AlertEventType.AUDIO_FAULT

    active_audio_alert = Alert(
        alert_id="alt_audio_01",
        farm_id="farm_001",
        zone_id="zone_01",
        device_id="SWC-NODE-001",
        event_type=AlertEventType.AUDIO_FAULT,
        severity=AlertSeverity.HIGH,
        status=AlertStatus.OPEN,
        source=AlertSource.IOT_DEVICE,
        title="Audio Fault",
        message="Mic failure",
    )

    # 2. Audio recovers
    event_healthy = IoTTelemetryAlertInputEvent(
        device_id="SWC-NODE-001",
        farm_id="farm_001",
        zone_id="zone_01",
        timestamp=now,
        audio_healthy=True,
    )
    trigs2, resolves2 = rule_engine.evaluate_telemetry_event(
        event_healthy,
        active_alert_lookup=lambda et: active_audio_alert if et == AlertEventType.AUDIO_FAULT else None,
    )
    assert len(trigs2) == 0
    assert len(resolves2) == 1
    assert resolves2[0].alert_to_resolve.alert_id == "alt_audio_01"


def test_presence_offline_and_recovery(rule_engine: AlertRuleEngine):
    now = datetime(2026, 10, 27, 12, 25, 0, tzinfo=timezone.utc)

    # 1. Device goes OFFLINE -> trigger
    off_event = IoTPresenceAlertInputEvent(
        device_id="SWC-NODE-001",
        farm_id="farm_001",
        zone_id="zone_01",
        status="OFFLINE",
        timestamp=now,
    )
    trigs, resolves = rule_engine.evaluate_presence_event(off_event, active_alert_lookup=lambda et: None)
    assert len(trigs) == 1
    assert trigs[0].event_type == AlertEventType.DEVICE_OFFLINE
    assert trigs[0].severity == AlertSeverity.CRITICAL

    active_offline_alert = Alert(
        alert_id="alt_off_01",
        farm_id="farm_001",
        zone_id="zone_01",
        device_id="SWC-NODE-001",
        event_type=AlertEventType.DEVICE_OFFLINE,
        severity=AlertSeverity.CRITICAL,
        status=AlertStatus.OPEN,
        source=AlertSource.IOT_DEVICE,
        title="Device Offline",
        message="Device offline",
    )

    # 2. Device reconnects ONLINE -> auto-resolve
    on_event = IoTPresenceAlertInputEvent(
        device_id="SWC-NODE-001",
        farm_id="farm_001",
        zone_id="zone_01",
        status="ONLINE",
        timestamp=now,
    )
    trigs2, resolves2 = rule_engine.evaluate_presence_event(
        on_event,
        active_alert_lookup=lambda et: active_offline_alert if et == AlertEventType.DEVICE_OFFLINE else None,
    )
    assert len(trigs2) == 0
    assert len(resolves2) == 1
    assert resolves2[0].alert_to_resolve.alert_id == "alt_off_01"


def test_command_failure_strict_filter(rule_engine: AlertRuleEngine):
    now = datetime(2026, 10, 27, 12, 30, 0, tzinfo=timezone.utc)

    # Should NOT trigger on non-failure statuses
    for ok_status in ["PENDING", "PUBLISHED", "SUCCESS", "ACKNOWLEDGED"]:
        ev = IoTCommandAlertInputEvent(
            command_id="cmd_01",
            device_id="SWC-NODE-001",
            farm_id="farm_001",
            command_type="SET_RELAY",
            status=ok_status,
            timestamp=now,
        )
        assert len(rule_engine.evaluate_command_event(ev)) == 0

    # MUST trigger on terminal failure statuses: FAILED, ERROR, TIMEOUT
    for fail_status in ["FAILED", "ERROR", "TIMEOUT"]:
        ev = IoTCommandAlertInputEvent(
            command_id=f"cmd_{fail_status}",
            device_id="SWC-NODE-001",
            farm_id="farm_001",
            command_type="SET_RELAY",
            status=fail_status,
            failure_reason="Actuator unresponsive",
            timestamp=now,
        )
        trigs = rule_engine.evaluate_command_event(ev)
        assert len(trigs) == 1
        assert trigs[0].event_type == AlertEventType.COMMAND_FAILED
        assert trigs[0].severity == AlertSeverity.HIGH
        assert "Actuator unresponsive" in trigs[0].message
