from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.controllers.device_controller import device_controller
from app.core.dependencies import (
    get_current_user,
    require_roles,
    verify_farm_resource_access,
)
from app.repositories.user_repository import user_repository
from app.repositories.zone_repository import zone_repository
from app.schemas.device import (
    DeviceCreateRequest,
    DeviceRegistryResponse,
    DeviceUpdateRequest,
)

router = APIRouter(
    prefix="/api/devices",
    tags=["Device Registry"],
)


@router.get(
    "",
    response_model=list[DeviceRegistryResponse],
    summary="List registered devices with farm filtering and authorization",
)
def list_devices(
    farm_id: str | None = Query(None, description="Filter by Farm / House ID"),
    farmId: str | None = Query(None, description="Filter by Farm / House ID (alias)"),
    zone_id: str | None = Query(None, description="Filter by Zone ID"),
    current_user: dict = Depends(get_current_user),
):
    # Parameter normalization & conflict check
    effective_farm_id = None
    if farm_id and farmId and farm_id.strip() != farmId.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ambiguous or conflicting farm_id/farmId parameters",
        )
    effective_farm_id = (farm_id or farmId)
    if effective_farm_id:
        effective_farm_id = effective_farm_id.strip()

    roles = current_user.get("roles") or []
    if not effective_farm_id and "ADMIN" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: 'farm_id' parameter is required for non-admin users",
        )

    canonical_farm_uuid = None
    if effective_farm_id:
        verify_farm_resource_access(current_user, effective_farm_id)
        # Normalize farm_code to canonical UUID to prevent PostgreSQL UUID cast error
        canonical_farm_uuid = user_repository.resolve_farm_uuid(effective_farm_id)
        if not canonical_farm_uuid:
            return []

    return device_controller.list_devices(farm_id=canonical_farm_uuid, zone_id=zone_id)


@router.get(
    "/{device_id}",
    response_model=DeviceRegistryResponse,
    summary="Get registered device metadata with parent farm resource authorization",
)
def get_device(device_id: str, current_user: dict = Depends(get_current_user)):
    parent_farm_id = user_repository.get_farm_id_for_device(device_id)
    if not parent_farm_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    verify_farm_resource_access(current_user, parent_farm_id)
    return device_controller.get_device(device_id)


@router.post(
    "",
    response_model=DeviceRegistryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new device in a farm (Admin or owning Farm Owner)",
)
def create_device(
    payload: DeviceCreateRequest,
    current_user: dict = Depends(require_roles("ADMIN", "FARM_OWNER")),
):
    verify_farm_resource_access(current_user, payload.farm_id)
    farm_uuid = user_repository.resolve_farm_uuid(payload.farm_id)
    if not farm_uuid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
    if payload.zone_id:
        zone = zone_repository.get_zone_by_id(payload.zone_id)
        if not zone or str(zone["farm_id"]) != str(farm_uuid):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="zone_id does not belong to target farm",
            )
    return device_controller.create_device(
        node_id=payload.node_id,
        farm_uuid=farm_uuid,
        zone_id=payload.zone_id,
        name=payload.name,
        device_type=payload.device_type,
        firmware_version=payload.firmware_version,
        ip_address=payload.ip_address,
    )


@router.put(
    "/{device_id}",
    response_model=DeviceRegistryResponse,
    summary="Update device metadata (Admin or owning Farm Owner)",
)
def update_device(
    device_id: str,
    payload: DeviceUpdateRequest,
    current_user: dict = Depends(require_roles("ADMIN", "FARM_OWNER")),
):
    parent_farm_id = user_repository.get_farm_id_for_device(device_id)
    if not parent_farm_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    verify_farm_resource_access(current_user, parent_farm_id)
    if payload.zone_id:
        zone = zone_repository.get_zone_by_id(payload.zone_id)
        if not zone or str(zone["farm_id"]) != str(parent_farm_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="zone_id does not belong to device's parent farm",
            )
    return device_controller.update_device(
        device_id=device_id,
        name=payload.name,
        device_type=payload.device_type,
        zone_id=payload.zone_id,
        firmware_version=payload.firmware_version,
        ip_address=payload.ip_address,
        is_active=payload.is_active,
    )


@router.delete(
    "/{device_id}",
    summary="Delete a device from registry (Admin or owning Farm Owner)",
)
def delete_device(
    device_id: str,
    current_user: dict = Depends(require_roles("ADMIN", "FARM_OWNER")),
):
    parent_farm_id = user_repository.get_farm_id_for_device(device_id)
    if not parent_farm_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    verify_farm_resource_access(current_user, parent_farm_id)
    return device_controller.delete_device(device_id)


camera_router = APIRouter(
    prefix="/api/cameras",
    tags=["Camera Registry"],
)


@camera_router.get(
    "/{camera_id}",
    response_model=DeviceRegistryResponse,
    summary="Get registered camera metadata with parent farm resource authorization",
)
def get_camera(camera_id: str, current_user: dict = Depends(get_current_user)):
    """Authoritatively resolves camera metadata (CP13 hardening R3).

    Order matters to avoid cross-tenant metadata disclosure:
    1. Resolve the parent farm.
    2. Verify the caller's farm authorization BEFORE reading any device detail.
    3. Only then check device_type.
    Unknown ids, devices of another tenant and non-CAMERA devices all receive the
    same 404 "Camera not found", so callers cannot enumerate other farms' device
    ids or learn a device's real type.
    """
    not_found = HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Camera not found",
    )
    parent_farm_id = user_repository.get_farm_id_for_device(camera_id)
    if not parent_farm_id:
        raise not_found
    try:
        verify_farm_resource_access(current_user, str(parent_farm_id))
    except HTTPException as exc:
        if exc.status_code == status.HTTP_403_FORBIDDEN:
            raise not_found from None
        raise

    device = device_controller.get_device(camera_id)
    dev_type = device.get("device_type") if isinstance(device, dict) else getattr(device, "device_type", None)
    if str(dev_type or "").upper() != "CAMERA":
        raise not_found
    return device

