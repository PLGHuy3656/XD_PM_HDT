from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import require_roles
from app.schemas.user import (
    UserCreateRequest,
    UserResponse,
    UserStatusUpdateRequest,
    UserUpdateRequest,
)
from app.services.user_service import UserService, user_service

router = APIRouter(
    prefix="/api/users",
    tags=["Users (Admin)"],
    dependencies=[Depends(require_roles("ADMIN"))],
)


@router.get("", response_model=List[UserResponse])
def list_users(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: UserService = Depends(lambda: user_service),
):
    """Lists all registered users (Admin only)."""
    return service.list_users(limit=limit, offset=offset)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    req: UserCreateRequest,
    service: UserService = Depends(lambda: user_service),
):
    """Creates a new user account with role assignment (Admin only)."""
    try:
        return service.create_user(req)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{user_id}", response_model=UserResponse)
def get_user_detail(
    user_id: str,
    service: UserService = Depends(lambda: user_service),
):
    """Gets details for a specific user (Admin only)."""
    user = service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
    return user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    req: UserUpdateRequest,
    service: UserService = Depends(lambda: user_service),
):
    """Updates user information and roles (Admin only)."""
    updated = service.update_user(user_id, req)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
    return updated


@router.patch("/{user_id}/status", status_code=status.HTTP_200_OK)
def update_user_status(
    user_id: str,
    req: UserStatusUpdateRequest,
    service: UserService = Depends(lambda: user_service),
):
    """Locks, unlocks, or deactivates a user account (Admin only)."""
    if req.status not in ("ACTIVE", "LOCKED", "INACTIVE"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status: {req.status}")
    ok = service.update_user_status(user_id, req.status)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
    return {"status": "ok", "user_id": user_id, "new_status": req.status}


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(
    user_id: str,
    service: UserService = Depends(lambda: user_service),
):
    """Deletes a user account (Admin only)."""
    ok = service.delete_user(user_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
    return {"status": "ok", "deleted_user_id": user_id}
