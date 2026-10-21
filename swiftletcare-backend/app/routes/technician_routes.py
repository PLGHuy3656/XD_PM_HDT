from fastapi import APIRouter

from app.controllers.technician_controller import technician_controller
from app.technician_schema import (
    AssignedFarmResponse,
    TechnicianFarmDetailResponse,
    TechnicianProfileResponse,
)


router = APIRouter(
    prefix="/api/technicians",
    tags=["Technician"],
)


@router.get(
    "/{technician_id}",
    response_model=TechnicianProfileResponse,
)
def get_technician_profile(
    technician_id: str,
):
    return technician_controller.get_profile(
        technician_id,
    )


@router.get(
    "/{technician_id}/farms",
    response_model=list[AssignedFarmResponse],
)
def get_assigned_farms(
    technician_id: str,
):
    return technician_controller.get_assigned_farms(
        technician_id,
    )


@router.get(
    "/{technician_id}/farms/{farm_id}",
    response_model=TechnicianFarmDetailResponse,
)
def get_assigned_farm_detail(
    technician_id: str,
    farm_id: str,
):
    return technician_controller.get_assigned_farm_detail(
        technician_id,
        farm_id,
    )