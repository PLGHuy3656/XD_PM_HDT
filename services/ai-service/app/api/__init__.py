"""REST API routers for AI Service V1."""
from app.api.analyze import router as analyze_router
from app.api.cameras import router as cameras_router
from app.api.events import router as events_router
from app.api.health import router as health_router
from app.api.runtime_control import router as runtime_control_router
from app.api.snapshots import router as snapshots_router

__all__ = [
    "analyze_router",
    "cameras_router",
    "events_router",
    "health_router",
    "runtime_control_router",
    "snapshots_router",
]
