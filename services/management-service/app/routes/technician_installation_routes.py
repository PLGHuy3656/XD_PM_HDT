from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.adapters.legacy_iot_adapter import legacy_iot_adapter
from app.core.dependencies import get_current_user
from app.repositories.technician_installation_repository import (
    DeviceAlreadyRegisteredError,
    InstallationStateError,
    technician_installation_repository,
)
from app.repositories.user_repository import user_repository
from app.schemas.technician_installation import (
    TechnicianInstallationConfigurationRequest,
    TechnicianInstallationCreateRequest,
    TechnicianInstallationResponse,
    TechnicianInstallationValidationChecks,
    TechnicianInstallationValidationResponse,
)

router = APIRouter(
    prefix="/api/technicians/me/installations",
    tags=["Technician Installation"],
)


def _require_technician(current_user: dict) -> UUID:
    if "TECHNICIAN" not in (current_user.get("roles") or []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Technician role required",
        )
    return UUID(str(current_user["id"]))


def _require_farm_assignment(technician_id: UUID, farm_id: UUID) -> None:
    if not user_repository.is_farm_assigned_to_technician(
        str(technician_id),
        str(farm_id),
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Farm is not actively assigned to this technician",
        )


def _get_installation_or_404(
    installation_id: UUID,
    technician_id: UUID,
) -> dict:
    installation = technician_installation_repository.get_installation(
        installation_id,
        technician_id,
    )
    if installation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Installation not found in the technician's active farm scope",
        )
    return installation


def _translate_installation_error(exc: Exception) -> HTTPException:
    if isinstance(exc, DeviceAlreadyRegisteredError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    if isinstance(exc, InstallationStateError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    raise exc


@router.post(
    "",
    response_model=TechnicianInstallationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register an inactive device in an assigned farm and zone",
)
def register_installation(
    payload: TechnicianInstallationCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    technician_id = _require_technician(current_user)
    _require_farm_assignment(technician_id, payload.farm_id)

    if payload.zone_id is not None:
        zone_farm_id = user_repository.get_farm_id_for_zone(
            str(payload.zone_id),
        )
        if zone_farm_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Zone not found",
            )
        if zone_farm_id != str(payload.farm_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Zone must belong to the selected farm",
            )

    try:
        installation = technician_installation_repository.create_installation(
            technician_id=technician_id,
            node_id=payload.node_id,
            farm_id=payload.farm_id,
            zone_id=payload.zone_id,
            name=payload.name,
            device_type=payload.device_type,
            firmware_version=payload.firmware_version,
            ip_address=payload.ip_address,
        )
    except (DeviceAlreadyRegisteredError, InstallationStateError) as exc:
        raise _translate_installation_error(exc) from exc

    if installation is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Farm assignment changed or the requested location is invalid",
        )
    return installation


@router.get(
    "",
    response_model=list[TechnicianInstallationResponse],
    summary="List installations in the technician's active farm assignments",
)
def list_installations(
    farm_id: UUID | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
):
    technician_id = _require_technician(current_user)
    if farm_id is not None:
        _require_farm_assignment(technician_id, farm_id)
    return technician_installation_repository.list_installations(
        technician_id,
        farm_id,
    )


@router.get(
    "/{installation_id}",
    response_model=TechnicianInstallationResponse,
    summary="Get installation progress and device metadata",
)
def get_installation(
    installation_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    technician_id = _require_technician(current_user)
    return _get_installation_or_404(installation_id, technician_id)


@router.patch(
    "/{installation_id}/configuration",
    response_model=TechnicianInstallationResponse,
    summary="Save device configuration metadata before activation",
)
def save_installation_configuration(
    installation_id: UUID,
    payload: TechnicianInstallationConfigurationRequest,
    current_user: dict = Depends(get_current_user),
):
    technician_id = _require_technician(current_user)
    try:
        installation = technician_installation_repository.save_configuration(
            installation_id,
            technician_id,
            payload.configuration,
        )
    except InstallationStateError as exc:
        raise _translate_installation_error(exc) from exc
    if installation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Installation not found in the technician's active farm scope",
        )
    return installation


@router.post(
    "/{installation_id}/activate",
    response_model=TechnicianInstallationResponse,
    summary="Activate a configured device in the registry",
)
def activate_installation(
    installation_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    technician_id = _require_technician(current_user)
    try:
        installation = technician_installation_repository.activate_installation(
            installation_id,
            technician_id,
        )
    except InstallationStateError as exc:
        raise _translate_installation_error(exc) from exc
    if installation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Installation not found in the technician's active farm scope",
        )
    return installation


@router.post(
    "/{installation_id}/validate",
    response_model=TechnicianInstallationValidationResponse,
    summary="Verify activation, configuration, farm/zone link, and connectivity",
)
def validate_installation(
    installation_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    technician_id = _require_technician(current_user)
    installation = _get_installation_or_404(installation_id, technician_id)
    if installation["status"] != "ACTIVATED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only an activated installation can be validated",
        )

    runtime_states = legacy_iot_adapter.get_devices_runtime_state(
        [str(installation["device_id"])],
    )
    checks = TechnicianInstallationValidationChecks(
        device_registered=True,
        device_activated=installation["is_active"],
        farm_zone_linked=installation["farm_zone_linked"],
        configuration_present=bool(installation["configuration"]),
        connectivity=str(installation["device_id"]) in runtime_states,
    )
    failure_reasons = [
        name
        for name, passed in checks.model_dump().items()
        if not passed
    ]
    checked_at = datetime.now(timezone.utc).isoformat()
    report = {
        "checked_at": checked_at,
        "passed": not failure_reasons,
        "checks": checks.model_dump(),
        "failure_reasons": failure_reasons,
    }

    try:
        updated_installation = (
            technician_installation_repository.save_validation_report(
                installation_id,
                technician_id,
                passed=not failure_reasons,
                report=report,
            )
        )
    except InstallationStateError as exc:
        raise _translate_installation_error(exc) from exc
    if updated_installation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Installation not found in the technician's active farm scope",
        )

    return TechnicianInstallationValidationResponse(
        installation=updated_installation,
        passed=not failure_reasons,
        checked_at=checked_at,
        checks=checks,
        failure_reasons=failure_reasons,
    )


@router.post(
    "/{installation_id}/handover",
    response_model=TechnicianInstallationResponse,
    summary="Complete handover after installation validation passes",
)
def hand_over_installation(
    installation_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    technician_id = _require_technician(current_user)
    try:
        installation = technician_installation_repository.hand_over_installation(
            installation_id,
            technician_id,
        )
    except InstallationStateError as exc:
        raise _translate_installation_error(exc) from exc
    if installation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Installation not found in the technician's active farm scope",
        )
    return installation
