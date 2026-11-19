import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import ValidationError

from app.domain_events.evaluator import (
    IoTConditionEvaluator,
    default_condition_evaluator,
)
from app.realtime.publisher import RealtimePublisher, ws_manager
from app.repositories.telemetry_repository import (
    TelemetryRepository,
    default_telemetry_repository,
)
from app.schemas.api import RealtimeEvent, TelemetryResponse
from app.schemas.telemetry import AcceptedTelemetry, TelemetryPayload

logger = logging.getLogger("iot_service.telemetry")


@dataclass(frozen=True)
class TelemetryProcessResult:
    """Result of processing a telemetry message."""
    success: bool
    telemetry: AcceptedTelemetry | None = None
    error: str | None = None


class TelemetryService:
    """Service handling the ingestion, validation, normalization,

    in-memory storage, and realtime emission of device telemetry.
    """

    def __init__(
        self,
        repository: TelemetryRepository | None = None,
        realtime_publisher: RealtimePublisher | None = None,
        condition_evaluator: IoTConditionEvaluator | None = None,
    ):
        self.repository: TelemetryRepository = (
            repository or default_telemetry_repository
        )
        self.realtime_publisher: RealtimePublisher = (
            realtime_publisher or ws_manager
        )
        self.condition_evaluator: IoTConditionEvaluator = (
            condition_evaluator or default_condition_evaluator
        )

    def get_latest(self, device_id: str) -> AcceptedTelemetry | None:
        """Retrieves the latest accepted telemetry for a device."""
        return self.repository.get_latest(device_id)

    def list_by_device(
        self, device_id: str, limit: int = 50
    ) -> list[AcceptedTelemetry]:
        """Lists recent telemetry records for a device up to limit."""
        return self.repository.list_by_device(device_id, limit=limit)

    def process_message(
        self, topic_device_code: str, payload_bytes: bytes | str
    ) -> TelemetryProcessResult:
        """Processes an incoming raw telemetry MQTT payload from a specific device topic."""
        # Step 1: Decode bytes
        try:
            if isinstance(payload_bytes, (bytes, bytearray)):
                payload_str = payload_bytes.decode("utf-8")
            elif isinstance(payload_bytes, str):
                payload_str = payload_bytes
            else:
                msg = f"Invalid payload type: expected bytes or str, got {type(payload_bytes).__name__}"
                logger.warning("[TELEMETRY REJECTED] %s for device_code='%s'", msg, topic_device_code)
                return TelemetryProcessResult(success=False, error=msg)
        except UnicodeDecodeError as exc:
            msg = f"Payload bytes could not be decoded as UTF-8: {exc}"
            logger.warning("[TELEMETRY REJECTED] %s for device_code='%s'", msg, topic_device_code)
            return TelemetryProcessResult(success=False, error=msg)

        # Step 2: Parse JSON
        try:
            data = json.loads(payload_str)
        except json.JSONDecodeError as exc:
            msg = f"Invalid JSON format: {exc}"
            logger.warning("[TELEMETRY REJECTED] %s for device_code='%s'", msg, topic_device_code)
            return TelemetryProcessResult(success=False, error=msg)

        if not isinstance(data, dict):
            msg = f"JSON payload must be an object/dict, got {type(data).__name__}"
            logger.warning("[TELEMETRY REJECTED] %s for device_code='%s'", msg, topic_device_code)
            return TelemetryProcessResult(success=False, error=msg)

        # Step 3: Validate TelemetryPayload schema
        try:
            telemetry_payload = TelemetryPayload.model_validate(data)
        except ValidationError as exc:
            msg = f"Schema validation failed: {exc.errors()}"
            logger.warning("[TELEMETRY REJECTED] %s for device_code='%s'", msg, topic_device_code)
            return TelemetryProcessResult(success=False, error=msg)

        # Step 4: Validate topic device_code == payload.deviceId
        if topic_device_code != telemetry_payload.deviceId:
            msg = (
                f"Device identity mismatch: topic device_code='{topic_device_code}' "
                f"does not match payload deviceId='{telemetry_payload.deviceId}'"
            )
            logger.warning("[TELEMETRY REJECTED] %s", msg)
            return TelemetryProcessResult(success=False, error=msg)

        # Step 5: Assign server UTC received_at
        received_at = datetime.now(timezone.utc)

        # Step 6: Create normalized AcceptedTelemetry
        accepted = AcceptedTelemetry(
            device_id=telemetry_payload.deviceId,
            received_at=received_at,
            metrics=telemetry_payload.metrics,
            actuators=telemetry_payload.actuators,
            state=telemetry_payload.state,
        )

        # Step 7: Save to repository abstraction
        try:
            self.repository.save(accepted)
        except Exception as exc:
            msg = f"Repository error saving telemetry: {exc}"
            logger.error("[TELEMETRY ERROR] %s", msg, exc_info=True)
            return TelemetryProcessResult(success=False, error=msg)

        logger.info(
            "[TELEMETRY ACCEPTED] device_id='%s' temp=%.2f hum=%.2f mode='%s' at %s",
            accepted.device_id,
            accepted.metrics.temperature,
            accepted.metrics.humidity,
            accepted.state.mode,
            accepted.received_at.isoformat(),
        )

        # Step 8: Evaluate domain alert events (Hysteresis & condition state machine)
        try:
            self.condition_evaluator.evaluate_telemetry(accepted)
        except Exception as exc:
            logger.warning(
                "[TELEMETRY CONDITION EVALUATION WARNING] Failed to evaluate conditions for '%s': %s",
                accepted.device_id,
                exc,
            )

        # Step 9: Publish realtime event (isolated from domain success)
        try:
            event = RealtimeEvent(
                type="telemetry.updated",
                deviceId=accepted.device_id,
                timestamp=accepted.received_at,
                data=TelemetryResponse.from_domain(accepted).model_dump(mode="json"),
            )
            self.realtime_publisher.publish(event)
        except Exception as exc:
            logger.warning(
                "[TELEMETRY REALTIME WARNING] Failed to publish telemetry.updated event for '%s': %s",
                accepted.device_id,
                exc,
            )

        return TelemetryProcessResult(success=True, telemetry=accepted)


telemetry_service = TelemetryService()
