"""Controllers package for Management Service."""
from app.controllers.auth_controller import AuthController, auth_controller
from app.controllers.device_controller import DeviceController, device_controller
from app.controllers.farm_controller import FarmController, farm_controller
from app.controllers.technician_controller import TechnicianController, technician_controller
from app.controllers.zone_controller import ZoneController, zone_controller

__all__ = [
    "AuthController",
    "auth_controller",
    "DeviceController",
    "device_controller",
    "FarmController",
    "farm_controller",
    "TechnicianController",
    "technician_controller",
    "ZoneController",
    "zone_controller",
]
