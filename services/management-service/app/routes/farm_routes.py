from fastapi import APIRouter, Depends

from app.controllers.farm_controller import farm_controller
from app.core.dependencies import get_current_user, verify_farm_resource_access
from app.schemas.farm import FarmDetailResponse, FarmResponse

router = APIRouter(
    prefix="/api/farms",
    tags=["Farms"],
)


@router.get(
    "",
    response_model=list[FarmResponse],
    summary="List farms accessible to current user",
)
def list_farms(current_user: dict = Depends(get_current_user)):
    return farm_controller.list_farms()


@router.get(
    "/{farm_id}",
    response_model=FarmDetailResponse,
    summary="Get farm details with resource authorization",
)
def get_farm(farm_id: str, current_user: dict = Depends(get_current_user)):
    verify_farm_resource_access(current_user, farm_id)
    return farm_controller.get_farm(farm_id)
