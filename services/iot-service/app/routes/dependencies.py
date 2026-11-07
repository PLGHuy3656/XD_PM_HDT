"""FastAPI dependency providers for IoT Service routes.

Security Boundary Note:
Authentication and RBAC (ADMIN, FARM_OWNER, TECHNICIAN) are owned by the
Management Service and will be enforced via API Gateway + Management identity
integration in a subsequent checkpoint. Do not duplicate user/role persistence
or local RBAC rules inside IoT Service.
"""

from app.realtime.publisher import WebSocketConnectionManager, ws_manager
from app.services.command_service import DeviceCommandService, command_service
from app.services.presence_service import DevicePresenceService, presence_service
from app.services.telemetry_service import TelemetryService, telemetry_service


def get_telemetry_service() -> TelemetryService:
    return telemetry_service


def get_presence_service() -> DevicePresenceService:
    return presence_service


def get_command_service() -> DeviceCommandService:
    return command_service


def get_ws_manager() -> WebSocketConnectionManager:
    return ws_manager
