
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.services.control_service import (
    get_control_commands as fetch_control_commands,
    get_control_state as fetch_control_state,
)


router = APIRouter(
    prefix="/api/devices",
    tags=["Environmental Control"],
)


@router.get("/{device_id}/control")
def get_control_state(device_id: UUID):
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
):
    commands = fetch_control_commands(device_id, limit)
    if commands is None:
        raise HTTPException(
            status_code=404,
            detail="Active device not found",
        )

    return commands
