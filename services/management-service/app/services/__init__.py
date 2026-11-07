"""Services package for Management Service."""
from app.services.auth_service import AuthService, auth_service
from app.services.device_service import DeviceService, device_service
from app.services.farm_service import FarmService, farm_service
from app.services.technician_service import TechnicianService, technician_service
from app.services.zone_service import ZoneService, zone_service

__all__ = [
    "AuthService",
    "auth_service",
    "DeviceService",
    "device_service",
    "FarmService",
    "farm_service",
    "TechnicianService",
    "technician_service",
    "ZoneService",
    "zone_service",
]
