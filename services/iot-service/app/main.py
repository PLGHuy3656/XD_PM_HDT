import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.config import settings
from app.mqtt.client import mqtt_manager
from app.routes import iot_router, ws_router

logger = logging.getLogger("iot_service.main")


async def command_timeout_sweeper(interval_seconds: float) -> None:
    """INT01-R1: server-authoritative runtime TIMEOUT for commands without ACK.

    Periodically moves PENDING/PUBLISHED commands past their deadline to the terminal
    TIMEOUT state (atomic with the MQTT ACK path, see InMemoryCommandRepository).
    """
    from app.services.command_service import command_service

    while True:
        await asyncio.sleep(interval_seconds)
        try:
            timed_out = command_service.evaluate_command_timeouts()
            if timed_out:
                logger.info("[COMMAND TIMEOUT SWEEP] %d command(s) -> TIMEOUT", len(timed_out))
        except Exception as exc:  # never let the sweeper die
            logger.warning("[COMMAND TIMEOUT SWEEP WARNING] %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages service lifespan: initializes background MQTT client and the command
    TIMEOUT sweeper on startup, and stops both gracefully on shutdown.
    """
    if settings.mqtt_auto_start:
        mqtt_manager.start()
    sweeper_task = None
    if settings.command_timeout_sweeper_enabled:
        sweeper_task = asyncio.create_task(
            command_timeout_sweeper(settings.command_timeout_sweep_interval_seconds)
        )
    app.state.command_timeout_sweeper = sweeper_task
    yield
    if sweeper_task is not None:
        sweeper_task.cancel()
        with suppress(asyncio.CancelledError):
            await sweeper_task
    if settings.mqtt_auto_start:
        mqtt_manager.stop()


app = FastAPI(
    title="SwiftletCare IoT Service",
    description="Microservice responsible for MQTT lifecycle, telemetry processing, device presence, and control configuration.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(iot_router)
app.include_router(ws_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.service_name,
    }


@app.get("/health/runtime")
def health_runtime():
    """INT01-R1: runtime dependency status (no secrets, no device data).

    HTTP 200 only proves the process is up; ``mqtt`` tells whether the broker link
    that every IoT business flow depends on is actually connected.
    """
    if not settings.mqtt_auto_start:
        mqtt_state = "disabled"
    else:
        mqtt_state = "connected" if mqtt_manager.is_connected else "disconnected"
    sweeper = getattr(app.state, "command_timeout_sweeper", None)
    return {
        "status": "ok" if mqtt_state != "disconnected" else "degraded",
        "service": settings.service_name,
        "mqtt": mqtt_state,
        "commandTimeoutSweeper": "running" if (sweeper is not None and not sweeper.done()) else "stopped",
        "commandAckTimeoutSeconds": settings.command_ack_timeout_seconds,
    }
