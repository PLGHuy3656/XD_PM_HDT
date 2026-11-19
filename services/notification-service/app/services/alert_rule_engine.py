from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List, Callable
from app.domain.enums import (
    AlertSeverity,
    AlertSource,
    AlertEventType,
)
from app.config.alert_rules import AlertRuleConfigProvider
from app.schemas.canonical import Alert
from app.schemas.events import (
    AIAlertInputEvent,
    IoTTelemetryAlertInputEvent,
    IoTPresenceAlertInputEvent,
    IoTCommandAlertInputEvent,
)


@dataclass
class AlertTrigger:
    farm_id: str
    zone_id: Optional[str]
    device_id: Optional[str]
    camera_id: Optional[str]
    event_type: AlertEventType
    severity: AlertSeverity
    source: AlertSource
    title: str
    message: str
    snapshot_url: Optional[str] = None
    telemetry_snapshot: Optional[dict] = None
    occurred_at: Optional[datetime] = None


@dataclass
class AlertAutoResolveAction:
    alert_to_resolve: Alert
    resolution_note: str
    resolved_at: Optional[datetime] = None


class AlertRuleEngine:
    """Evaluates incoming domain events against farm-configured thresholds and hysteresis deadbands."""

    def __init__(self, config_provider: AlertRuleConfigProvider) -> None:
        self.config_provider = config_provider

    def evaluate_ai_event(
        self,
        event: AIAlertInputEvent,
    ) -> List[AlertTrigger]:
        """Evaluate AI detection / predator events. Predator alerts never auto-resolve."""
        triggers: List[AlertTrigger] = []

        if event.event_type == AlertEventType.PREDATOR_DETECTED:
            predator_label = event.predator_type or "Unknown"
            conf_str = f" (confidence: {event.confidence:.2f})" if event.confidence is not None else ""
            triggers.append(
                AlertTrigger(
                    farm_id=event.farm_id,
                    zone_id=event.zone_id,
                    device_id=None,
                    camera_id=event.camera_id,
                    event_type=AlertEventType.PREDATOR_DETECTED,
                    severity=AlertSeverity.CRITICAL,
                    source=AlertSource.AI,
                    title=f"Predator Detected: {predator_label}",
                    message=f"Predator ({predator_label}) detected at camera '{event.camera_id}'{conf_str}.",
                    snapshot_url=event.snapshot_url,
                    occurred_at=event.timestamp,
                )
            )

        return triggers

    def evaluate_telemetry_event(
        self,
        event: IoTTelemetryAlertInputEvent,
        active_alert_lookup: Callable[[AlertEventType], Optional[Alert]],
    ) -> tuple[List[AlertTrigger], List[AlertAutoResolveAction]]:
        """Evaluate IoT telemetry against thresholds with hysteresis deadbands for auto-recovery."""
        triggers: List[AlertTrigger] = []
        resolves: List[AlertAutoResolveAction] = []
        now = event.timestamp or datetime.now(timezone.utc)

        config = self.config_provider.get_rules_for_farm(event.farm_id)

        telemetry_snap = {
            "temperature": event.temperature,
            "humidity": event.humidity,
            "audioHealthy": event.audio_healthy,
        }

        # 1. Temperature High Evaluation
        if event.temperature is not None:
            active_high = active_alert_lookup(AlertEventType.HIGH_TEMPERATURE)
            if event.temperature >= config.high_temp_celsius:
                triggers.append(
                    AlertTrigger(
                        farm_id=event.farm_id,
                        zone_id=event.zone_id,
                        device_id=event.device_id,
                        camera_id=None,
                        event_type=AlertEventType.HIGH_TEMPERATURE,
                        severity=AlertSeverity.HIGH,
                        source=AlertSource.IOT_ENVIRONMENT,
                        title="High Temperature Warning",
                        message=(
                            f"Temperature {event.temperature:.1f}°C exceeded high threshold "
                            f"({config.high_temp_celsius:.1f}°C)."
                        ),
                        telemetry_snapshot=telemetry_snap,
                        occurred_at=now,
                    )
                )
            elif active_high is not None and event.temperature <= config.high_temp_recovery_celsius:
                resolves.append(
                    AlertAutoResolveAction(
                        alert_to_resolve=active_high,
                        resolution_note=(
                            f"Auto-recovered: Temperature normalized to {event.temperature:.1f}°C "
                            f"(recovery threshold: {config.high_temp_recovery_celsius:.1f}°C)."
                        ),
                        resolved_at=now,
                    )
                )

            # 2. Temperature Low Evaluation
            active_low = active_alert_lookup(AlertEventType.LOW_TEMPERATURE)
            if event.temperature <= config.low_temp_celsius:
                triggers.append(
                    AlertTrigger(
                        farm_id=event.farm_id,
                        zone_id=event.zone_id,
                        device_id=event.device_id,
                        camera_id=None,
                        event_type=AlertEventType.LOW_TEMPERATURE,
                        severity=AlertSeverity.MEDIUM,
                        source=AlertSource.IOT_ENVIRONMENT,
                        title="Low Temperature Warning",
                        message=(
                            f"Temperature {event.temperature:.1f}°C fell below threshold "
                            f"({config.low_temp_celsius:.1f}°C)."
                        ),
                        telemetry_snapshot=telemetry_snap,
                        occurred_at=now,
                    )
                )
            elif active_low is not None and event.temperature >= config.low_temp_recovery_celsius:
                resolves.append(
                    AlertAutoResolveAction(
                        alert_to_resolve=active_low,
                        resolution_note=(
                            f"Auto-recovered: Temperature normalized to {event.temperature:.1f}°C "
                            f"(recovery threshold: {config.low_temp_recovery_celsius:.1f}°C)."
                        ),
                        resolved_at=now,
                    )
                )

        # 3. Humidity High Evaluation
        if event.humidity is not None:
            active_h_high = active_alert_lookup(AlertEventType.HIGH_HUMIDITY)
            if event.humidity >= config.high_humidity_pct:
                triggers.append(
                    AlertTrigger(
                        farm_id=event.farm_id,
                        zone_id=event.zone_id,
                        device_id=event.device_id,
                        camera_id=None,
                        event_type=AlertEventType.HIGH_HUMIDITY,
                        severity=AlertSeverity.MEDIUM,
                        source=AlertSource.IOT_ENVIRONMENT,
                        title="High Humidity Warning",
                        message=(
                            f"Humidity {event.humidity:.1f}% exceeded high threshold "
                            f"({config.high_humidity_pct:.1f}%)."
                        ),
                        telemetry_snapshot=telemetry_snap,
                        occurred_at=now,
                    )
                )
            elif active_h_high is not None and event.humidity <= config.high_humidity_recovery_pct:
                resolves.append(
                    AlertAutoResolveAction(
                        alert_to_resolve=active_h_high,
                        resolution_note=(
                            f"Auto-recovered: Humidity normalized to {event.humidity:.1f}% "
                            f"(recovery threshold: {config.high_humidity_recovery_pct:.1f}%)."
                        ),
                        resolved_at=now,
                    )
                )

            # 4. Humidity Low Evaluation
            active_h_low = active_alert_lookup(AlertEventType.LOW_HUMIDITY)
            if event.humidity <= config.low_humidity_pct:
                triggers.append(
                    AlertTrigger(
                        farm_id=event.farm_id,
                        zone_id=event.zone_id,
                        device_id=event.device_id,
                        camera_id=None,
                        event_type=AlertEventType.LOW_HUMIDITY,
                        severity=AlertSeverity.MEDIUM,
                        source=AlertSource.IOT_ENVIRONMENT,
                        title="Low Humidity Warning",
                        message=(
                            f"Humidity {event.humidity:.1f}% fell below threshold "
                            f"({config.low_humidity_pct:.1f}%)."
                        ),
                        telemetry_snapshot=telemetry_snap,
                        occurred_at=now,
                    )
                )
            elif active_h_low is not None and event.humidity >= config.low_humidity_recovery_pct:
                resolves.append(
                    AlertAutoResolveAction(
                        alert_to_resolve=active_h_low,
                        resolution_note=(
                            f"Auto-recovered: Humidity normalized to {event.humidity:.1f}% "
                            f"(recovery threshold: {config.low_humidity_recovery_pct:.1f}%)."
                        ),
                        resolved_at=now,
                    )
                )

        # 5. Audio Fault Evaluation
        if event.audio_healthy is not None:
            active_audio = active_alert_lookup(AlertEventType.AUDIO_FAULT)
            if event.audio_healthy is False:
                triggers.append(
                    AlertTrigger(
                        farm_id=event.farm_id,
                        zone_id=event.zone_id,
                        device_id=event.device_id,
                        camera_id=None,
                        event_type=AlertEventType.AUDIO_FAULT,
                        severity=AlertSeverity.HIGH,
                        source=AlertSource.IOT_DEVICE,
                        title="Audio Subsystem Fault",
                        message=f"Audio subsystem fault reported on device '{event.device_id}'.",
                        telemetry_snapshot=telemetry_snap,
                        occurred_at=now,
                    )
                )
            elif event.audio_healthy is True and active_audio is not None:
                resolves.append(
                    AlertAutoResolveAction(
                        alert_to_resolve=active_audio,
                        resolution_note="Auto-recovered: Audio subsystem reported healthy.",
                        resolved_at=now,
                    )
                )

        return triggers, resolves

    def evaluate_presence_event(
        self,
        event: IoTPresenceAlertInputEvent,
        active_alert_lookup: Callable[[AlertEventType], Optional[Alert]],
    ) -> tuple[List[AlertTrigger], List[AlertAutoResolveAction]]:
        """Evaluate device presence events. OFFLINE triggers alert; ONLINE auto-resolves."""
        triggers: List[AlertTrigger] = []
        resolves: List[AlertAutoResolveAction] = []
        now = event.timestamp or datetime.now(timezone.utc)
        status_norm = event.status.strip().upper()

        active_offline = active_alert_lookup(AlertEventType.DEVICE_OFFLINE)

        if status_norm == "OFFLINE":
            triggers.append(
                AlertTrigger(
                    farm_id=event.farm_id,
                    zone_id=event.zone_id,
                    device_id=event.device_id,
                    camera_id=None,
                    event_type=AlertEventType.DEVICE_OFFLINE,
                    severity=AlertSeverity.CRITICAL,
                    source=AlertSource.IOT_DEVICE,
                    title="Device Offline",
                    message=f"Device '{event.device_id}' went offline.",
                    occurred_at=now,
                )
            )
        elif status_norm == "ONLINE" and active_offline is not None:
            resolves.append(
                AlertAutoResolveAction(
                    alert_to_resolve=active_offline,
                    resolution_note=f"Auto-recovered: Device '{event.device_id}' reconnected online.",
                    resolved_at=now,
                )
            )

        return triggers, resolves

    def evaluate_command_event(
        self,
        event: IoTCommandAlertInputEvent,
    ) -> List[AlertTrigger]:
        """Evaluate command failure events.

        Strict failure filter: triggers ONLY on FAILED, ERROR, TIMEOUT.
        Never triggers on PENDING, PUBLISHED, SUCCESS, ACKNOWLEDGED.
        Command failure alerts never auto-resolve.
        """
        triggers: List[AlertTrigger] = []
        now = event.timestamp or datetime.now(timezone.utc)
        status_norm = event.status.strip().upper()

        # Terminal failure states only
        if status_norm in ("FAILED", "ERROR", "TIMEOUT"):
            reason_str = f" Reason: {event.failure_reason}" if event.failure_reason else ""
            triggers.append(
                AlertTrigger(
                    farm_id=event.farm_id,
                    zone_id=event.zone_id,
                    device_id=event.device_id,
                    camera_id=None,
                    event_type=AlertEventType.COMMAND_FAILED,
                    severity=AlertSeverity.HIGH,
                    source=AlertSource.IOT_DEVICE,
                    title="Actuator Command Failed",
                    message=(
                        f"Command '{event.command_type}' on device '{event.device_id}' "
                        f"failed ({status_norm}).{reason_str}"
                    ),
                    occurred_at=now,
                )
            )

        return triggers
