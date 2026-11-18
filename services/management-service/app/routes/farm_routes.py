from fastapi import APIRouter, Depends, HTTPException, status

from app.controllers.farm_controller import farm_controller
from app.core.dependencies import (
    get_current_user,
    require_admin,
    require_roles,
    verify_farm_resource_access,
)
from app.schemas.farm import (
    FarmCreateRequest,
    FarmDetailResponse,
    FarmResponse,
    FarmUpdateRequest,
)

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
    return farm_controller.list_farms(current_user)


@router.get(
    "/{farm_id}",
    response_model=FarmDetailResponse,
    summary="Get farm details with resource authorization",
)
def get_farm(farm_id: str, current_user: dict = Depends(get_current_user)):
    verify_farm_resource_access(current_user, farm_id)
    return farm_controller.get_farm(farm_id)


@router.post(
    "",
    response_model=FarmDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new farm (Admin or Farm Owner)",
)
def create_farm(
    payload: FarmCreateRequest,
    current_user: dict = Depends(require_roles("ADMIN", "FARM_OWNER")),
):
    roles = current_user.get("roles") or []
    owner_id = payload.owner_id if "ADMIN" in roles else str(current_user["id"])
    return farm_controller.create_farm(
        farm_code=payload.farm_code,
        farm_name=payload.farm_name,
        address=payload.address,
        status_val=payload.status,
        owner_id=owner_id,
    )


@router.put(
    "/{farm_id}",
    response_model=FarmDetailResponse,
    summary="Update farm metadata (Admin or owning Farm Owner)",
)
def update_farm(
    farm_id: str,
    payload: FarmUpdateRequest,
    current_user: dict = Depends(require_roles("ADMIN", "FARM_OWNER")),
):
    verify_farm_resource_access(current_user, farm_id)
    roles = current_user.get("roles") or []
    owner_id = payload.owner_id
    if owner_id is not None and "ADMIN" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ADMIN can reassign farm ownership",
        )
    return farm_controller.update_farm(
        farm_id=farm_id,
        farm_name=payload.farm_name,
        address=payload.address,
        status_val=payload.status,
        owner_id=owner_id,
    )


@router.delete(
    "/{farm_id}",
    summary="Delete a farm (Admin only)",
)
def delete_farm(
    farm_id: str,
    current_user: dict = Depends(require_admin),
):
    return farm_controller.delete_farm(farm_id)
