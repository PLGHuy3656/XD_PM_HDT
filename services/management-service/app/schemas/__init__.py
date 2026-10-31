"""Schemas package for Management Service."""
from app.schemas.auth import LoginRequest, TokenResponse, UserAuthInfo
from app.schemas.device import DeviceCreateRequest, DeviceRegistryResponse
from app.schemas.farm import FarmDetailResponse, FarmResponse
from app.schemas.technician import (
    AssignedFarmResponse,
    TechnicianDashboardResponse,
    TechnicianDeviceDetailResponse,
    TechnicianDeviceResponse,
    TechnicianFarmDetailResponse,
    TechnicianProfileResponse,
)
from app.schemas.user import RoleEnum
from app.schemas.zone import ZoneResponse

__all__ = [
    "LoginRequest",
    "TokenResponse",
    "UserAuthInfo",
    "DeviceCreateRequest",
    "DeviceRegistryResponse",
    "FarmDetailResponse",
    "FarmResponse",
    "AssignedFarmResponse",
    "TechnicianDashboardResponse",
    "TechnicianDeviceDetailResponse",
    "TechnicianDeviceResponse",
    "TechnicianFarmDetailResponse",
    "TechnicianProfileResponse",
    "RoleEnum",
    "ZoneResponse",
]
