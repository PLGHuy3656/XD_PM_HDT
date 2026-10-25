from uuid import UUID

from fastapi import APIRouter

from app.controllers.technician_controller import technician_controller
from app.schemas.technician import (
    AssignedFarmResponse,
    TechnicianDashboardResponse,
    TechnicianDeviceDetailResponse,
    TechnicianDeviceResponse,
    TechnicianFarmDetailResponse,
    TechnicianProfileResponse,
)


router = APIRouter(
    prefix="/api/technicians",
    tags=["Technician"],
)


@router.get(
    "/{technician_id}/dashboard",
    response_model=TechnicianDashboardResponse,
)
def get_technician_dashboard(
    technician_id: UUID,
):
    return technician_controller.get_dashboard_summary(
        str(technician_id),
    )


@router.get(
    "/{technician_id}",
    response_model=TechnicianProfileResponse,
)
def get_technician_profile(
    technician_id: UUID,
):
    return technician_controller.get_profile(
        str(technician_id),
    )


@router.get(
    "/{technician_id}/farms",
    response_model=list[AssignedFarmResponse],
)
def get_assigned_farms(
    technician_id: UUID,
):
    return technician_controller.get_assigned_farms(
        str(technician_id),
    )


@router.get(
    "/{technician_id}/farms/{farm_id}",
    response_model=TechnicianFarmDetailResponse,
)
def get_assigned_farm_detail(
    technician_id: UUID,
    farm_id: UUID,
):
    return technician_controller.get_assigned_farm_detail(
        str(technician_id),
        str(farm_id),
    )


@router.get(
    "/{technician_id}/farms/{farm_id}/devices",
    response_model=list[TechnicianDeviceResponse],
)
def get_assigned_farm_devices(
    technician_id: UUID,
    farm_id: UUID,
):
    return technician_controller.get_assigned_farm_devices(
        str(technician_id),
        str(farm_id),
    )


@router.get(
    "/{technician_id}/farms/{farm_id}/devices/{device_id}",
    response_model=TechnicianDeviceDetailResponse,
)
def get_assigned_farm_device_detail(
    technician_id: UUID,
    farm_id: UUID,
    device_id: str,
):
    return technician_controller.get_assigned_farm_device_detail(
        str(technician_id),
        str(farm_id),
        device_id,
    )
