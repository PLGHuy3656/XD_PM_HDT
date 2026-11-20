import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Protocol

from app.domain_events.evaluator import (
    IoTConditionEvaluator,
    default_condition_evaluator,
)
from app.mqtt.topics import build_topic
from app.repositories.command_repository import (
    CommandRepository,
    compare_and_update,
    default_command_repository,
)
from app.schemas.command import (
    ACTIVE_COMMAND_STATUSES,
    DeviceCommand,
    RelayTarget,
    SetRelayPayload,
    UpdateThresholdsPayload,
)

logger = logging.getLogger("iot_service.command")


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _publish_command_updated(cmd: DeviceCommand, timestamp: datetime) -> None:
    """Best-effort internal realtime command.updated event (never raises)."""
    try:
        from app.realtime.publisher import ws_manager
        from app.schemas.api import CommandResponse, RealtimeEvent

        ws_manager.publish(
            RealtimeEvent(
                type="command.updated",
                deviceId=cmd.device_id,
                timestamp=timestamp,
                data=CommandResponse.from_domain(cmd).model_dump(mode="json"),
            )
        )
    except Exception as exc:  # pragma: no cover - realtime is best-effort
        logger.warning("[COMMAND REALTIME WARNING] %s", exc)


class CommandPublisher(Protocol):
    """Protocol for sending MQTT commands."""

    def publish(
        self,
        topic: str,
        payload: str | bytes,
        qos: int = 1,
        retain: bool = False,
    ) -> bool:
        ...


class DeviceCommandService:
    """Service responsible for creating, tracking, and publishing device commands."""

    def __init__(
        self,
        repository: CommandRepository | None = None,
        publisher: CommandPublisher | None = None,
        condition_evaluator: IoTConditionEvaluator | None = None,
    ):
        self.repository = repository or default_command_repository
        self._publisher = publisher
        self.condition_evaluator: IoTConditionEvaluator = (
            condition_evaluator or default_condition_evaluator
        )

    @property
    def publisher(self) -> CommandPublisher:
        if self._publisher is None:
            from app.mqtt.client import mqtt_manager
            self._publisher = mqtt_manager
        return self._publisher

    def send_set_relay_command(
        self,
        device_id: str,
        target: RelayTarget,
        state: int,
    ) -> DeviceCommand:
        """Validates, creates, and publishes a SET_RELAY manual actuator command."""
        command_id = str(uuid.uuid4())
        payload = SetRelayPayload(
            commandId=command_id,
            action="SET_RELAY",
            target=target,
            state=state,  # type: ignore
        )

        return self._dispatch_command(
            device_id=device_id,
            action="SET_RELAY",
            payload_dict=payload.model_dump(),
        )

    def send_update_thresholds_command(
        self,
        device_id: str,
        target_temp: float,
        target_hum: float,
        is_auto_mode: bool,
    ) -> DeviceCommand:
        """Validates, creates, and publishes an UPDATE_THRESHOLDS configuration command."""
        command_id = str(uuid.uuid4())
        payload = UpdateThresholdsPayload(
            commandId=command_id,
            action="UPDATE_THRESHOLDS",
            targetTemp=target_temp,
            targetHum=target_hum,
            isAutoMode=is_auto_mode,
        )

        return self._dispatch_command(
            device_id=device_id,
            action="UPDATE_THRESHOLDS",
            payload_dict=payload.model_dump(),
        )

    def _dispatch_command(
        self,
        device_id: str,
        action: str,
        payload_dict: dict,
    ) -> DeviceCommand:
        now = datetime.now(timezone.utc)
        command_id = payload_dict["commandId"]

        # Validate device_id / topic BEFORE persisting PENDING state so invalid node_id never pollutes repository
        topic = build_topic("command", device_id)

        # INT01-R1: server-authoritative ACK deadline, also published to the device as expiresAt so a
        # device with a synchronized clock (the INT01 simulator) never executes a stale command.
        expires_at = now + timedelta(seconds=self._timeout_seconds())
        payload_dict = {**payload_dict, "expiresAt": _iso_utc(expires_at)}
        payload_json = json.dumps(payload_dict)

        # Step 1: Initialize PENDING state in repository
        command = DeviceCommand(
            command_id=command_id,
            device_id=device_id,
            action=action,  # type: ignore
            payload=payload_dict,
            status="PENDING",
            created_at=now,
            expires_at=expires_at,
        )
        self.repository.save(command)

        # Step 2: Publish with QoS 1, retain=False (never retained: a reconnecting device must not replay it)
        publish_success = self.publisher.publish(
            topic=topic,
            payload=payload_json,
            qos=1,
            retain=False,
        )

        # Step 4: Transition to PUBLISHED or FAILED (atomic: an ACK may already have arrived on the MQTT thread)
        if publish_success:
            pub_now = datetime.now(timezone.utc)
            updated = compare_and_update(
                self.repository,
                command_id,
                ("PENDING",),
                {"status": "PUBLISHED", "published_at": pub_now},
            )
            if updated is None:
                current = self.repository.get(command_id) or command
                updated = current.model_copy(update={"published_at": pub_now})
                self.repository.update(updated)
            logger.info(
                "[COMMAND PUBLISHED] command_id='%s' action='%s' to '%s'",
                command_id,
                action,
                topic,
            )
            return updated
        else:
            updated = compare_and_update(
                self.repository,
                command_id,
                ("PENDING",),
                {
                    "status": "FAILED",
                    "ack_message": "MQTT publish failed or broker unavailable",
                },
            ) or (self.repository.get(command_id) or command)
            logger.warning(
                "[COMMAND FAILED] Could not publish command_id='%s' to '%s'",
                command_id,
                topic,
            )
            try:
                self.condition_evaluator.evaluate_command_failure(
                    device_id=device_id,
                    command_id=command_id,
                    action=action,
                    target=payload_dict.get("target"),
                    reason="MQTT publish failed or broker unavailable",
                    timestamp=now,
                )
            except Exception as exc:
                logger.warning("[COMMAND FAILURE DOMAIN EVENT WARNING] %s", exc)
            return updated

    @staticmethod
    def _timeout_seconds() -> int:
        from app.config import settings

        return int(settings.command_ack_timeout_seconds)

    def _deadline(self, cmd: DeviceCommand, timeout_seconds: int | None) -> datetime:
        if timeout_seconds is None and cmd.expires_at is not None:
            return cmd.expires_at
        ref_time = cmd.published_at or cmd.created_at
        return ref_time + timedelta(
            seconds=timeout_seconds if timeout_seconds is not None else self._timeout_seconds()
        )

    def expire_if_due(
        self,
        cmd: DeviceCommand,
        now: datetime | None = None,
        timeout_seconds: int | None = None,
    ) -> DeviceCommand | None:
        """Atomically moves one PENDING/PUBLISHED command past its deadline to terminal TIMEOUT.

        Returns the TIMEOUT record if this call performed the transition, else None.
        """
        if cmd.status not in ACTIVE_COMMAND_STATUSES:
            return None
        current_time = now or datetime.now(timezone.utc)
        if current_time <= self._deadline(cmd, timeout_seconds):
            return None
        effective = timeout_seconds if timeout_seconds is not None else self._timeout_seconds()
        updated = compare_and_update(
            self.repository,
            cmd.command_id,
            ACTIVE_COMMAND_STATUSES,
            {
                "status": "TIMEOUT",
                "ack_message": f"Command timed out waiting for device ACK (>{effective}s)",
            },
        )
        if updated is None:
            return None
        logger.warning(
            "[COMMAND TIMEOUT] command_id='%s' device='%s' action='%s'",
            updated.command_id,
            updated.device_id,
            updated.action,
        )
        try:
            self.condition_evaluator.evaluate_command_failure(
                device_id=updated.device_id,
                command_id=updated.command_id,
                action=str(updated.action),
                target=updated.payload.get("target"),
                reason=updated.ack_message,
                timestamp=current_time,
            )
        except Exception as exc:
            logger.warning("[COMMAND TIMEOUT DOMAIN EVENT WARNING] %s", exc)
        _publish_command_updated(updated, current_time)
        return updated

    def evaluate_command_timeouts(
        self,
        now: datetime | None = None,
        timeout_seconds: int | None = None,
    ) -> list[DeviceCommand]:
        """Transitions PENDING/PUBLISHED commands with no ACK past their deadline to TIMEOUT.

        INT01-R1: invoked periodically by the IoT lifespan sweeper (app.main) and lazily on reads.
        """
        current_time = now or datetime.now(timezone.utc)
        timed_out: list[DeviceCommand] = []
        if not hasattr(self.repository, "list_all"):
            return timed_out

        for cmd in self.repository.list_all():
            updated = self.expire_if_due(cmd, current_time, timeout_seconds)
            if updated is not None:
                timed_out.append(updated)
        return timed_out

    def get_command(self, command_id: str) -> DeviceCommand | None:
        cmd = self.repository.get(command_id)
        if cmd is None:
            return None
        # Lazy expiry keeps reads server-authoritative even if the sweeper is delayed.
        return self.expire_if_due(cmd) or self.repository.get(command_id)

    def list_commands(
        self, device_id: str, limit: int = 100
    ) -> list[DeviceCommand]:
        return self.repository.list_by_device(device_id, limit=limit)


command_service = DeviceCommandService()
