from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.controllers.technician_controller import technician_controller
from app.core.dependencies import get_current_user, require_admin, require_roles
from app.repositories.user_repository import user_repository
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


def _verify_technician_self_or_admin(target_technician_id: str, current_user: dict):
    roles = current_user.get("roles") or []
    if "ADMIN" in roles:
        return
    if str(current_user.get("id")) != target_technician_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot access another technician's resource",
        )


def _verify_technician_farm_assignment(technician_id: str, farm_id: str):
    if not user_repository.is_farm_assigned_to_technician(technician_id, farm_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Farm not actively assigned to technician",
        )


@router.get(
    "",
    response_model=list[TechnicianProfileResponse],
    summary="List all technicians (Admin/Technician)",
)
def list_technicians(
    current_user: dict = Depends(require_roles("ADMIN", "TECHNICIAN")),
):
    return technician_controller.list_technicians()


@router.get(
    "/{technician_id}/dashboard",
    response_model=TechnicianDashboardResponse,
    summary="Get technician dashboard summary",
)
def get_technician_dashboard(
    technician_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    tech_id_str = str(technician_id)
    _verify_technician_self_or_admin(tech_id_str, current_user)
    return technician_controller.get_dashboard_summary(tech_id_str)


@router.get(
    "/{technician_id}",
    response_model=TechnicianProfileResponse,
    summary="Get technician profile",
)
def get_technician_profile(
    technician_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    tech_id_str = str(technician_id)
    _verify_technician_self_or_admin(tech_id_str, current_user)
    return technician_controller.get_profile(tech_id_str)


@router.get(
    "/{technician_id}/farms",
    response_model=list[AssignedFarmResponse],
    summary="Get farms assigned to technician",
)
def get_assigned_farms(
    technician_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    tech_id_str = str(technician_id)
    _verify_technician_self_or_admin(tech_id_str, current_user)
    return technician_controller.get_assigned_farms(tech_id_str)


@router.get(
    "/{technician_id}/farms/{farm_id}",
    response_model=TechnicianFarmDetailResponse,
    summary="Get assigned farm detail",
)
def get_assigned_farm_detail(
    technician_id: UUID,
    farm_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    tech_id_str = str(technician_id)
    farm_id_str = str(farm_id)
    _verify_technician_self_or_admin(tech_id_str, current_user)
    _verify_technician_farm_assignment(tech_id_str, farm_id_str)
    return technician_controller.get_assigned_farm_detail(
        tech_id_str,
        farm_id_str,
    )


@router.get(
    "/{technician_id}/farms/{farm_id}/devices",
    response_model=list[TechnicianDeviceResponse],
    summary="Get devices in an assigned farm",
)
def get_assigned_farm_devices(
    technician_id: UUID,
    farm_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    tech_id_str = str(technician_id)
    farm_id_str = str(farm_id)
    _verify_technician_self_or_admin(tech_id_str, current_user)
    _verify_technician_farm_assignment(tech_id_str, farm_id_str)
    return technician_controller.get_assigned_farm_devices(
        tech_id_str,
        farm_id_str,
    )


@router.get(
    "/{technician_id}/farms/{farm_id}/devices/{device_id}",
    response_model=TechnicianDeviceDetailResponse,
    summary="Get specific device detail in an assigned farm",
)
def get_assigned_farm_device_detail(
    technician_id: UUID,
    farm_id: UUID,
    device_id: str,
    current_user: dict = Depends(get_current_user),
):
    tech_id_str = str(technician_id)
    farm_id_str = str(farm_id)
    _verify_technician_self_or_admin(tech_id_str, current_user)
    _verify_technician_farm_assignment(tech_id_str, farm_id_str)
    return technician_controller.get_assigned_farm_device_detail(
        tech_id_str,
        farm_id_str,
        device_id,
    )


@router.post(
    "/{technician_id}/farms/{farm_id}/assign",
    summary="Assign a farm to a technician (Admin only)",
)
def assign_technician(
    technician_id: UUID,
    farm_id: UUID,
    is_primary: bool = True,
    current_user: dict = Depends(require_admin),
):
    return technician_controller.assign_technician(
        str(technician_id),
        str(farm_id),
        is_primary,
    )
