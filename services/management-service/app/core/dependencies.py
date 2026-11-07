from fastapi import Depends, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from app.core.security import decode_access_token
from app.repositories.user_repository import user_repository
from app.services.auth_service import auth_service

# Bearer scheme enables Swagger UI "Authorize" dialog
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """
    Validates Bearer JWT and resolves the authoritative user from management_db.
    Raises HTTP 401 for missing, invalid, or expired tokens.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = auth_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_roles(*allowed_roles: str):
    """
    Dependency factory enforcing role-based access control.
    Raises HTTP 403 if the user does not possess at least one of the allowed roles.
    """
    def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_roles = current_user.get("roles") or []
        if not any(r in allowed_roles for r in user_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Insufficient role permissions",
            )
        return current_user

    return role_checker


# Convenient role dependency shortcuts
require_admin = require_roles("ADMIN")
require_management_user = require_roles("ADMIN", "FARM_OWNER", "TECHNICIAN")


def verify_farm_resource_access(current_user: dict, farm_id: str):
    """
    Authoritative resource check for a farm.
    - ADMIN: full access.
    - TECHNICIAN: must have an active assignment to the farm in technician_assignments.
    - FARM_OWNER: must own the farm in management_db (reported as schema gap if owner_id missing).
    """
    roles = current_user.get("roles") or []

    if "ADMIN" in roles:
        return True

    if "TECHNICIAN" in roles:
        user_id = current_user["id"]
        if user_repository.is_farm_assigned_to_technician(user_id, farm_id):
            return True
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Farm not assigned to technician",
        )

    if "FARM_OWNER" in roles:
        user_id = current_user["id"]
        if user_repository.is_farm_owned_by_user(user_id, farm_id):
            return True
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Farm not owned by user",
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Forbidden: Role not authorized for farm resources",
    )


def require_farm_access(farm_id: str = Path(...), current_user: dict = Depends(get_current_user)) -> str:
    """Dependency verifying that the current user is authorized to access the specified farm."""
    verify_farm_resource_access(current_user, farm_id)
    return farm_id


def require_zone_access(zone_id: str = Path(...), current_user: dict = Depends(get_current_user)) -> str:
    """Dependency verifying that the current user is authorized to access the parent farm of the zone."""
    farm_id = user_repository.get_farm_id_for_zone(zone_id)
    if not farm_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )
    verify_farm_resource_access(current_user, farm_id)
    return zone_id


def require_device_access(device_id: str = Path(...), current_user: dict = Depends(get_current_user)) -> str:
    """Dependency verifying that the current user is authorized to access the parent farm of the device."""
    farm_id = user_repository.get_farm_id_for_device(device_id)
    if not farm_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    verify_farm_resource_access(current_user, farm_id)
    return device_id


def check_technician_permission(technician_id: str, farm_id: str, required_permission: str = "MONITOR") -> bool:
    """
    Helper for future control_permission (MONITOR vs OPERATE).
    control_permission is not currently present in the schema (SCHEMA GAP).
    Defaults to checking if technician has active assignment.
    """
    return user_repository.is_farm_assigned_to_technician(technician_id, farm_id)
