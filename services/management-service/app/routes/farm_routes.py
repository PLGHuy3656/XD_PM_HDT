from uuid import UUID
from fastapi import APIRouter
from app.controllers.farm_controller import farm_controller
from app.schemas.farm import FarmDetailResponse, FarmResponse

router = APIRouter(
    prefix="/api/farms",
    tags=["Farms"],
)


@router.get("", response_model=list[FarmResponse])
def list_farms():
    return farm_controller.list_farms()


@router.get("/{farm_id}", response_model=FarmDetailResponse)
def get_farm(farm_id: str):
    return farm_controller.get_farm(farm_id)
