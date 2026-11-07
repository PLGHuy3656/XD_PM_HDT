"""FastAPI dependencies for accessing AI runtime state and managers (CP5.3)."""
from __future__ import annotations

from pathlib import Path

from fastapi import Request, WebSocket

from app.runtime.manager import AIRuntimeManager
from app.runtime.state_store import InMemoryAIRuntimeStateStore
from app.websocket.manager import AIWebSocketManager


def get_runtime_manager(request: Request) -> AIRuntimeManager:
    return request.app.state.runtime_manager


def get_state_store(request: Request) -> InMemoryAIRuntimeStateStore:
    return request.app.state.runtime_manager.state_store


def get_snapshot_dir(request: Request) -> Path:
    custom_dir = getattr(request.app.state, "snapshot_dir", None)
    if custom_dir is not None:
        return Path(custom_dir)
    return request.app.state.runtime_manager.snapshot_dir


def get_ws_manager(websocket: WebSocket) -> AIWebSocketManager:
    return websocket.app.state.ws_manager


def is_camera_registered(
    camera_id: str,
    runtime_manager: AIRuntimeManager,
    state_store: InMemoryAIRuntimeStateStore,
) -> bool:
    """Return True if camera_id is registered in AIRuntimeManager or present in runtime state."""
    return (
        runtime_manager.get_pipeline(camera_id) is not None
        or state_store.get_camera_status(camera_id) is not None
    )
