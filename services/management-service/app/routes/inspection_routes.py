"""INT03-R1: Owner "Yêu cầu kiểm tra" (Inspection Request) minimum viable workflow.

RBAC is enforced here (and again at the Gateway):
- FARM_OWNER creates for a farm they own (farm must be APPROVED), may cancel NEW/ACCEPTED.
- TECHNICIAN sees requests of farms actively assigned to them; only the assigned technician can
  accept/start/complete, and only while still actively assigned to that farm.
- ADMIN sees all requests and assigns a technician actively assigned to the farm (NEW only).
Out-of-scope or unknown ids fail closed with 404. assignee ids are never taken from the client
for technician actions (the caller's own id is used).
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app import inspection_events
from app.core.dependencies import get_current_user, require_admin, require_roles
from app.repositories.inspection_repository import inspection_repository, is_uuid
from app.repositories.user_repository import user_repository
from app.repositories.zone_repository import zone_repository
from app.schemas.inspection import (
    InspectionAssignRequest,
    InspectionCompleteRequest,
    InspectionNoteRequest,
    InspectionRequestCreate,
    InspectionRequestResponse,
)

router = APIRouter(prefix="/api/inspection-requests", tags=["Inspection Requests"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection request not found")


def _conflict(msg: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)


def _can_view(user: dict, req: dict) -> bool:
    roles = user.get("roles") or []
    uid = str(user["id"])
    if "ADMIN" in roles:
        return True
    if "FARM_OWNER" in roles and user_repository.is_farm_owned_by_user(uid, req["farm_id"]):
        return True
    if "TECHNICIAN" in roles and user_repository.is_farm_assigned_to_technician(uid, req["farm_id"]):
        return True
    return False


def _load_visible(request_id: str, user: dict, with_history: bool = True) -> dict:
    req = inspection_repository.get(request_id, with_history=with_history)
    if not req or not _can_view(user, req):
        raise _NOT_FOUND
    return req


@router.get("", response_model=list[InspectionRequestResponse])
def list_inspection_requests(
    status_filter: str | None = Query(default=None, alias="status", pattern="^(NEW|ACCEPTED|IN_PROGRESS|COMPLETED|CANCELLED)$"),
    farm_id: str | None = Query(default=None),
    unassigned: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=200),
    current_user: dict = Depends(require_roles("ADMIN", "FARM_OWNER", "TECHNICIAN")),
):
    farm_uuid = None
    if farm_id:
        farm_uuid = user_repository.resolve_farm_uuid(farm_id)
        if not farm_uuid:
            return []
    return inspection_repository.list_for_user(current_user, status_filter, farm_uuid, unassigned, limit)


@router.get("/{request_id}", response_model=InspectionRequestResponse)
def get_inspection_request(request_id: str, current_user: dict = Depends(get_current_user)):
    return _load_visible(request_id, current_user)


@router.post("", response_model=InspectionRequestResponse, status_code=status.HTTP_201_CREATED)
def create_inspection_request(
    payload: InspectionRequestCreate,
    current_user: dict = Depends(require_roles("FARM_OWNER")),
):
    uid = str(current_user["id"])
    farm_uuid = user_repository.resolve_farm_uuid(payload.farm_id)
    if not farm_uuid or not user_repository.is_farm_owned_by_user(uid, farm_uuid):
        # Owner B must not learn whether Farm A exists.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
    from app.repositories.farm_repository import farm_repository

    farm = farm_repository.get_farm_by_id(farm_uuid)
    if not farm or farm.get("approval_status") != "APPROVED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Farm must be approved before requesting an inspection")
    zone_id = payload.zone_id or None
    device_id = payload.device_id or None
    if zone_id:
        zone = zone_repository.get_zone_by_id(zone_id) if is_uuid(zone_id) else None
        if not zone or str(zone["farm_id"]) != str(farm_uuid):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="zone_id does not belong to farm")
    if device_id:
        if not is_uuid(device_id) or str(user_repository.get_farm_id_for_device(device_id) or "") != str(farm_uuid):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="device_id does not belong to farm")
    technician_id = inspection_repository.pick_default_technician(farm_uuid)
    req = inspection_repository.create(
        farm_id=farm_uuid, title=payload.title, description=payload.description,
        priority=payload.priority, zone_id=zone_id, device_id=device_id,
        requested_by=uid, assigned_technician_id=technician_id,
    )
    inspection_events.created(req)
    return req


@router.post("/{request_id}/assign", response_model=InspectionRequestResponse)
def assign_inspection_request(
    request_id: str,
    payload: InspectionAssignRequest,
    current_user: dict = Depends(require_admin),
):
    req = _load_visible(request_id, current_user, with_history=False)
    if req["status"] != "NEW":
        raise _conflict("Only NEW requests can be (re)assigned")
    if not is_uuid(payload.technician_id) or not user_repository.is_farm_assigned_to_technician(payload.technician_id, req["farm_id"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Technician is not actively assigned to this farm")
    updated = inspection_repository.assign(request_id, payload.technician_id, str(current_user["id"]))
    if not updated:
        raise _conflict("Request changed concurrently or already assigned to this technician")
    inspection_events.assigned(updated, str(current_user["id"]))
    return updated


def _technician_action(request_id: str, user: dict, action: str, result_note: str | None = None):
    uid = str(user["id"])
    req = _load_visible(request_id, user, with_history=False)  # 404 when farm not assigned to caller
    if req.get("assigned_technician_id") != uid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Request is not assigned to you")
    previous = req["status"]
    if action == "accept":
        updated = inspection_repository.accept(request_id, uid)
    elif action == "start":
        updated = inspection_repository.start(request_id, uid)
    else:
        updated = inspection_repository.complete(request_id, uid, result_note or "")
    if not updated:
        raise _conflict(f"Invalid transition from {previous}")
    inspection_events.status_changed(updated, uid, previous)
    return updated


@router.post("/{request_id}/accept", response_model=InspectionRequestResponse)
def accept_inspection_request(request_id: str, current_user: dict = Depends(require_roles("TECHNICIAN"))):
    return _technician_action(request_id, current_user, "accept")


@router.post("/{request_id}/start", response_model=InspectionRequestResponse)
def start_inspection_request(request_id: str, current_user: dict = Depends(require_roles("TECHNICIAN"))):
    return _technician_action(request_id, current_user, "start")


@router.post("/{request_id}/complete", response_model=InspectionRequestResponse)
def complete_inspection_request(
    request_id: str,
    payload: InspectionCompleteRequest,
    current_user: dict = Depends(require_roles("TECHNICIAN")),
):
    return _technician_action(request_id, current_user, "complete", payload.result_note)


@router.post("/{request_id}/cancel", response_model=InspectionRequestResponse)
def cancel_inspection_request(
    request_id: str,
    payload: InspectionNoteRequest | None = None,
    current_user: dict = Depends(require_roles("FARM_OWNER")),
):
    uid = str(current_user["id"])
    req = _load_visible(request_id, current_user, with_history=False)
    if req["requested_by"] != uid and not user_repository.is_farm_owned_by_user(uid, req["farm_id"]):
        raise _NOT_FOUND
    previous = req["status"]
    updated = inspection_repository.cancel(request_id, uid, payload.note if payload else None)
    if not updated:
        raise _conflict(f"Cannot cancel a request in status {previous}")
    inspection_events.status_changed(updated, uid, previous)
    return updated
