from app.api.health import router as health_router
from app.api.alerts import router as alerts_router
from app.api.notifications import router as notifications_router
from app.api.devices import router as devices_router
from app.api.internal_events import router as internal_events_router

__all__ = [
    "health_router",
    "alerts_router",
    "notifications_router",
    "devices_router",
    "internal_events_router",
]
