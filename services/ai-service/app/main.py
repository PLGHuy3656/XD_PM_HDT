"""FastAPI application entrypoint for SwiftletCare AI Service V1 (CP5.3)."""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import FastAPI

from app import __version__
from app.api import (
    analyze_router,
    cameras_router,
    events_router,
    health_router,
    runtime_control_router,
    snapshots_router,
)
from app.config import AI_PIPELINE_DIR, load_pipeline_config, load_runtime_cameras, settings
from app.infrastructure.rabbitmq import get_domain_event_publisher
from app.ports.domain_event_publisher import DomainEventPublisher
from app.runtime.manager import AIRuntimeManager
from app.runtime.publisher_sink import DomainEventPublisherRuntimeSink
from app.websocket import AIWebSocketManager, router as ws_router


def create_app(
    runtime_manager: Optional[AIRuntimeManager] = None,
    ws_manager: Optional[AIWebSocketManager] = None,
    domain_event_publisher: Optional[DomainEventPublisher] = None,
    snapshot_dir: Optional[Path | str] = None,
    load_configured_cameras: Optional[bool] = None,
) -> FastAPI:
    """Create and configure the AI Service FastAPI application."""
    if ws_manager is not None:
        effective_ws_manager = ws_manager
    else:
        if runtime_manager is not None:
            p_cfg = runtime_manager.cfg
        else:
            pipeline_yaml = AI_PIPELINE_DIR / "configs" / "pipeline.yaml"
            p_cfg = load_pipeline_config(pipeline_yaml) if pipeline_yaml.exists() else {}
        ws_hz = float(p_cfg.get("ws", {}).get("detection_max_hz", 0.0)) if p_cfg else 0.0
        effective_ws_manager = AIWebSocketManager(detection_max_hz=ws_hz)

    effective_publisher = domain_event_publisher or get_domain_event_publisher()
    effective_publisher_sink = DomainEventPublisherRuntimeSink(publisher=effective_publisher)

    if runtime_manager is not None:
        effective_runtime_manager = runtime_manager
    else:
        pipeline_yaml = AI_PIPELINE_DIR / "configs" / "pipeline.yaml"
        p_cfg = load_pipeline_config(pipeline_yaml) if pipeline_yaml.exists() else {}
        effective_runtime_manager = AIRuntimeManager(pipeline_cfg=p_cfg)

    effective_runtime_manager.add_sink(effective_ws_manager.sink)
    effective_runtime_manager.add_sink(effective_publisher_sink)

    should_load_cameras = (
        load_configured_cameras
        if load_configured_cameras is not None
        else os.getenv("AI_LOAD_CONFIGURED_CAMERAS", "false").lower() in ("1", "true", "yes")
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        loop = asyncio.get_running_loop()
        application.state.ws_manager.attach_loop(loop)
        application.state.runtime_manager.add_sink(application.state.ws_manager.sink)
        application.state.runtime_manager.add_sink(application.state.publisher_sink)

        if settings.rabbitmq_enabled and hasattr(application.state.domain_event_publisher, "connect"):
            try:
                await application.state.domain_event_publisher.connect()
            except Exception as exc:
                # Log and allow service to continue running even if RabbitMQ is temporarily unreachable
                import logging
                logging.getLogger("ai_service").error("Failed to connect RabbitMQ producer during startup: %s", exc)

        if should_load_cameras:
            cameras_yaml = AI_PIPELINE_DIR / "configs" / "cameras.yaml"
            if cameras_yaml.exists():
                for cam_cfg in load_runtime_cameras(cameras_yaml):
                    if application.state.runtime_manager.get_pipeline(cam_cfg.camera_id) is None:
                        application.state.runtime_manager.register_camera(cam_cfg)
                    if cam_cfg.autostart:
                        application.state.runtime_manager.start_camera(cam_cfg.camera_id)

        try:
            yield
        finally:
            application.state.ws_manager.flush_sync(timeout=1.0)
            application.state.runtime_manager.close_all()
            application.state.runtime_manager.remove_sink(application.state.ws_manager.sink)
            application.state.runtime_manager.remove_sink(application.state.publisher_sink)
            await application.state.ws_manager.close_all()
            if settings.rabbitmq_enabled and hasattr(application.state.domain_event_publisher, "close"):
                try:
                    await application.state.domain_event_publisher.close()
                except Exception:
                    pass

    application = FastAPI(
        title="SwiftletCare AI Service (Prototype V1)",
        description=(
            "Thin FastAPI REST V1 + WebSocket V1 transport layer exposing "
            "canonical AI runtime state (`DetectionResult`, `CountUpdate`, "
            "`AIEvent`, `CameraRuntimeStatus`)."
        ),
        version=__version__,
        lifespan=lifespan,
    )

    application.state.runtime_manager = effective_runtime_manager
    application.state.ws_manager = effective_ws_manager
    application.state.domain_event_publisher = effective_publisher
    application.state.publisher_sink = effective_publisher_sink
    application.state.snapshot_dir = Path(snapshot_dir) if snapshot_dir is not None else None

    application.include_router(health_router)
    application.include_router(cameras_router)
    application.include_router(events_router)
    application.include_router(snapshots_router)
    application.include_router(analyze_router)
    application.include_router(runtime_control_router)
    application.include_router(ws_router)

    return application


app = create_app()
