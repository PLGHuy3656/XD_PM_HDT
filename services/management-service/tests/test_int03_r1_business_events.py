"""INT03-R1: Management business events + Inspection Request RBAC/state machine (unit level, no DB)."""
import uuid

import pytest
from fastapi import HTTPException

from app import business_events, events, inspection_events
import app.routes.farm_routes as farm_routes
import app.routes.inspection_routes as ir_routes
import app.routes.technician_routes as technician_routes
from app.schemas.farm import FarmCreateRequest, FarmRejectRequest
from app.schemas.inspection import InspectionAssignRequest, InspectionCompleteRequest, InspectionRequestCreate

OWNER_A = str(uuid.uuid4())
OWNER_B = str(uuid.uuid4())
TECH_1 = str(uuid.uuid4())
TECH_2 = str(uuid.uuid4())
ADMIN = str(uuid.uuid4())
FARM_A = str(uuid.uuid4())
REQ_ID = str(uuid.uuid4())


# --------------------------------------------------------------------------- envelope

def test_envelope_is_canonical_and_never_contains_secrets():
    env = events.build_envelope(
        "management.user.created",
        {"userId": "u1", "password": "x", "password_hash": "h", "token": "t", "fullName": "A"},
        ["r1", "r1", "r2", None],
    )
    assert env["eventVersion"] == "1.0" and env["producer"] == "management-service"
    uuid.UUID(env["eventId"])
    for k in ("password", "password_hash", "token"):
        assert k not in env["payload"]
    assert env["payload"]["recipientUserIds"] == ["r1", "r2"]


def test_unknown_event_type_rejected():
    with pytest.raises(ValueError):
        events.build_envelope("management.nope", {}, ["r"])


def test_record_event_without_recipients_is_noop(monkeypatch):
    called = []
    monkeypatch.setattr(events, "get_connection", lambda: called.append(1))
    assert events.record_event("management.user.created", {}, []) is None
    assert called == []


def test_record_event_failure_never_raises(monkeypatch):
    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(events, "get_connection", boom)
    assert events.record_event("management.user.created", {"userId": "u"}, ["r"]) is None


# --------------------------------------------------------------------------- farm events

def _farm(status="PENDING"):
    return {"farm_id": FARM_A, "farm_code": "FARM-1", "farm_name": "Farm A", "approval_status": status,
            "approved_at": None, "address": None, "status": "ACTIVE", "rejection_reason": None,
            "zone_count": 0, "device_count": 0}


def test_owner_farm_request_emits_after_create_admin_create_does_not(monkeypatch):
    recorded = []
    monkeypatch.setattr(events, "record_event", lambda t, p, r, c=None: recorded.append((t, p, list(r))) or "eid")
    monkeypatch.setattr(events, "admin_user_ids", lambda exclude=None: [ADMIN])
    monkeypatch.setattr(events, "user_display_name", lambda uid: "Owner A")
    monkeypatch.setattr(farm_routes.farm_controller, "create_farm", lambda **kw: _farm(kw["approval_status"]))

    farm_routes.create_farm(FarmCreateRequest(farm_name="Farm A"), current_user={"id": OWNER_A, "roles": ["FARM_OWNER"]})
    assert recorded[-1][0] == "management.farm.approval_requested"
    assert recorded[-1][2] == [ADMIN]
    assert recorded[-1][1]["farmId"] == FARM_A and recorded[-1][1]["requestedByName"] == "Owner A"

    recorded.clear()
    farm_routes.create_farm(FarmCreateRequest(farm_name="X", owner_id=OWNER_A), current_user={"id": ADMIN, "roles": ["ADMIN"]})
    assert recorded == []  # admin-created farms are APPROVED; no approval request


def test_failed_farm_create_emits_nothing(monkeypatch):
    recorded = []
    monkeypatch.setattr(events, "record_event", lambda *a, **k: recorded.append(a))

    def fail(**kw):
        raise HTTPException(status_code=409, detail="exists")

    monkeypatch.setattr(farm_routes.farm_controller, "create_farm", fail)
    with pytest.raises(HTTPException):
        farm_routes.create_farm(FarmCreateRequest(farm_name="Dup"), current_user={"id": OWNER_A, "roles": ["FARM_OWNER"]})
    assert recorded == []


def test_reject_notifies_only_owner_with_reason(monkeypatch):
    recorded = []
    monkeypatch.setattr(events, "record_event", lambda t, p, r, c=None: recorded.append((t, p, list(r))))
    monkeypatch.setattr(events, "farm_context", lambda fid: {"farm_id": FARM_A, "farm_code": "F", "farm_name": "Farm A",
                                                            "owner_id": OWNER_A, "owner_name": "A", "technician_ids": [TECH_1]})
    monkeypatch.setattr(farm_routes.farm_controller, "reject_farm", lambda **kw: _farm("REJECTED"))
    farm_routes.reject_farm(FARM_A, FarmRejectRequest(rejection_reason="Thiếu giấy tờ"), current_user={"id": ADMIN, "roles": ["ADMIN"]})
    t, p, r = recorded[-1]
    assert t == "management.farm.rejected" and r == [OWNER_A] and p["rejectionReason"] == "Thiếu giấy tờ"


# --------------------------------------------------------------------------- assignment idempotency

def test_reassign_same_technician_does_not_renotify(monkeypatch):
    recorded = []
    monkeypatch.setattr(business_events, "technician_assignment", lambda *a: recorded.append(a))
    monkeypatch.setattr(technician_routes.farm_repository, "get_farm_by_id", lambda fid: _farm("APPROVED"))
    monkeypatch.setattr(technician_routes.technician_controller, "assign_technician", lambda *a: {"status": "ASSIGNED"})
    state = {"active": False}
    monkeypatch.setattr(technician_routes.user_repository, "is_farm_assigned_to_technician", lambda t, f: state["active"])
    admin = {"id": ADMIN, "roles": ["ADMIN"]}
    technician_routes.assign_technician(uuid.UUID(TECH_1), uuid.UUID(FARM_A), True, current_user=admin)
    state["active"] = True
    technician_routes.assign_technician(uuid.UUID(TECH_1), uuid.UUID(FARM_A), True, current_user=admin)
    assert len(recorded) == 1 and recorded[0][2] is True


def test_unassign_notifies_and_requeues(monkeypatch):
    recorded, requeued = [], []
    monkeypatch.setattr(business_events, "technician_assignment", lambda *a: recorded.append(a))
    monkeypatch.setattr(technician_routes.technician_controller, "unassign_technician", lambda *a: {"status": "UNASSIGNED"})
    monkeypatch.setattr(technician_routes.inspection_repository, "requeue_for_unassigned_technician", lambda *a: requeued.append(a) or [])
    technician_routes.unassign_technician(uuid.UUID(TECH_1), uuid.UUID(FARM_A), current_user={"id": ADMIN, "roles": ["ADMIN"]})
    assert recorded[0][2] is False and requeued and requeued[0][1] == TECH_1


# --------------------------------------------------------------------------- inspection RBAC / state machine

def _req(status="NEW", tech=TECH_1, owner=OWNER_A):
    return {"id": REQ_ID, "request_code": "IR-1", "farm_id": FARM_A, "farm_name": "Farm A", "status": status,
            "assigned_technician_id": tech, "requested_by": owner, "title": "Kiểm tra độ ẩm", "priority": "MEDIUM",
            "result_note": None}


@pytest.fixture
def scope(monkeypatch):
    owned = {(OWNER_A, FARM_A)}
    assigned = {(TECH_1, FARM_A), (TECH_2, FARM_A)}
    monkeypatch.setattr(ir_routes.user_repository, "is_farm_owned_by_user", lambda u, f: (u, f) in owned)
    monkeypatch.setattr(ir_routes.user_repository, "is_farm_assigned_to_technician", lambda t, f: (t, f) in assigned)
    monkeypatch.setattr(ir_routes.user_repository, "resolve_farm_uuid", lambda f: FARM_A if f == FARM_A else None)
    emitted = []
    monkeypatch.setattr(inspection_events, "created", lambda r: emitted.append(("created", r)))
    monkeypatch.setattr(inspection_events, "status_changed", lambda r, a, p: emitted.append(("status", r, a, p)))
    monkeypatch.setattr(inspection_events, "assigned", lambda r, a: emitted.append(("assigned", r)))
    return {"assigned": assigned, "emitted": emitted}


def test_owner_b_cannot_create_for_farm_a(scope):
    with pytest.raises(HTTPException) as exc:
        ir_routes.create_inspection_request(InspectionRequestCreate(farm_id=FARM_A, title="Hack"), current_user={"id": OWNER_B, "roles": ["FARM_OWNER"]})
    assert exc.value.status_code == 404
    assert scope["emitted"] == []


def test_owner_create_links_default_technician_or_admin_queue(scope, monkeypatch):
    from app.repositories.farm_repository import farm_repository as fr_inst

    monkeypatch.setattr(fr_inst, "get_farm_by_id", lambda fid: _farm("APPROVED"))
    created = {}
    monkeypatch.setattr(ir_routes.inspection_repository, "pick_default_technician", lambda fid: None)
    monkeypatch.setattr(ir_routes.inspection_repository, "create", lambda **kw: created.update(kw) or _req(tech=kw["assigned_technician_id"]))
    res = ir_routes.create_inspection_request(InspectionRequestCreate(farm_id=FARM_A, title="Kiểm tra"), current_user={"id": OWNER_A, "roles": ["FARM_OWNER"]})
    assert created["assigned_technician_id"] is None and created["requested_by"] == OWNER_A
    assert res["assigned_technician_id"] is None
    assert scope["emitted"][-1][0] == "created"


def test_create_rejects_zone_of_other_farm(scope, monkeypatch):
    from app.repositories.farm_repository import farm_repository as fr_inst

    monkeypatch.setattr(fr_inst, "get_farm_by_id", lambda fid: _farm("APPROVED"))
    monkeypatch.setattr(ir_routes.zone_repository, "get_zone_by_id", lambda zid: {"farm_id": str(uuid.uuid4())})
    with pytest.raises(HTTPException) as exc:
        ir_routes.create_inspection_request(InspectionRequestCreate(farm_id=FARM_A, title="Kiểm tra", zone_id=str(uuid.uuid4())), current_user={"id": OWNER_A, "roles": ["FARM_OWNER"]})
    assert exc.value.status_code == 400


def test_create_requires_approved_farm(scope, monkeypatch):
    from app.repositories.farm_repository import farm_repository as fr_inst

    monkeypatch.setattr(fr_inst, "get_farm_by_id", lambda fid: _farm("PENDING"))
    with pytest.raises(HTTPException) as exc:
        ir_routes.create_inspection_request(InspectionRequestCreate(farm_id=FARM_A, title="Kiểm tra"), current_user={"id": OWNER_A, "roles": ["FARM_OWNER"]})
    assert exc.value.status_code == 409


def test_unassigned_technician_cannot_see_or_act(scope, monkeypatch):
    outsider = str(uuid.uuid4())
    monkeypatch.setattr(ir_routes.inspection_repository, "get", lambda rid, with_history=False: _req())
    with pytest.raises(HTTPException) as exc:
        ir_routes.get_inspection_request(REQ_ID, current_user={"id": outsider, "roles": ["TECHNICIAN"]})
    assert exc.value.status_code == 404
    with pytest.raises(HTTPException) as exc:
        ir_routes.accept_inspection_request(REQ_ID, current_user={"id": outsider, "roles": ["TECHNICIAN"]})
    assert exc.value.status_code == 404


def test_other_assigned_technician_cannot_accept_someone_elses_request(scope, monkeypatch):
    monkeypatch.setattr(ir_routes.inspection_repository, "get", lambda rid, with_history=False: _req(tech=TECH_1))
    with pytest.raises(HTTPException) as exc:
        ir_routes.accept_inspection_request(REQ_ID, current_user={"id": TECH_2, "roles": ["TECHNICIAN"]})
    assert exc.value.status_code == 403


def test_accept_uses_caller_id_and_conflict_on_lost_race(scope, monkeypatch):
    monkeypatch.setattr(ir_routes.inspection_repository, "get", lambda rid, with_history=False: _req())
    calls = []
    monkeypatch.setattr(ir_routes.inspection_repository, "accept", lambda rid, tid: calls.append(tid) or None)
    with pytest.raises(HTTPException) as exc:
        ir_routes.accept_inspection_request(REQ_ID, current_user={"id": TECH_1, "roles": ["TECHNICIAN"]})
    assert exc.value.status_code == 409 and calls == [TECH_1]
    assert scope["emitted"] == []


def test_complete_success_emits_status_change(scope, monkeypatch):
    monkeypatch.setattr(ir_routes.inspection_repository, "get", lambda rid, with_history=False: _req("IN_PROGRESS"))
    monkeypatch.setattr(ir_routes.inspection_repository, "complete", lambda rid, tid, note: _req("COMPLETED"))
    res = ir_routes.complete_inspection_request(REQ_ID, InspectionCompleteRequest(result_note="Đã thay cảm biến"), current_user={"id": TECH_1, "roles": ["TECHNICIAN"]})
    assert res["status"] == "COMPLETED"
    assert scope["emitted"][-1][0] == "status" and scope["emitted"][-1][3] == "IN_PROGRESS"


def test_admin_assign_requires_tech_actively_assigned_to_farm(scope, monkeypatch):
    monkeypatch.setattr(ir_routes.inspection_repository, "get", lambda rid, with_history=False: _req(tech=None))
    with pytest.raises(HTTPException) as exc:
        ir_routes.assign_inspection_request(REQ_ID, InspectionAssignRequest(technician_id=str(uuid.uuid4())), current_user={"id": ADMIN, "roles": ["ADMIN"]})
    assert exc.value.status_code == 400
    monkeypatch.setattr(ir_routes.inspection_repository, "assign", lambda rid, tid, aid: _req(tech=tid))
    res = ir_routes.assign_inspection_request(REQ_ID, InspectionAssignRequest(technician_id=TECH_2), current_user={"id": ADMIN, "roles": ["ADMIN"]})
    assert res["assigned_technician_id"] == TECH_2 and scope["emitted"][-1][0] == "assigned"


def test_unknown_or_malformed_request_id_fails_closed(scope, monkeypatch):
    monkeypatch.setattr(ir_routes.inspection_repository, "get", lambda rid, with_history=False: None)
    with pytest.raises(HTTPException) as exc:
        ir_routes.get_inspection_request("not-a-uuid", current_user={"id": ADMIN, "roles": ["ADMIN"]})
    assert exc.value.status_code == 404


def test_status_change_recipients_exclude_actor(monkeypatch):
    recorded = []
    monkeypatch.setattr(events, "record_event", lambda t, p, r, c=None: recorded.append((t, p, sorted(r))))
    inspection_events.status_changed(_req("ACCEPTED"), TECH_1, "NEW")
    assert recorded[-1][2] == [OWNER_A]


def test_complete_accepts_short_valid_result_note_and_trims(scope, monkeypatch):
    captured = []
    monkeypatch.setattr(ir_routes.inspection_repository, "get", lambda rid, with_history=False: _req("IN_PROGRESS"))

    def fake_complete(rid, tid, note):
        captured.append(note)
        done = _req("COMPLETED")
        done["result_note"] = note
        return done

    monkeypatch.setattr(ir_routes.inspection_repository, "complete", fake_complete)
    payload = InspectionCompleteRequest(result_note="  ổn  ")
    assert payload.result_note == "ổn"
    res = ir_routes.complete_inspection_request(REQ_ID, payload, current_user={"id": TECH_1, "roles": ["TECHNICIAN"]})
    assert res["status"] == "COMPLETED"
    assert res["result_note"] == "ổn"
    assert captured == ["ổn"]


def test_complete_rejects_empty_or_whitespace_only_result_note():
    from pydantic import ValidationError

    for bad in ("", "   ", "\n\t  "):
        with pytest.raises(ValidationError):
            InspectionCompleteRequest(result_note=bad)
