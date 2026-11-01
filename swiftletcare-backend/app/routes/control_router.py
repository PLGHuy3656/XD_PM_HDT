
from typing import Annotated, Union
from uuid import UUID

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Query,
    Request,
)
from pydantic import Field

from app.schemas.control import (
    RelayCommandRequest,
    ThresholdCommandRequest,
)
from app.services.control_service import (
    get_control_commands as fetch_control_commands,
    get_control_device_node_id,
    get_control_state as fetch_control_state,
    prepare_relay_command,
    prepare_threshold_command,
    send_prepared_command,
)
from app.services.management_authorization import (
    require_device_monitor_permission,
    require_device_operate_permission,
)


router = APIRouter(
    prefix="/api/devices",
    tags=["Environmental Control"],
)

ControlCommandRequest = Annotated[
    Union[RelayCommandRequest, ThresholdCommandRequest],
    Field(discriminator="action"),
]


@router.get("/{device_id}/control")
def get_control_state(
    device_id: UUID,
    authorization: str = Header(...),
):
    node_id = get_control_device_node_id(device_id)
    if node_id is None:
        raise HTTPException(
            status_code=404,
            detail="Active device not found",
        )
    require_device_monitor_permission(node_id, authorization)

    state = fetch_control_state(device_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail="Active device not found",
        )

    return state


@router.get("/{device_id}/control/commands")
def get_control_commands(
    device_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    authorization: str = Header(...),
):
    node_id = get_control_device_node_id(device_id)
    if node_id is None:
        raise HTTPException(
            status_code=404,
            detail="Active device not found",
        )
    require_device_monitor_permission(node_id, authorization)

    commands = fetch_control_commands(device_id, limit)
    if commands is None:
        raise HTTPException(
            status_code=404,
            detail="Active device not found",
        )

    return commands


@router.post("/{device_id}/control/commands")
def send_control_command(
    device_id: UUID,
    body: ControlCommandRequest,
    request: Request,
    authorization: str = Header(...),
):
    node_id = get_control_device_node_id(device_id)
    if node_id is None:
        raise HTTPException(
            status_code=404,
            detail="Active device not found",
        )

    require_device_operate_permission(
        node_id,
        authorization,
    )

    mqtt_client = getattr(request.app.state, "mqtt_client", None)
    if mqtt_client is None:
        raise HTTPException(
            status_code=503,
            detail="MQTT client is not initialized",
        )

    if isinstance(body, RelayCommandRequest):
        prepared = prepare_relay_command(device_id, body)
    else:
        prepared = prepare_threshold_command(device_id, body)

    return send_prepared_command(
        device_id,
        prepared,
        mqtt_client,
    )