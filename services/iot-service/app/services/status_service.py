import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import ValidationError

from app.schemas.presence import DevicePresence, StatusPayload
from app.services.presence_service import DevicePresenceService, presence_service

logger = logging.getLogger("iot_service.status")


@dataclass(frozen=True)
class StatusProcessResult:
    """Result of processing a status or LWT message."""
    success: bool
    presence: DevicePresence | None = None
    error: str | None = None


class StatusService:
    """Service handling explicit MQTT status and broker-retained LWT disconnect messages."""

    def __init__(self, presence_svc: DevicePresenceService | None = None):
        self.presence_service = presence_svc or presence_service

    def process_message(
        self, topic_device_code: str, payload_bytes: bytes | str
    ) -> StatusProcessResult:
        """Processes an incoming raw status or LWT payload from a device topic.

        Steps:
        1. Decode bytes (UTF-8).
        2. Parse JSON object.
        3. Validate schema using StatusPayload ("online" or "offline").
        4. Update device presence (ONLINE or OFFLINE).
        5. Return StatusProcessResult.
        """
        # Step 1: Decode
        try:
            if isinstance(payload_bytes, (bytes, bytearray)):
                payload_str = payload_bytes.decode("utf-8")
            elif isinstance(payload_bytes, str):
                payload_str = payload_bytes
            else:
                msg = f"Invalid payload type: expected bytes or str, got {type(payload_bytes).__name__}"
                logger.warning("[STATUS REJECTED] %s for device_code='%s'", msg, topic_device_code)
                return StatusProcessResult(success=False, error=msg)
        except UnicodeDecodeError as exc:
            msg = f"Payload bytes could not be decoded as UTF-8: {exc}"
            logger.warning("[STATUS REJECTED] %s for device_code='%s'", msg, topic_device_code)
            return StatusProcessResult(success=False, error=msg)

        # Step 2: Parse JSON
        try:
            data = json.loads(payload_str)
        except json.JSONDecodeError as exc:
            msg = f"Invalid JSON format: {exc}"
            logger.warning("[STATUS REJECTED] %s for device_code='%s'", msg, topic_device_code)
            return StatusProcessResult(success=False, error=msg)

        if not isinstance(data, dict):
            msg = f"JSON payload must be an object/dict, got {type(data).__name__}"
            logger.warning("[STATUS REJECTED] %s for device_code='%s'", msg, topic_device_code)
            return StatusProcessResult(success=False, error=msg)

        # Step 3: Validate schema
        try:
            payload = StatusPayload.model_validate(data)
        except ValidationError as exc:
            msg = f"Schema validation failed: {exc.errors()}"
            logger.warning("[STATUS REJECTED] %s for device_code='%s'", msg, topic_device_code)
            return StatusProcessResult(success=False, error=msg)

        # Step 4: Update presence
        now = datetime.now(timezone.utc)
        try:
            if payload.status == "online":
                presence = self.presence_service.record_online_status(
                    topic_device_code, timestamp=now
                )
            else:
                presence = self.presence_service.record_offline_status(
                    topic_device_code, timestamp=now
                )
        except Exception as exc:
            msg = f"Error recording status: {exc}"
            logger.error("[STATUS ERROR] %s", msg, exc_info=True)
            return StatusProcessResult(success=False, error=msg)

        return StatusProcessResult(success=True, presence=presence)


status_service = StatusService()
