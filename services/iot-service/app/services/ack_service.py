import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import ValidationError

from app.realtime.publisher import RealtimePublisher, ws_manager
from app.repositories.command_repository import (
    CommandRepository,
    default_command_repository,
)
from app.schemas.api import CommandResponse, RealtimeEvent
from app.schemas.command import AckPayload, DeviceCommand

logger = logging.getLogger("iot_service.ack")


@dataclass(frozen=True)
class AckProcessResult:
    """Result of processing a device ACK."""
    success: bool
    command: DeviceCommand | None = None
    error: str | None = None


class AckService:
    """Service handling device command acknowledgments, lifecycle correlation,

    and realtime command.updated event emission.
    """

    def __init__(
        self,
        repository: CommandRepository | None = None,
        realtime_publisher: RealtimePublisher | None = None,
    ):
        self.repository = repository or default_command_repository
        self.realtime_publisher: RealtimePublisher = (
            realtime_publisher or ws_manager
        )

    def process_message(
        self, topic_device_code: str, payload_bytes: bytes | str
    ) -> AckProcessResult:
        """Processes an incoming raw ACK payload from a device topic."""
        # Step 1: Decode
        try:
            if isinstance(payload_bytes, (bytes, bytearray)):
                payload_str = payload_bytes.decode("utf-8")
            elif isinstance(payload_bytes, str):
                payload_str = payload_bytes
            else:
                msg = f"Invalid payload type: expected bytes or str, got {type(payload_bytes).__name__}"
                logger.warning("[ACK REJECTED] %s for device_code='%s'", msg, topic_device_code)
                return AckProcessResult(success=False, error=msg)
        except UnicodeDecodeError as exc:
            msg = f"Payload bytes could not be decoded as UTF-8: {exc}"
            logger.warning("[ACK REJECTED] %s for device_code='%s'", msg, topic_device_code)
            return AckProcessResult(success=False, error=msg)

        # Step 2: Parse JSON
        try:
            data = json.loads(payload_str)
        except json.JSONDecodeError as exc:
            msg = f"Invalid JSON format: {exc}"
            logger.warning("[ACK REJECTED] %s for device_code='%s'", msg, topic_device_code)
            return AckProcessResult(success=False, error=msg)

        if not isinstance(data, dict):
            msg = f"JSON payload must be an object/dict, got {type(data).__name__}"
            logger.warning("[ACK REJECTED] %s for device_code='%s'", msg, topic_device_code)
            return AckProcessResult(success=False, error=msg)

        # Step 3: Validate schema
        try:
            ack_payload = AckPayload.model_validate(data)
        except ValidationError as exc:
            msg = f"Schema validation failed: {exc.errors()}"
            logger.warning("[ACK REJECTED] %s for device_code='%s'", msg, topic_device_code)
            return AckProcessResult(success=False, error=msg)

        # Step 4: Validate topic device == payload device
        if topic_device_code != ack_payload.deviceId:
            msg = (
                f"Device identity mismatch: topic device_code='{topic_device_code}' "
                f"does not match payload deviceId='{ack_payload.deviceId}'"
            )
            logger.warning("[ACK REJECTED] %s", msg)
            return AckProcessResult(success=False, error=msg)

        # Step 5: Look up original command
        command = self.repository.get(ack_payload.commandId)
        if not command:
            msg = f"Unknown commandId '{ack_payload.commandId}': no matching command found"
            logger.warning("[ACK REJECTED] %s", msg)
            return AckProcessResult(success=False, error=msg)

        # Step 6: Validate ACK device matches original command device
        if command.device_id != ack_payload.deviceId:
            msg = (
                f"Device mismatch for commandId '{ack_payload.commandId}': "
                f"original device was '{command.device_id}' but ACK was received from '{ack_payload.deviceId}'"
            )
            logger.warning("[ACK REJECTED] %s", msg)
            return AckProcessResult(success=False, error=msg)

        # Step 7: Handle duplicate/terminal state idempotently
        if command.status in ("SUCCESS", "FAILED", "ERROR"):
            logger.info(
                "[ACK IDEMPOTENT] Command '%s' is already in terminal state '%s'; ignoring duplicate ACK",
                command.command_id,
                command.status,
            )
            return AckProcessResult(success=True, command=command)

        # Step 8: Update command lifecycle
        now = datetime.now(timezone.utc)
        updated = command.model_copy(
            update={
                "status": ack_payload.status,
                "acknowledged_at": now,
                "ack_status": ack_payload.status,
                "ack_message": ack_payload.message,
                "ack_mode": ack_payload.mode,
            }
        )
        self.repository.update(updated)

        logger.info(
            "[ACK CORRELATED] command_id='%s' status='%s' mode='%s'",
            updated.command_id,
            updated.status,
            updated.ack_mode,
        )

        # Step 9: Publish realtime command.updated event (isolated from domain success)
        try:
            event = RealtimeEvent(
                type="command.updated",
                deviceId=updated.device_id,
                timestamp=now,
                data=CommandResponse.from_domain(updated).model_dump(mode="json"),
            )
            self.realtime_publisher.publish(event)
        except Exception as exc:
            logger.warning(
                "[ACK REALTIME WARNING] Failed to publish command.updated event for '%s': %s",
                updated.command_id,
                exc,
            )

        return AckProcessResult(success=True, command=updated)


ack_service = AckService()
