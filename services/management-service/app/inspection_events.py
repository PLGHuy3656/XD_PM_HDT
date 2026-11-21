"""INT03-R1: Inspection Request domain events (recipients resolved from management_db)."""
from __future__ import annotations

from app import events
from app.business_events import _safe

STATUS_LABELS = {
    "NEW": "Mới",
    "ACCEPTED": "Đã tiếp nhận",
    "IN_PROGRESS": "Đang kiểm tra",
    "COMPLETED": "Hoàn thành",
    "CANCELLED": "Đã hủy",
}


def _payload(req: dict, **extra) -> dict:
    base = {
        "inspectionRequestId": req["id"],
        "requestCode": req["request_code"],
        "farmId": req["farm_id"],
        "farmName": req.get("farm_name"),
        "zoneId": req.get("zone_id"),
        "zoneName": req.get("zone_name"),
        "deviceId": req.get("device_id"),
        "deviceName": req.get("device_name"),
        "title": req.get("title"),
        "priority": req.get("priority"),
        "status": req.get("status"),
        "statusLabel": STATUS_LABELS.get(req.get("status")),
        "assignedTechnicianId": req.get("assigned_technician_id"),
        "assignedTechnicianName": req.get("assigned_technician_name"),
        "requestedBy": req.get("requested_by"),
        "requestedByName": req.get("requested_by_name"),
    }
    base.update(extra)
    return base


@_safe
def created(req: dict) -> str | None:
    if req.get("assigned_technician_id"):
        return events.record_event(
            "management.inspection_request.created",
            _payload(req, link="/technician/alerts?tab=inspections&requestId=" + req["id"], queue="TECHNICIAN"),
            [req["assigned_technician_id"]],
        )
    # No technician can be linked: Admin assignment queue (not a fake assignment).
    return events.record_event(
        "management.inspection_request.created",
        _payload(req, link="/admin/farms?tab=inspections&requestId=" + req["id"], queue="ADMIN"),
        events.admin_user_ids(),
    )


@_safe
def assigned(req: dict, admin_id: str) -> str | None:
    recipients = [req["assigned_technician_id"], req["requested_by"]]
    return events.record_event(
        "management.inspection_request.assigned",
        _payload(req, actorId=admin_id, link="/technician/alerts?tab=inspections&requestId=" + req["id"],
                 ownerLink="/owner/farms?requestId=" + req["id"]),
        recipients,
    )


@_safe
def status_changed(req: dict, actor_id: str, previous_status: str | None) -> str | None:
    recipients = {req["requested_by"]}
    if req.get("assigned_technician_id"):
        recipients.add(req["assigned_technician_id"])
    recipients.discard(actor_id)  # the actor already sees the change in the UI
    return events.record_event(
        "management.inspection_request.status_changed",
        _payload(req, previousStatus=previous_status, actorId=actor_id,
                 resultNote=req.get("result_note") if req.get("status") == "COMPLETED" else None,
                 link="/owner/farms?requestId=" + req["id"],
                 technicianLink="/technician/alerts?tab=inspections&requestId=" + req["id"]),
        recipients,
    )


@_safe
def requeued(request_id: str, actor_id: str) -> str | None:
    from app.repositories.inspection_repository import inspection_repository

    req = inspection_repository.get(request_id)
    if not req:
        return None
    return events.record_event(
        "management.inspection_request.requeued",
        _payload(req, actorId=actor_id, link="/admin/farms?tab=inspections&requestId=" + req["id"]),
        events.admin_user_ids(exclude=actor_id) or events.admin_user_ids(),
    )
