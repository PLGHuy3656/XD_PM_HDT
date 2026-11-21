"""INT03-R1: emit Management business events after successful commits.

Every helper is best-effort: it never raises into the request (the business change is already
committed) and never claims a notification was delivered. See app/events.py for delivery limits.
"""
from __future__ import annotations

import logging
from typing import Any

from app import events

logger = logging.getLogger(__name__)


def _safe(fn):
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            logger.exception("Emitting business event via %s failed", fn.__name__)
            return None

    wrapper.__name__ = fn.__name__
    return wrapper


def _val(obj: Any, key: str):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


@_safe
def user_created(user: Any, actor_id: str | None) -> str | None:
    # All active admins, including the creating admin: account creation is admin-only in this system
    # (no self-registration endpoint exists), and a single-admin deployment must still see the record.
    recipients = events.admin_user_ids()
    return events.record_event(
        "management.user.created",
        {
            "userId": str(_val(user, "id")),
            "fullName": _val(user, "full_name"),
            "email": _val(user, "email"),
            "roles": list(_val(user, "roles") or []),
            "actorId": actor_id,
            "link": "/admin/users",
        },
        recipients,
    )


@_safe
def farm_approval_requested(farm: dict, requester_id: str) -> str | None:
    if (farm or {}).get("approval_status") != "PENDING":
        return None
    return events.record_event(
        "management.farm.approval_requested",
        {
            "farmId": farm["farm_id"],
            "farmCode": farm.get("farm_code"),
            "farmName": farm.get("farm_name"),
            "requestedBy": requester_id,
            "requestedByName": events.user_display_name(requester_id),
            "approvalStatus": "PENDING",
            "link": f"/admin/farms?farmId={farm['farm_id']}",
        },
        events.admin_user_ids(),
    )


@_safe
def farm_decision(farm: dict, decision: str, admin_id: str, reason: str | None = None) -> str | None:
    ctx = events.farm_context(farm["farm_id"])
    if not ctx or not ctx["owner_id"]:
        return None
    event_type = "management.farm.approved" if decision == "APPROVED" else "management.farm.rejected"
    return events.record_event(
        event_type,
        {
            "farmId": ctx["farm_id"],
            "farmCode": ctx["farm_code"],
            "farmName": ctx["farm_name"],
            "decision": decision,
            "decidedBy": admin_id,
            "decidedAt": farm.get("approved_at"),
            "rejectionReason": reason if decision == "REJECTED" else None,
            "link": "/owner/farms",
        },
        [ctx["owner_id"]],
    )


@_safe
def technician_assignment(farm_id: str, technician_id: str, assigned: bool, actor_id: str) -> str | None:
    ctx = events.farm_context(farm_id)
    if not ctx:
        return None
    recipients = [technician_id]
    if ctx["owner_id"]:
        recipients.append(ctx["owner_id"])
    return events.record_event(
        "management.technician.assigned" if assigned else "management.technician.unassigned",
        {
            "farmId": ctx["farm_id"],
            "farmCode": ctx["farm_code"],
            "farmName": ctx["farm_name"],
            "technicianId": technician_id,
            "technicianName": events.user_display_name(technician_id),
            "actorId": actor_id,
            "link": "/owner/farms",
            "technicianLink": "/technician/dashboard",
        },
        recipients,
    )


@_safe
def device_registered(device: Any, actor: dict) -> str | None:
    farm_id = str(_val(device, "farm_id"))
    ctx = events.farm_context(farm_id)
    if not ctx or not ctx["owner_id"] or ctx["owner_id"] == str(actor.get("id")):
        return None  # the owner registering their own device does not need to be told
    return events.record_event(
        "management.device.registered",
        {
            "farmId": ctx["farm_id"],
            "farmName": ctx["farm_name"],
            "deviceId": str(_val(device, "device_id")),
            "nodeId": _val(device, "node_id"),
            "deviceName": _val(device, "name"),
            "deviceType": _val(device, "device_type"),
            "zoneId": _val(device, "zone_id"),
            "zoneName": _val(device, "zone_name"),
            "registrationStatus": "REGISTERED",
            "registeredBy": str(actor.get("id")),
            "registeredByName": actor.get("full_name"),
            "link": "/owner/devices",
        },
        [ctx["owner_id"]],
    )
