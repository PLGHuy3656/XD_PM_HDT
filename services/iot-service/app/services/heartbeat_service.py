import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import ValidationError

from app.schemas.presence import DevicePresence, HeartbeatPayload
from app.services.presence_service import DevicePresenceService, presence_service

logger = logging.getLogger("iot_service.heartbeat")


@dataclass(frozen=True)
class HeartbeatProcessResult:
    """Result of processing a heartbeat message."""
    success: bool
    presence: DevicePresence | None = None
    error: str | None = None


class HeartbeatService:
    """Service handling the ingestion, validation, and presence update of device heartbeats."""

    def __init__(self, presence_svc: DevicePresenceService | None = None):
        self.presence_service = presence_svc or presence_service

    def process_message(
        self, topic_device_code: str, payload_bytes: bytes | str
    ) -> HeartbeatProcessResult:
        """Processes an incoming raw heartbeat payload from a specific device topic.

        Steps:
        1. Decode bytes (UTF-8).
        2. Parse JSON object.
        3. Validate schema using HeartbeatPayload.
        4. Validate identity match: topic_device_code == payload.deviceId.
        5. Assign server UTC last_seen timestamp.
        6. Update device presence in repository.
        7. Return HeartbeatProcessResult.
        """
        # Step 1: Decode
        try:
            if isinstance(payload_bytes, (bytes, bytearray)):
                payload_str = payload_bytes.decode("utf-8")
            elif isinstance(payload_bytes, str):
                payload_str = payload_bytes
            else:
                msg = f"Invalid payload type: expected bytes or str, got {type(payload_bytes).__name__}"
                logger.warning("[HEARTBEAT REJECTED] %s for device_code='%s'", msg, topic_device_code)
                return HeartbeatProcessResult(success=False, error=msg)
        except UnicodeDecodeError as exc:
            msg = f"Payload bytes could not be decoded as UTF-8: {exc}"
            logger.warning("[HEARTBEAT REJECTED] %s for device_code='%s'", msg, topic_device_code)
            return HeartbeatProcessResult(success=False, error=msg)

        # Step 2: Parse JSON
        try:
            data = json.loads(payload_str)
        except json.JSONDecodeError as exc:
            msg = f"Invalid JSON format: {exc}"
            logger.warning("[HEARTBEAT REJECTED] %s for device_code='%s'", msg, topic_device_code)
            return HeartbeatProcessResult(success=False, error=msg)

        if not isinstance(data, dict):
            msg = f"JSON payload must be an object/dict, got {type(data).__name__}"
            logger.warning("[HEARTBEAT REJECTED] %s for device_code='%s'", msg, topic_device_code)
            return HeartbeatProcessResult(success=False, error=msg)

        # Step 3: Validate schema
        try:
            payload = HeartbeatPayload.model_validate(data)
        except ValidationError as exc:
            msg = f"Schema validation failed: {exc.errors()}"
            logger.warning("[HEARTBEAT REJECTED] %s for device_code='%s'", msg, topic_device_code)
            return HeartbeatProcessResult(success=False, error=msg)

        # Step 4: Validate identity
        if topic_device_code != payload.deviceId:
            msg = (
                f"Device identity mismatch: topic device_code='{topic_device_code}' "
                f"does not match payload deviceId='{payload.deviceId}'"
            )
            logger.warning("[HEARTBEAT REJECTED] %s", msg)
            return HeartbeatProcessResult(success=False, error=msg)

        # Step 5 & 6: Assign server UTC timestamp and update presence
        now = datetime.now(timezone.utc)
        try:
            presence = self.presence_service.record_heartbeat(
                topic_device_code, payload, timestamp=now
            )
        except Exception as exc:
            msg = f"Error recording presence: {exc}"
            logger.error("[HEARTBEAT ERROR] %s", msg, exc_info=True)
            return HeartbeatProcessResult(success=False, error=msg)

        return HeartbeatProcessResult(success=True, presence=presence)


heartbeat_service = HeartbeatService()
