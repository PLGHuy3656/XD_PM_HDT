from app.routes.iot_routes import router as iot_router
from app.routes.ws_routes import router as ws_router

__all__ = [
    "iot_router",
    "ws_router",
]
