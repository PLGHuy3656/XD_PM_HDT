import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Protocol

from app.domain_events.evaluator import (
    IoTConditionEvaluator,
    default_condition_evaluator,
)
from app.mqtt.topics import build_topic
from app.repositories.command_repository import (
    CommandRepository,
    default_command_repository,
)
from app.schemas.command import (
    DeviceCommand,
    RelayTarget,
    SetRelayPayload,
    UpdateThresholdsPayload,
)

logger = logging.getLogger("iot_service.command")


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

        # Step 1: Initialize PENDING state in repository
        command = DeviceCommand(
            command_id=command_id,
            device_id=device_id,
            action=action,  # type: ignore
            payload=payload_dict,
            status="PENDING",
            created_at=now,
        )
        self.repository.save(command)

        # Step 2: Build command topic: swiftlet/command/{device_code}
        topic = build_topic("command", device_id)
        payload_json = json.dumps(payload_dict)

        # Step 3: Publish with QoS 1, retain=False
        publish_success = self.publisher.publish(
            topic=topic,
            payload=payload_json,
            qos=1,
            retain=False,
        )

        # Step 4: Transition to PUBLISHED or FAILED
        if publish_success:
            pub_now = datetime.now(timezone.utc)
            current = self.repository.get(command_id) or command
            if current.status in ("SUCCESS", "FAILED", "ERROR"):
                updated = current.model_copy(
                    update={
                        "published_at": pub_now,
                    }
                )
            else:
                updated = current.model_copy(
                    update={
                        "status": "PUBLISHED",
                        "published_at": pub_now,
                    }
                )
            self.repository.update(updated)
            logger.info(
                "[COMMAND PUBLISHED] command_id='%s' action='%s' to '%s'",
                command_id,
                action,
                topic,
            )
            return updated
        else:
            updated = command.model_copy(
                update={
                    "status": "FAILED",
                    "ack_message": "MQTT publish failed or broker unavailable",
                }
            )
            self.repository.update(updated)
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

    def get_command(self, command_id: str) -> DeviceCommand | None:
        return self.repository.get(command_id)

    def list_commands(
        self, device_id: str, limit: int = 100
    ) -> list[DeviceCommand]:
        return self.repository.list_by_device(device_id, limit=limit)


command_service = DeviceCommandService()
