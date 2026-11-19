import uuid
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user
from app.core.service_auth import verify_internal_service
from app.main import app


def _override_user(user_id: str, roles: list[str]):
    return lambda: {"id": user_id, "email": f"{user_id}@test.local", "roles": roles}


def test_farm_crud_and_rbac(monkeypatch):
    admin_id = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())
    tech_id = str(uuid.uuid4())
    farm_uuid = str(uuid.uuid4())

    sample_farm = {
        "farm_id": farm_uuid,
        "farm_code": "FARM-TEST-01",
        "farm_name": "Test Farm 01",
        "address": "Can Gio",
        "status": "ACTIVE",
        "zone_count": 0,
        "device_count": 0,
        "owner_name": "Owner",
        "owner_phone": None,
        "technician_id": None,
        "technician_name": None,
        "created_at": "2026-11-18T00:00:00Z",
    }

    from app.routes import farm_routes as fr_mod
    from app.core import dependencies as dep_mod

    monkeypatch.setattr(fr_mod.farm_controller, "create_farm", MagicMock(return_value=sample_farm))
    monkeypatch.setattr(fr_mod.farm_controller, "update_farm", MagicMock(return_value=sample_farm))
    monkeypatch.setattr(fr_mod.farm_controller, "delete_farm", MagicMock(return_value={"status": "deleted", "farm_id": farm_uuid}))
    monkeypatch.setattr(dep_mod.user_repository, "is_farm_owned_by_user", lambda uid, fid: uid == owner_id)

    client = TestClient(app)
    try:
        # TECHNICIAN forbidden on POST /api/farms
        app.dependency_overrides[get_current_user] = _override_user(tech_id, ["TECHNICIAN"])
        r = client.post("/api/farms", json={"farm_code": "F1", "farm_name": "N1"})
        assert r.status_code == 403

        # FARM_OWNER creates farm -> owner_id forced to self
        app.dependency_overrides[get_current_user] = _override_user(owner_id, ["FARM_OWNER"])
        r = client.post("/api/farms", json={"farm_code": "FARM-TEST-01", "farm_name": "Test Farm 01", "owner_id": admin_id})
        assert r.status_code == 201
        assert fr_mod.farm_controller.create_farm.call_args.kwargs["owner_id"] == owner_id

        # FARM_OWNER cannot reassign owner_id on PUT
        r = client.put(f"/api/farms/{farm_uuid}", json={"owner_id": admin_id})
        assert r.status_code == 403

        # FARM_OWNER updates own farm
        r = client.put(f"/api/farms/{farm_uuid}", json={"farm_name": "Renamed"})
        assert r.status_code == 200

        # FARM_OWNER cannot DELETE farm (ADMIN only)
        r = client.delete(f"/api/farms/{farm_uuid}")
        assert r.status_code == 403

        # ADMIN deletes farm
        app.dependency_overrides[get_current_user] = _override_user(admin_id, ["ADMIN"])
        r = client.delete(f"/api/farms/{farm_uuid}")
        assert r.status_code == 200
        assert r.json()["status"] == "deleted"
    finally:
        app.dependency_overrides.clear()


def test_zone_and_device_crud_and_rbac(monkeypatch):
    owner_id = str(uuid.uuid4())
    tech_id = str(uuid.uuid4())
    farm_uuid = str(uuid.uuid4())
    zone_uuid = str(uuid.uuid4())
    dev_uuid = str(uuid.uuid4())

    sample_zone = {
        "zone_id": zone_uuid,
        "farm_id": farm_uuid,
        "zone_code": "Z-A",
        "name": "Zone A",
        "device_count": 0,
        "created_at": "2026-11-18T00:00:00Z",
    }
    sample_device = {
        "device_id": dev_uuid,
        "node_id": "NODE-01",
        "name": "Sensor 1",
        "device_type": "CONTROLLER",
        "farm_id": farm_uuid,
        "zone_id": zone_uuid,
        "zone_name": "Zone A",
        "ip_address": None,
        "firmware_version": "1.0.0",
        "is_active": True,
        "status": "OFFLINE",
        "presence_status": "OFFLINE",
        "created_at": "2026-11-18T00:00:00Z",
    }

    from app.routes import zone_routes as zr_mod
    from app.routes import device_routes as dr_mod
    from app.core import dependencies as dep_mod

    monkeypatch.setattr(dep_mod.user_repository, "is_farm_owned_by_user", lambda uid, fid: uid == owner_id)
    monkeypatch.setattr(dep_mod.user_repository, "is_farm_assigned_to_technician", lambda uid, fid: False)
    monkeypatch.setattr(zr_mod.user_repository, "resolve_farm_uuid", lambda fid: farm_uuid)
    monkeypatch.setattr(dr_mod.user_repository, "resolve_farm_uuid", lambda fid: farm_uuid)
    monkeypatch.setattr(dr_mod.user_repository, "get_farm_id_for_device", lambda did: farm_uuid)
    monkeypatch.setattr(
        dr_mod.farm_repository,
        "get_farm_by_id",
        lambda fid: {"farm_id": fid, "approval_status": "APPROVED"},
    )
    other_farm_uuid = str(uuid.uuid4())
    monkeypatch.setattr(
        dr_mod.zone_repository,
        "get_zone_by_id",
        lambda zid: {"zone_id": zid, "farm_id": other_farm_uuid if zid == "other-zone" else farm_uuid},
    )
    monkeypatch.setattr(zr_mod.zone_controller, "get_zone", MagicMock(return_value=sample_zone))
    monkeypatch.setattr(zr_mod.zone_controller, "create_zone", MagicMock(return_value=sample_zone))
    monkeypatch.setattr(zr_mod.zone_controller, "update_zone", MagicMock(return_value=sample_zone))
    monkeypatch.setattr(zr_mod.zone_controller, "delete_zone", MagicMock(return_value={"status": "deleted", "zone_id": zone_uuid}))
    monkeypatch.setattr(dr_mod.device_controller, "create_device", MagicMock(return_value=sample_device))
    monkeypatch.setattr(dr_mod.device_controller, "update_device", MagicMock(return_value=sample_device))
    monkeypatch.setattr(dr_mod.device_controller, "delete_device", MagicMock(return_value={"status": "deleted", "device_id": dev_uuid}))

    client = TestClient(app)
    try:
        # TECHNICIAN forbidden on Zone & Device writes
        app.dependency_overrides[get_current_user] = _override_user(tech_id, ["TECHNICIAN"])
        assert client.post(f"/api/farms/{farm_uuid}/zones", json={"zone_code": "Z-A", "name": "Zone A"}).status_code == 403
        assert client.post("/api/devices", json={"node_id": "NODE-01", "farm_id": farm_uuid}).status_code == 403

        # FARM_OWNER creates, updates, deletes Zone & Device
        app.dependency_overrides[get_current_user] = _override_user(owner_id, ["FARM_OWNER"])
        assert client.post(f"/api/farms/{farm_uuid}/zones", json={"zone_code": "Z-A", "name": "Zone A"}).status_code == 201
        assert client.put(f"/api/zones/{zone_uuid}", json={"name": "Zone A2"}).status_code == 200
        assert client.delete(f"/api/zones/{zone_uuid}").status_code == 200

        assert client.post("/api/devices", json={"node_id": "NODE-01", "farm_id": farm_uuid}).status_code == 201
        assert client.post("/api/devices", json={"node_id": "NODE-01", "farm_id": farm_uuid, "zone_id": "other-zone"}).status_code == 400
        assert client.put(f"/api/devices/{dev_uuid}", json={"name": "Sensor 1b"}).status_code == 200
        assert client.put(f"/api/devices/{dev_uuid}", json={"zone_id": "other-zone"}).status_code == 400
        assert client.delete(f"/api/devices/{dev_uuid}").status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_technician_unassign_and_internal_recipients(monkeypatch):
    admin_id = str(uuid.uuid4())
    tech_id = str(uuid.uuid4())
    farm_uuid = str(uuid.uuid4())

    from app.routes import technician_routes as tr_mod
    from app.routes import internal_routes as ir_mod

    monkeypatch.setattr(
        tr_mod.technician_controller,
        "unassign_technician",
        MagicMock(return_value={"technician_id": tech_id, "farm_id": farm_uuid, "status": "UNASSIGNED"}),
    )
    monkeypatch.setattr(
        ir_mod.farm_service,
        "get_farm_recipients",
        MagicMock(return_value={"farm_id": farm_uuid, "farm_code": "FARM-01", "owner_id": admin_id, "technician_ids": [tech_id]}),
    )

    client = TestClient(app)
    try:
        # Unassign requires ADMIN
        app.dependency_overrides[get_current_user] = _override_user(tech_id, ["TECHNICIAN"])
        assert client.delete(f"/api/technicians/{tech_id}/farms/{farm_uuid}/assign").status_code == 403

        app.dependency_overrides[get_current_user] = _override_user(admin_id, ["ADMIN"])
        r = client.delete(f"/api/technicians/{tech_id}/farms/{farm_uuid}/assign")
        assert r.status_code == 200
        assert r.json()["status"] == "UNASSIGNED"

        # Internal farm recipients fails closed without service auth
        assert client.get(f"/internal/v1/farms/{farm_uuid}/recipients").status_code in (401, 403)

        app.dependency_overrides[verify_internal_service] = lambda: {"service": "notification-service"}
        r = client.get(f"/internal/v1/farms/{farm_uuid}/recipients")
        assert r.status_code == 200
        body = r.json()
        assert body["owner_id"] == admin_id
        assert body["technician_ids"] == [tech_id]
    finally:
        app.dependency_overrides.clear()
