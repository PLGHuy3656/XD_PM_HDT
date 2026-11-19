import uuid
from fastapi import HTTPException
import pytest

import app.routes.farm_routes as farm_routes
import app.routes.zone_routes as zone_routes
import app.routes.device_routes as device_routes
import app.routes.technician_routes as technician_routes
from app.schemas.farm import FarmCreateRequest, FarmRejectRequest
from app.schemas.zone import ZoneCreateRequest
from app.schemas.device import DeviceCreateRequest


def test_create_farm_approval_status_by_role(monkeypatch):
    captured = []

    def fake_create_farm(**kwargs):
        captured.append(kwargs)
        return {
            "farm_id": str(uuid.uuid4()),
            "farm_code": "FARM-ABC123",
            "farm_name": kwargs["farm_name"],
            "address": kwargs.get("address"),
            "status": kwargs.get("status_val", "ACTIVE"),
            "approval_status": kwargs["approval_status"],
            "rejection_reason": None,
            "zone_count": 0,
            "device_count": 0,
            "approved_by": kwargs.get("approved_by"),
            "approved_at": None,
            "created_at": None,
        }

    monkeypatch.setattr(farm_routes.farm_controller, "create_farm", fake_create_farm)

    owner_user = {"id": "owner-1", "roles": ["FARM_OWNER"]}
    res_owner = farm_routes.create_farm(FarmCreateRequest(farm_name="Owner Farm"), current_user=owner_user)
    assert res_owner["approval_status"] == "PENDING"
    assert captured[-1]["approved_by"] is None

    admin_user = {"id": "admin-1", "roles": ["ADMIN"]}
    res_admin = farm_routes.create_farm(FarmCreateRequest(farm_name="Admin Farm"), current_user=admin_user)
    assert res_admin["approval_status"] == "APPROVED"
    assert captured[-1]["approved_by"] == "admin-1"


def test_approve_and_reject_farm_routes(monkeypatch):
    calls = []

    def fake_approve(farm_id: str, admin_user_id: str):
        calls.append(("approve", farm_id, admin_user_id))
        return {
            "farm_id": farm_id,
            "farm_code": "FARM-1",
            "farm_name": "Farm 1",
            "status": "ACTIVE",
            "approval_status": "APPROVED",
            "rejection_reason": None,
            "zone_count": 0,
            "device_count": 0,
            "approved_by": admin_user_id,
        }

    def fake_reject(farm_id: str, admin_user_id: str, rejection_reason: str):
        calls.append(("reject", farm_id, admin_user_id, rejection_reason))
        return {
            "farm_id": farm_id,
            "farm_code": "FARM-1",
            "farm_name": "Farm 1",
            "status": "ACTIVE",
            "approval_status": "REJECTED",
            "rejection_reason": rejection_reason,
            "zone_count": 0,
            "device_count": 0,
            "approved_by": admin_user_id,
        }

    monkeypatch.setattr(farm_routes.farm_controller, "approve_farm", fake_approve)
    monkeypatch.setattr(farm_routes.farm_controller, "reject_farm", fake_reject)

    admin = {"id": "admin-99", "roles": ["ADMIN"]}
    approved = farm_routes.approve_farm("farm-1", current_user=admin)
    assert approved["approval_status"] == "APPROVED"
    rejected = farm_routes.reject_farm("farm-1", FarmRejectRequest(rejection_reason="Missing address"), current_user=admin)
    assert rejected["approval_status"] == "REJECTED"
    assert rejected["rejection_reason"] == "Missing address"


def test_unapproved_farm_blocks_zone_device_and_technician_assignment(monkeypatch):
    farm_uuid = str(uuid.uuid4())
    tech_uuid = uuid.uuid4()
    admin_user = {"id": "admin-1", "roles": ["ADMIN"]}

    monkeypatch.setattr(zone_routes, "verify_farm_resource_access", lambda u, f: None)
    monkeypatch.setattr(zone_routes.user_repository, "resolve_farm_uuid", lambda f: farm_uuid)
    monkeypatch.setattr(
        zone_routes.farm_repository,
        "get_farm_by_id",
        lambda f: {"farm_id": farm_uuid, "approval_status": "PENDING"},
    )
    with pytest.raises(HTTPException) as zone_exc:
        zone_routes.create_zone(farm_uuid, ZoneCreateRequest(name="Zone A"), current_user=admin_user)
    assert zone_exc.value.status_code == 403

    monkeypatch.setattr(device_routes, "verify_farm_resource_access", lambda u, f: None)
    monkeypatch.setattr(device_routes.user_repository, "resolve_farm_uuid", lambda f: farm_uuid)
    monkeypatch.setattr(
        device_routes.farm_repository,
        "get_farm_by_id",
        lambda f: {"farm_id": farm_uuid, "approval_status": "REJECTED"},
    )
    with pytest.raises(HTTPException) as dev_exc:
        device_routes.create_device(
            DeviceCreateRequest(node_id="NODE-01", farm_id=farm_uuid),
            current_user=admin_user,
        )
    assert dev_exc.value.status_code == 403

    monkeypatch.setattr(
        technician_routes.farm_repository,
        "get_farm_by_id",
        lambda f: {"farm_id": farm_uuid, "approval_status": "PENDING"},
    )
    with pytest.raises(HTTPException) as tech_exc:
        technician_routes.assign_technician(tech_uuid, uuid.UUID(farm_uuid), current_user=admin_user)
    assert tech_exc.value.status_code == 409


def test_technician_device_zone_mapping_permissions_and_cross_farm_guard(monkeypatch):
    from app.schemas.device import DeviceZoneUpdateRequest

    farm_a = str(uuid.uuid4())
    farm_b = str(uuid.uuid4())
    dev_id = str(uuid.uuid4())
    zone_a = str(uuid.uuid4())
    zone_b = str(uuid.uuid4())
    tech_user = {"id": "tech-1", "roles": ["TECHNICIAN"]}

    monkeypatch.setattr(device_routes.user_repository, "get_farm_id_for_device", lambda d: farm_a)

    # 1. Unassigned technician -> 403
    def deny_access(u, f):
        raise HTTPException(status_code=403, detail="Forbidden")

    monkeypatch.setattr(device_routes, "verify_farm_resource_access", deny_access)
    with pytest.raises(HTTPException) as unauth_exc:
        device_routes.update_device_zone(dev_id, DeviceZoneUpdateRequest(zone_id=zone_a), current_user=tech_user)
    assert unauth_exc.value.status_code == 403

    # 2. Assigned technician on PENDING farm -> 403
    monkeypatch.setattr(device_routes, "verify_farm_resource_access", lambda u, f: None)
    monkeypatch.setattr(
        device_routes.farm_repository,
        "get_farm_by_id",
        lambda f: {"farm_id": farm_a, "approval_status": "PENDING"},
    )
    with pytest.raises(HTTPException) as pending_exc:
        device_routes.update_device_zone(dev_id, DeviceZoneUpdateRequest(zone_id=zone_a), current_user=tech_user)
    assert pending_exc.value.status_code == 403

    # 3. Assigned technician on APPROVED farm trying to move device to zone in Farm B -> 400
    monkeypatch.setattr(
        device_routes.farm_repository,
        "get_farm_by_id",
        lambda f: {"farm_id": farm_a, "approval_status": "APPROVED"},
    )
    monkeypatch.setattr(
        device_routes.zone_repository,
        "get_zone_by_id",
        lambda z: {"zone_id": zone_b, "farm_id": farm_b},
    )
    with pytest.raises(HTTPException) as cross_exc:
        device_routes.update_device_zone(dev_id, DeviceZoneUpdateRequest(zone_id=zone_b), current_user=tech_user)
    assert cross_exc.value.status_code == 400

    # 4. Assigned technician on APPROVED farm moving device to valid zone in Farm A -> 200
    monkeypatch.setattr(
        device_routes.zone_repository,
        "get_zone_by_id",
        lambda z: {"zone_id": zone_a, "farm_id": farm_a},
    )
    monkeypatch.setattr(
        device_routes.device_repository,
        "update_device_zone",
        lambda d, z: {
            "device_id": d,
            "node_id": "NODE-01",
            "name": "Sensor 1",
            "device_type": "ENVIRONMENT_MONITOR",
            "farm_id": farm_a,
            "zone_id": z,
            "zone_name": "Zone A",
            "is_active": True,
        },
    )
    res = device_routes.update_device_zone(dev_id, DeviceZoneUpdateRequest(zone_id=zone_a), current_user=tech_user)
    assert res["zone_id"] == zone_a


def test_technician_device_registration_permissions(monkeypatch):
    farm_a = str(uuid.uuid4())
    farm_b = str(uuid.uuid4())
    zone_b = str(uuid.uuid4())
    tech_user = {"id": "tech-1", "roles": ["TECHNICIAN"]}

    # 1. Unassigned farm -> 403
    def deny(u, f):
        raise HTTPException(status_code=403, detail="Forbidden")

    monkeypatch.setattr(device_routes, "verify_farm_resource_access", deny)
    with pytest.raises(HTTPException) as exc1:
        device_routes.create_device(
            DeviceCreateRequest(node_id="TECH-N1", farm_id=farm_a),
            current_user=tech_user,
        )
    assert exc1.value.status_code == 403

    # 2. Assigned PENDING farm -> 403
    monkeypatch.setattr(device_routes, "verify_farm_resource_access", lambda u, f: None)
    monkeypatch.setattr(device_routes.user_repository, "resolve_farm_uuid", lambda f: farm_a)
    monkeypatch.setattr(
        device_routes.farm_repository,
        "get_farm_by_id",
        lambda f: {"farm_id": farm_a, "approval_status": "PENDING"},
    )
    with pytest.raises(HTTPException) as exc2:
        device_routes.create_device(
            DeviceCreateRequest(node_id="TECH-N1", farm_id=farm_a),
            current_user=tech_user,
        )
    assert exc2.value.status_code == 403

    # 3. Assigned APPROVED farm + cross-farm zone -> 400
    monkeypatch.setattr(
        device_routes.farm_repository,
        "get_farm_by_id",
        lambda f: {"farm_id": farm_a, "approval_status": "APPROVED"},
    )
    monkeypatch.setattr(
        device_routes.zone_repository,
        "get_zone_by_id",
        lambda z: {"zone_id": zone_b, "farm_id": farm_b},
    )
    with pytest.raises(HTTPException) as exc3:
        device_routes.create_device(
            DeviceCreateRequest(node_id="TECH-N1", farm_id=farm_a, zone_id=zone_b),
            current_user=tech_user,
        )
    assert exc3.value.status_code == 400

    # 4. Assigned APPROVED farm + unassigned zone -> 201
    monkeypatch.setattr(
        device_routes.device_controller,
        "create_device",
        lambda **kw: {
            "device_id": str(uuid.uuid4()),
            "node_id": kw["node_id"],
            "name": kw.get("name"),
            "device_type": kw.get("device_type"),
            "farm_id": kw["farm_uuid"],
            "zone_id": kw.get("zone_id"),
            "is_active": True,
        },
    )
    res = device_routes.create_device(
        DeviceCreateRequest(node_id="TECH-N1", farm_id=farm_a, name="Sensor X"),
        current_user=tech_user,
    )
    assert res["node_id"] == "TECH-N1"
    assert res["zone_id"] is None
