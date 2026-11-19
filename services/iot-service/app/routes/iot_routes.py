from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.mqtt.topics import TopicParseError
from app.routes.dependencies import (
    get_command_service,
    get_presence_service,
    get_telemetry_service,
)
from app.schemas.api import (
    CommandResponse,
    ConfigCommandRequest,
    PresenceResponse,
    RelayCommandRequest,
    TelemetryResponse,
)
from app.schemas.diagnostics import (
    AdminDeviceRegistryItem,
    DeviceDiagnosticDetail,
    DiagnosticSummary,
    InstallationChecklistResponse,
    ProvisionDeviceRequest,
)
from app.services.command_service import DeviceCommandService
from app.services.diagnostics_service import (
    DiagnosticsService,
    default_diagnostics_service,
)
from app.services.presence_service import DevicePresenceService
from app.services.telemetry_service import TelemetryService

router = APIRouter(prefix="/api/iot", tags=["IoT"])


@router.get(
    "/devices/{device_id}/telemetry/latest",
    response_model=TelemetryResponse,
    summary="Get latest normalized telemetry for a device",
)
def get_latest_telemetry(
    device_id: str,
    svc: TelemetryService = Depends(get_telemetry_service),
) -> TelemetryResponse:
    telemetry = svc.get_latest(device_id)
    if telemetry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No telemetry found for device '{device_id}'",
        )
    return TelemetryResponse.from_domain(telemetry)


@router.get(
    "/devices/{device_id}/telemetry",
    response_model=list[TelemetryResponse],
    summary="List recent telemetry history for a device (prototype in-memory store)",
)
def list_telemetry_history(
    device_id: str,
    limit: int = Query(default=50, ge=1, le=500, description="Maximum records to return (1..500)"),
    svc: TelemetryService = Depends(get_telemetry_service),
) -> list[TelemetryResponse]:
    records = svc.list_by_device(device_id, limit=limit)
    return [TelemetryResponse.from_domain(rec) for rec in records]


@router.get(
    "/devices/presence",
    response_model=list[PresenceResponse],
    summary="List runtime presence states for all tracked devices",
)
def list_device_presence(
    svc: DevicePresenceService = Depends(get_presence_service),
) -> list[PresenceResponse]:
    records = svc.list_all()
    return [PresenceResponse.from_domain(rec) for rec in records]


@router.get(
    "/devices/{device_id}/presence",
    response_model=PresenceResponse,
    summary="Get current runtime presence state for a specific device",
)
def get_device_presence(
    device_id: str,
    svc: DevicePresenceService = Depends(get_presence_service),
) -> PresenceResponse:
    presence = svc.get_presence(device_id)
    if presence is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Presence not found for device '{device_id}'",
        )
    return PresenceResponse.from_domain(presence)


@router.post(
    "/devices/{device_id}/commands/relay",
    response_model=CommandResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Issue manual SET_RELAY actuator command to a device",
)
def create_relay_command(
    device_id: str,
    body: RelayCommandRequest,
    svc: DeviceCommandService = Depends(get_command_service),
) -> CommandResponse:
    try:
        cmd = svc.send_set_relay_command(
            device_id=device_id,
            target=body.target,
            state=body.state,
        )
    except (TopicParseError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return CommandResponse.from_domain(cmd)


@router.post(
    "/devices/{device_id}/commands/config",
    response_model=CommandResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Issue UPDATE_THRESHOLDS environmental configuration command to a device",
)
def create_config_command(
    device_id: str,
    body: ConfigCommandRequest,
    svc: DeviceCommandService = Depends(get_command_service),
) -> CommandResponse:
    try:
        cmd = svc.send_update_thresholds_command(
            device_id=device_id,
            target_temp=body.targetTemp,
            target_hum=body.targetHum,
            is_auto_mode=body.isAutoMode,
        )
    except (TopicParseError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return CommandResponse.from_domain(cmd)


@router.get(
    "/commands/{command_id}",
    response_model=CommandResponse,
    summary="Query the lifecycle state of a specific command",
)
def get_command_state(
    command_id: str,
    svc: DeviceCommandService = Depends(get_command_service),
) -> CommandResponse:
    cmd = svc.get_command(command_id)
    if cmd is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Command '{command_id}' not found",
        )
    return CommandResponse.from_domain(cmd)


# --- Provisioning, Installation & Diagnostics Routes ---

@router.get(
    "/devices/registry-summary",
    response_model=list[AdminDeviceRegistryItem],
    summary="Get overview of all registered devices with provisioning status for Administrator",
)
def get_registry_summary() -> list[AdminDeviceRegistryItem]:
    return default_diagnostics_service.get_admin_registry_summary()


@router.get(
    "/diagnostics/summary",
    response_model=DiagnosticSummary,
    summary="Get aggregate health and diagnostic counts for Technician Dashboard",
)
def get_diagnostics_summary() -> DiagnosticSummary:
    return default_diagnostics_service.get_diagnostic_summary()


@router.get(
    "/devices/{device_id}/diagnostics",
    response_model=DeviceDiagnosticDetail,
    summary="Get detailed technical diagnostic signals for a device (Technician)",
)
def get_device_diagnostics(device_id: str) -> DeviceDiagnosticDetail:
    diag = default_diagnostics_service.get_device_diagnostics(device_id)
    if diag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found",
        )
    return diag


@router.get(
    "/devices/{device_id}/installation-checklist",
    response_model=InstallationChecklistResponse,
    summary="Check installation and readiness checklist for a device (Technician)",
)
def get_installation_checklist(device_id: str) -> InstallationChecklistResponse:
    return default_diagnostics_service.get_installation_checklist(device_id)


@router.post(
    "/devices/{device_id}/provision",
    status_code=status.HTTP_200_OK,
    summary="Provision and assign a device to a farm and zone (Technician)",
)
def provision_device(device_id: str, body: ProvisionDeviceRequest):
    return default_diagnostics_service.provision_device(device_id, body)


