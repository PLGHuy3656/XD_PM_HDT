"""IoT Condition Evaluator & Alert State Machine (CP7.2).

Enforces hysteresis deadbands to eliminate flapping around thresholds:
- High Temperature: >= 31.0°C started, <= 30.5°C recovered
- Low Temperature: <= 25.0°C started, >= 25.5°C recovered
- High Humidity: >= 85.0% started, <= 83.0% recovered
- Low Humidity: <= 65.0% started, >= 67.0% recovered
- Audio Fault: audioHealthy true -> false started, false -> true recovered
- Presence: ONLINE -> OFFLINE: iot.device.offline once
            OFFLINE -> ONLINE: iot.device.online once
- Command Failure: terminal failure -> iot.command.failed once
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any

from app.domain_events.canonical import CanonicalDomainEvent
from app.domain_events.metadata_resolver import (
    DeviceMetadataResolver,
    default_metadata_resolver,
)
from app.domain_events.publisher import (
    DomainEventPublisher,
    default_domain_event_publisher,
)
from app.schemas.telemetry import AcceptedTelemetry

logger = logging.getLogger("iot_service.evaluator")

# Threshold & Deadband Constants (Frozen CP7.2)
HIGH_TEMP_THRESHOLD = 31.0
TEMP_DEADBAND = 0.5
HIGH_TEMP_RECOVERY = HIGH_TEMP_THRESHOLD - TEMP_DEADBAND  # 30.5

LOW_TEMP_THRESHOLD = 25.0
LOW_TEMP_RECOVERY = LOW_TEMP_THRESHOLD + TEMP_DEADBAND   # 25.5

HIGH_HUM_THRESHOLD = 85.0
HUM_DEADBAND = 2.0
HIGH_HUM_RECOVERY = HIGH_HUM_THRESHOLD - HUM_DEADBAND    # 83.0

LOW_HUM_THRESHOLD = 65.0
LOW_HUM_RECOVERY = LOW_HUM_THRESHOLD + HUM_DEADBAND     # 67.0


@dataclass
class DeviceAlertState:
    """State tracking for a single device to eliminate repeated alerts and flapping."""
    high_temp_active: bool = False
    low_temp_active: bool = False
    high_hum_active: bool = False
    low_hum_active: bool = False
    audio_fault_active: bool = False
    last_presence: str | None = None


class IoTConditionEvaluator:
    """Evaluates telemetry, presence, and commands to publish domain alert events."""

    def __init__(
        self,
        publisher: DomainEventPublisher | None = None,
        resolver: DeviceMetadataResolver | None = None,
    ):
        self.publisher: DomainEventPublisher = publisher or default_domain_event_publisher
        self.resolver: DeviceMetadataResolver = resolver or default_metadata_resolver
        self._states: dict[str, DeviceAlertState] = {}

    def _get_state(self, device_id: str) -> DeviceAlertState:
        if device_id not in self._states:
            self._states[device_id] = DeviceAlertState()
        return self._states[device_id]

    def _emit(
        self,
        event_type: str,
        device_id: str,
        occurred_at: datetime,
        payload_extra: dict[str, Any],
        correlation_id: str | None = None,
    ) -> bool:
        location = self.resolver.resolve(device_id)
        if location is None:
            logger.warning(
                "[METADATA ISOLATION] Device '%s' not registered to any farm/zone; dropping event '%s'",
                device_id,
                event_type,
            )
            return False

        payload = {
            "farmId": location.farm_id,
            "zoneId": location.zone_id,
            "deviceId": device_id,
            **payload_extra,
        }

        iso_time = occurred_at.isoformat().replace("+00:00", "Z")
        event = CanonicalDomainEvent(
            eventType=event_type,
            occurredAt=iso_time,
            correlationId=correlation_id,
            payload=payload,
        )

        return self.publisher.publish(event)

    def evaluate_telemetry(self, telemetry: AcceptedTelemetry) -> list[str]:
        """Evaluates telemetry metrics against environmental and audio conditions.

        Returns list of emitted eventType strings.
        """
        device_id = telemetry.device_id
        metrics = telemetry.metrics
        now = telemetry.received_at
        state = self._get_state(device_id)
        emitted: list[str] = []

        temp = metrics.temperature
        hum = metrics.humidity
        audio_ok = metrics.audioHealthy

        # 1. High Temperature Condition
        if not state.high_temp_active:
            if temp >= HIGH_TEMP_THRESHOLD:
                state.high_temp_active = True
                ev = "iot.environment.high_temperature.started"
                if self._emit(ev, device_id, now, {
                    "metric": "temperature",
                    "value": round(temp, 2),
                    "threshold": HIGH_TEMP_THRESHOLD,
                    "unit": "C",
                }):
                    emitted.append(ev)
        else:
            if temp <= HIGH_TEMP_RECOVERY:
                state.high_temp_active = False
                ev = "iot.environment.high_temperature.recovered"
                if self._emit(ev, device_id, now, {
                    "metric": "temperature",
                    "value": round(temp, 2),
                    "threshold": HIGH_TEMP_RECOVERY,
                    "unit": "C",
                }):
                    emitted.append(ev)

        # 2. Low Temperature Condition
        if not state.low_temp_active:
            if temp <= LOW_TEMP_THRESHOLD:
                state.low_temp_active = True
                ev = "iot.environment.low_temperature.started"
                if self._emit(ev, device_id, now, {
                    "metric": "temperature",
                    "value": round(temp, 2),
                    "threshold": LOW_TEMP_THRESHOLD,
                    "unit": "C",
                }):
                    emitted.append(ev)
        else:
            if temp >= LOW_TEMP_RECOVERY:
                state.low_temp_active = False
                ev = "iot.environment.low_temperature.recovered"
                if self._emit(ev, device_id, now, {
                    "metric": "temperature",
                    "value": round(temp, 2),
                    "threshold": LOW_TEMP_RECOVERY,
                    "unit": "C",
                }):
                    emitted.append(ev)

        # 3. High Humidity Condition
        if not state.high_hum_active:
            if hum >= HIGH_HUM_THRESHOLD:
                state.high_hum_active = True
                ev = "iot.environment.high_humidity.started"
                if self._emit(ev, device_id, now, {
                    "metric": "humidity",
                    "value": round(hum, 2),
                    "threshold": HIGH_HUM_THRESHOLD,
                    "unit": "%",
                }):
                    emitted.append(ev)
        else:
            if hum <= HIGH_HUM_RECOVERY:
                state.high_hum_active = False
                ev = "iot.environment.high_humidity.recovered"
                if self._emit(ev, device_id, now, {
                    "metric": "humidity",
                    "value": round(hum, 2),
                    "threshold": HIGH_HUM_RECOVERY,
                    "unit": "%",
                }):
                    emitted.append(ev)

        # 4. Low Humidity Condition
        if not state.low_hum_active:
            if hum <= LOW_HUM_THRESHOLD:
                state.low_hum_active = True
                ev = "iot.environment.low_humidity.started"
                if self._emit(ev, device_id, now, {
                    "metric": "humidity",
                    "value": round(hum, 2),
                    "threshold": LOW_HUM_THRESHOLD,
                    "unit": "%",
                }):
                    emitted.append(ev)
        else:
            if hum >= LOW_HUM_RECOVERY:
                state.low_hum_active = False
                ev = "iot.environment.low_humidity.recovered"
                if self._emit(ev, device_id, now, {
                    "metric": "humidity",
                    "value": round(hum, 2),
                    "threshold": LOW_HUM_RECOVERY,
                    "unit": "%",
                }):
                    emitted.append(ev)

        # 5. Audio Fault Condition
        if not state.audio_fault_active:
            if not audio_ok:
                state.audio_fault_active = True
                ev = "iot.audio.fault.started"
                if self._emit(ev, device_id, now, {
                    "metric": "audio",
                    "value": "FAULT",
                    "audioRms": round(metrics.audioRms, 2),
                    "reason": "Acoustic sensor detected audio wire break or speaker silence",
                }):
                    emitted.append(ev)
        else:
            if audio_ok:
                state.audio_fault_active = False
                ev = "iot.audio.fault.recovered"
                if self._emit(ev, device_id, now, {
                    "metric": "audio",
                    "value": "NORMAL",
                    "audioRms": round(metrics.audioRms, 2),
                    "reason": "Swiftlet nesting audio sound restored to healthy level",
                }):
                    emitted.append(ev)

        return emitted

    def evaluate_presence_transition(
        self,
        device_id: str,
        new_status: str,
        timestamp: datetime | None = None,
    ) -> str | None:
        """Evaluates ONLINE <-> OFFLINE discrete transitions.

        Routine heartbeats while ONLINE do not produce events.
        """
        now = timestamp or datetime.now(timezone.utc)
        state = self._get_state(device_id)
        prev = state.last_presence

        if prev == new_status:
            return None

        state.last_presence = new_status

        if prev == "ONLINE" and new_status in ("OFFLINE", "STALE"):
            ev = "iot.device.offline"
            if self._emit(ev, device_id, now, {
                "status": "OFFLINE",
                "reason": "Device heartbeat timed out or LWT disconnected",
            }):
                return ev
        elif prev in ("OFFLINE", "STALE", None) and new_status == "ONLINE":
            ev = "iot.device.online"
            if self._emit(ev, device_id, now, {
                "status": "ONLINE",
                "reason": "Device status online or heartbeat received",
            }):
                return ev

        return None

    def evaluate_command_failure(
        self,
        device_id: str,
        command_id: str,
        action: str,
        target: str | None = None,
        reason: str | None = None,
        timestamp: datetime | None = None,
    ) -> str | None:
        """Emits iot.command.failed on terminal failure (MQTT publish failure or device FAILED ACK)."""
        now = timestamp or datetime.now(timezone.utc)
        ev = "iot.command.failed"
        if self._emit(
            ev,
            device_id,
            now,
            {
                "commandId": command_id,
                "action": action,
                "target": target or "system",
                "reason": reason or "Command execution failed or timed out on edge node",
            },
            correlation_id=command_id,
        ):
            return ev
        return None


default_condition_evaluator = IoTConditionEvaluator()
