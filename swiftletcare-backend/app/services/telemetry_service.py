import asyncio
import json
import logging
from datetime import datetime, timezone

from pydantic import ValidationError

from app.realtime.manager import RealtimeManager, realtime_manager
from app.repositories.telemetry_repository import (
    TelemetryRepository,
    telemetry_repository,
)
from app.schemas.telemetry import TelemetryPayload

logger = logging.getLogger("telemetry.service")


class TelemetryService:
    """
    Business logic layer for telemetry processing, validation rules,
    coordination between repository and realtime broadcasting,
    and graceful error handling.
    """

    def __init__(
        self,
        repository: TelemetryRepository | None = None,
        realtime: RealtimeManager | None = None,
    ):
        self.repository = repository or telemetry_repository
        self.realtime_manager = realtime or realtime_manager

    def validate_timestamp(self, timestamp: int) -> datetime:
        recorded_at = datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        )
        now = datetime.now(timezone.utc)
        if (recorded_at - now).total_seconds() > 300:
            raise ValueError("Telemetry timestamp is too far in the future")
        return recorded_at

    def process_message(
        self,
        topic: str,
        payload_bytes: bytes | str,
        event_loop: asyncio.AbstractEventLoop | None = None,
    ) -> bool:
        """
        Validates topic & payload, persists telemetry via repository,
        and broadcasts to WebSocket clients.
        Returns True on success, False if rejected or failed.
        """
        try:
            parts = topic.split("/")

            if len(parts) != 4 or parts[:2] != ["swiftlet", "telemetry"]:
                raise ValueError("Invalid telemetry topic")

            house_code = parts[2]
            node_id_from_topic = parts[3]

            payload = TelemetryPayload.model_validate_json(payload_bytes)

            if payload.nodeId != node_id_from_topic:
                raise ValueError("nodeId does not match MQTT topic")

            recorded_at = self.validate_timestamp(payload.timestamp)

            # Persist to database
            self.repository.save_telemetry(house_code, payload, recorded_at)

            logger.info(
                "Saved telemetry: node=%s house=%s",
                payload.nodeId,
                house_code,
            )

            # Broadcast to WebSocket subscribers
            self._broadcast_realtime(house_code, payload, event_loop)
            return True

        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            logger.warning(
                "Rejected telemetry from %s: %s",
                topic,
                exc,
            )
            return False

        except Exception:
            logger.exception(
                "Failed to process telemetry from %s",
                topic,
            )
            return False

    def _broadcast_realtime(
        self,
        house_code: str,
        payload: TelemetryPayload,
        event_loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        if event_loop is None or not event_loop.is_running():
            logger.warning(
                "Telemetry saved, but realtime event loop is unavailable"
            )
            return

        realtime_data = {
            "type": "telemetry",
            "houseCode": house_code,
            "nodeId": payload.nodeId,
            "timestamp": payload.timestamp,
            "metrics": payload.metrics.model_dump(by_alias=True),
            "actuators": payload.actuators.model_dump(),
            "state": payload.state.model_dump(),
        }

        future = asyncio.run_coroutine_threadsafe(
            self.realtime_manager.broadcast(realtime_data),
            event_loop,
        )

        def log_broadcast_result(result):
            try:
                result.result()
            except Exception:
                logger.exception("Failed to broadcast telemetry")

        future.add_done_callback(log_broadcast_result)


telemetry_service = TelemetryService()
