"""Domain event mapper translating canonical RabbitMQ envelopes to NotificationService calls (CP7.4)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.domain.enums import AlertEventType, AlertSeverity, AlertSource
from app.infrastructure.rabbitmq.envelope import CanonicalEnvelope, PermanentEnvelopeError
from app.schemas.events import (
    AIAlertInputEvent,
    IoTCommandAlertInputEvent,
    IoTPresenceAlertInputEvent,
)
from app.services.notification_service import NotificationService

logger = logging.getLogger("notification_service.infrastructure.rabbitmq.mapper")


def _parse_utc_iso8601(dt_str: str) -> datetime:
    try:
        candidate = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(candidate)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


class EventMapper:
    """Translates canonical domain envelopes into typed domain calls on NotificationService."""

    def __init__(self, service: NotificationService) -> None:
        self.service = service

    def process_envelope(self, envelope: CanonicalEnvelope) -> None:
        """Dispatches validated envelope to the appropriate application handler."""
        event_type = envelope.event_type
        payload = envelope.payload
        occurred_at = _parse_utc_iso8601(envelope.occurred_at)

        # 1. AI Predator Detected
        if event_type == "ai.predator.detected":
            self._map_ai_predator(envelope, payload, occurred_at)
            return

        # 2. IoT Environment High Temperature
        if event_type in ("iot.environment.high_temperature.started", "iot.environment.high_temperature.recovered"):
            self._map_environment_transition(
                envelope=envelope,
                payload=payload,
                occurred_at=occurred_at,
                event_type=AlertEventType.HIGH_TEMPERATURE,
                severity=AlertSeverity.HIGH,
                title_prefix="High Temperature",
                unit="°C",
            )
            return

        # 3. IoT Environment Low Temperature
        if event_type in ("iot.environment.low_temperature.started", "iot.environment.low_temperature.recovered"):
            self._map_environment_transition(
                envelope=envelope,
                payload=payload,
                occurred_at=occurred_at,
                event_type=AlertEventType.LOW_TEMPERATURE,
                severity=AlertSeverity.MEDIUM,
                title_prefix="Low Temperature",
                unit="°C",
            )
            return

        # 4. IoT Environment High Humidity
        if event_type in ("iot.environment.high_humidity.started", "iot.environment.high_humidity.recovered"):
            self._map_environment_transition(
                envelope=envelope,
                payload=payload,
                occurred_at=occurred_at,
                event_type=AlertEventType.HIGH_HUMIDITY,
                severity=AlertSeverity.MEDIUM,
                title_prefix="High Humidity",
                unit="%",
            )
            return

        # 5. IoT Environment Low Humidity
        if event_type in ("iot.environment.low_humidity.started", "iot.environment.low_humidity.recovered"):
            self._map_environment_transition(
                envelope=envelope,
                payload=payload,
                occurred_at=occurred_at,
                event_type=AlertEventType.LOW_HUMIDITY,
                severity=AlertSeverity.MEDIUM,
                title_prefix="Low Humidity",
                unit="%",
            )
            return

        # 6. IoT Audio Fault
        if event_type in ("iot.audio.fault.started", "iot.audio.fault.recovered"):
            self._map_audio_transition(envelope, payload, occurred_at)
            return

        # 7. IoT Device Presence (ONLINE / OFFLINE)
        if event_type in ("iot.device.offline", "iot.device.online"):
            self._map_presence(envelope, payload, occurred_at)
            return

        # 8. IoT Command Failed
        if event_type == "iot.command.failed":
            self._map_command_failed(envelope, payload, occurred_at)
            return

        raise PermanentEnvelopeError(f"Unhandled canonical eventType: '{event_type}'")

    # -------------------------------------------------------------------------
    # Mapping Helpers
    # -------------------------------------------------------------------------

    def _map_ai_predator(
        self,
        envelope: CanonicalEnvelope,
        payload: Dict[str, Any],
        occurred_at: datetime,
    ) -> None:
        camera_id = payload.get("cameraId")
        farm_id = payload.get("farmId")
        if not camera_id or not farm_id:
            raise PermanentEnvelopeError("ai.predator.detected payload missing required cameraId or farmId")

        pred_cls = payload.get("predatorClass", "Unknown")
        confidence = payload.get("confidence")
        snapshot_ref = payload.get("snapshotRef")
        bbox = payload.get("bbox")

        event = AIAlertInputEvent(
            event_id=envelope.event_id,
            event_type=AlertEventType.PREDATOR_DETECTED,
            camera_id=camera_id,
            farm_id=farm_id,
            zone_id=payload.get("zoneId"),
            detected_at=occurred_at,
            timestamp=occurred_at,
            predator_type=pred_cls,
            confidence=confidence,
            bbox=bbox,
            snapshot_url=snapshot_ref,
        )
        self.service.handle_ai_event(event)

    def _map_environment_transition(
        self,
        envelope: CanonicalEnvelope,
        payload: Dict[str, Any],
        occurred_at: datetime,
        event_type: AlertEventType,
        severity: AlertSeverity,
        title_prefix: str,
        unit: str,
    ) -> None:
        device_id = payload.get("deviceId")
        farm_id = payload.get("farmId")
        if not device_id or not farm_id:
            raise PermanentEnvelopeError(f"{envelope.event_type} payload missing required deviceId or farmId")

        is_recovery = envelope.event_type.endswith(".recovered")
        val = payload.get("value")
        thr = payload.get("threshold")

        val_str = f"{val:.1f}{unit}" if isinstance(val, (int, float)) else f"{val}{unit}"
        thr_str = f"{thr:.1f}{unit}" if isinstance(thr, (int, float)) else f"{thr}{unit}"

        if not is_recovery:
            title = f"{title_prefix} Warning"
            msg = f"{title_prefix} warning: current value {val_str} breached threshold ({thr_str})."
        else:
            title = f"{title_prefix} Normalized"
            msg = f"Auto-recovered: {title_prefix} returned to normal ({val_str})."

        self.service.handle_condition_transition(
            event_type=event_type,
            is_recovery=is_recovery,
            farm_id=farm_id,
            zone_id=payload.get("zoneId"),
            device_id=device_id,
            title=title,
            message=msg,
            severity=severity,
            source=AlertSource.IOT_ENVIRONMENT,
            telemetry_snapshot={"value": val, "threshold": thr, "metric": payload.get("metric")},
            resolution_note=msg if is_recovery else None,
            occurred_at=occurred_at,
        )

    def _map_audio_transition(
        self,
        envelope: CanonicalEnvelope,
        payload: Dict[str, Any],
        occurred_at: datetime,
    ) -> None:
        device_id = payload.get("deviceId")
        farm_id = payload.get("farmId")
        if not device_id or not farm_id:
            raise PermanentEnvelopeError("iot.audio.fault.* payload missing required deviceId or farmId")

        is_recovery = envelope.event_type.endswith(".recovered")
        audio_healthy = payload.get("audioHealthy")
        audio_rms = payload.get("audioRms", 0.0)

        if not is_recovery:
            title = "Audio Subsystem Fault"
            msg = f"Audio fault reported on device '{device_id}' (RMS: {audio_rms})."
        else:
            title = "Audio Subsystem Recovered"
            msg = f"Auto-recovered: Audio subsystem on device '{device_id}' reported healthy."

        self.service.handle_condition_transition(
            event_type=AlertEventType.AUDIO_FAULT,
            is_recovery=is_recovery,
            farm_id=farm_id,
            zone_id=payload.get("zoneId"),
            device_id=device_id,
            title=title,
            message=msg,
            severity=AlertSeverity.HIGH,
            source=AlertSource.IOT_DEVICE,
            telemetry_snapshot={"audioHealthy": audio_healthy, "audioRms": audio_rms},
            resolution_note=msg if is_recovery else None,
            occurred_at=occurred_at,
        )

    def _map_presence(
        self,
        envelope: CanonicalEnvelope,
        payload: Dict[str, Any],
        occurred_at: datetime,
    ) -> None:
        device_id = payload.get("deviceId")
        farm_id = payload.get("farmId")
        if not device_id or not farm_id:
            raise PermanentEnvelopeError("iot.device.* payload missing required deviceId or farmId")

        status_norm = "OFFLINE" if envelope.event_type == "iot.device.offline" else "ONLINE"
        event = IoTPresenceAlertInputEvent(
            device_id=device_id,
            farm_id=farm_id,
            zone_id=payload.get("zoneId"),
            status=status_norm,
            updated_at=occurred_at,
            timestamp=occurred_at,
        )
        self.service.handle_presence_event(event)

    def _map_command_failed(
        self,
        envelope: CanonicalEnvelope,
        payload: Dict[str, Any],
        occurred_at: datetime,
    ) -> None:
        device_id = payload.get("deviceId")
        farm_id = payload.get("farmId")
        command_id = payload.get("commandId")
        if not device_id or not farm_id or not command_id:
            raise PermanentEnvelopeError("iot.command.failed payload missing required deviceId, farmId, or commandId")

        action = payload.get("action", "COMMAND")
        failure_reason = payload.get("failureReason", "Execution failure")

        event = IoTCommandAlertInputEvent(
            command_id=command_id,
            device_id=device_id,
            farm_id=farm_id,
            zone_id=payload.get("zoneId"),
            command_type=action,
            status="FAILED",
            failure_reason=failure_reason,
            updated_at=occurred_at,
            timestamp=occurred_at,
        )
        self.service.handle_command_event(event)


__all__ = ["EventMapper"]
