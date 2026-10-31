import asyncio
import logging
from datetime import datetime, timezone

from app.realtime.manager import realtime_manager
from app.repositories.telemetry_repository import save_telemetry
from app.schemas.telemetry import TelemetryPayload

logger = logging.getLogger("telemetry")


def process_telemetry(
    house_code: str,
    payload: TelemetryPayload,
    event_loop: asyncio.AbstractEventLoop | None,
) -> None:
    recorded_at = datetime.fromtimestamp(
        payload.timestamp,
        tz=timezone.utc,
    )
    now = datetime.now(timezone.utc)
    if (recorded_at - now).total_seconds() > 300:
        raise ValueError("Telemetry timestamp is too far in the future")

    save_telemetry(house_code, payload, recorded_at)

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
        realtime_manager.broadcast(realtime_data),
        event_loop,
    )

    def log_broadcast_result(result):
        try:
            result.result()
        except Exception:
            logger.exception("Failed to broadcast telemetry")

    future.add_done_callback(log_broadcast_result)