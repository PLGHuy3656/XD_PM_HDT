import uuid
from unittest.mock import AsyncMock
from fastapi import Response
from fastapi.testclient import TestClient

import app.auth as auth_mod
import app.routes as r_mod
from app.main import app
from tests.conftest import make_jwt_token


def _hdr(roles: list[str]):
    tok = make_jwt_token(roles=roles, email="u@test.local")
    return {"Authorization": f"Bearer {tok}"}


def test_gateway_management_crud_proxy_and_rbac(monkeypatch):
    farm_id = str(uuid.uuid4())
    zone_id = str(uuid.uuid4())
    dev_id = str(uuid.uuid4())
    tech_id = str(uuid.uuid4())

    monkeypatch.setattr(auth_mod, "is_token_revoked", lambda token: False)
    monkeypatch.setattr(
        auth_mod,
        "check_user_active_via_management",
        AsyncMock(side_effect=lambda user_id, token, *a, **kw: {"id": user_id, "roles": __import__("jwt").decode(token, options={"verify_signature": False}).get("roles", []), "status": "ACTIVE"}),
    )
    monkeypatch.setattr(r_mod, "resolve_farm_access", AsyncMock(return_value=farm_id))
    monkeypatch.setattr(r_mod, "resolve_device_access", AsyncMock(return_value=None))
    fwd_mock = AsyncMock(return_value=Response(content=b'{"ok":true}', status_code=200, media_type="application/json"))
    monkeypatch.setattr(r_mod.proxy_handler, "forward", fwd_mock)

    client = TestClient(app)

    # Unauthenticated -> 401
    assert client.post("/api/farms", json={"farm_code": "F1", "farm_name": "N1"}).status_code == 401

    # TECHNICIAN -> 403 on all CRUD writes & unassign
    tech_hdr = _hdr(["TECHNICIAN"])
    assert client.post("/api/farms", headers=tech_hdr, json={"farm_code": "F1", "farm_name": "N1"}).status_code == 403
    assert client.put(f"/api/farms/{farm_id}", headers=tech_hdr, json={"farm_name": "N2"}).status_code == 403
    assert client.delete(f"/api/farms/{farm_id}", headers=tech_hdr).status_code == 403
    assert client.post(f"/api/farms/{farm_id}/zones", headers=tech_hdr, json={"zone_code": "Z1", "name": "Z"}).status_code == 403
    assert client.put(f"/api/zones/{zone_id}", headers=tech_hdr, json={"name": "Z2"}).status_code == 403
    assert client.delete(f"/api/zones/{zone_id}", headers=tech_hdr).status_code == 403
    assert client.post("/api/devices", headers=tech_hdr, json={"node_id": "N1", "farm_id": farm_id}).status_code == 200
    assert client.put(f"/api/devices/{dev_id}", headers=tech_hdr, json={"name": "D2"}).status_code == 403
    assert client.patch(f"/api/devices/{dev_id}/zone", headers=tech_hdr, json={"zone_id": zone_id}).status_code == 200
    assert client.delete(f"/api/devices/{dev_id}", headers=tech_hdr).status_code == 403
    assert client.delete(f"/api/technicians/{tech_id}/farms/{farm_id}/assign", headers=tech_hdr).status_code == 403

    # FARM_OWNER -> 200 on Farm/Zone/Device CRUD, 403 on DELETE farm & unassign, 400 on non-UUID zone
    owner_hdr = _hdr(["FARM_OWNER"])
    assert client.post("/api/farms", headers=owner_hdr, json={"farm_code": "F1", "farm_name": "N1"}).status_code == 200
    assert client.put(f"/api/farms/{farm_id}", headers=owner_hdr, json={"farm_name": "N2"}).status_code == 200
    assert client.delete(f"/api/farms/{farm_id}", headers=owner_hdr).status_code == 403
    assert client.post(f"/api/farms/{farm_id}/zones", headers=owner_hdr, json={"zone_code": "Z1", "name": "Z"}).status_code == 200
    assert client.put("/api/zones/not-a-uuid", headers=owner_hdr, json={"name": "Z2"}).status_code == 400
    assert client.put(f"/api/zones/{zone_id}", headers=owner_hdr, json={"name": "Z2"}).status_code == 200
    assert client.delete(f"/api/zones/{zone_id}", headers=owner_hdr).status_code == 200
    assert client.post("/api/devices", headers=owner_hdr, json={"node_id": "N1", "farm_id": farm_id}).status_code == 200
    assert client.put(f"/api/devices/{dev_id}", headers=owner_hdr, json={"name": "D2"}).status_code == 200
    assert client.delete(f"/api/devices/{dev_id}", headers=owner_hdr).status_code == 200
    assert client.delete(f"/api/technicians/{tech_id}/farms/{farm_id}/assign", headers=owner_hdr).status_code == 403
    assert client.post(f"/api/farms/{farm_id}/approve", headers=tech_hdr).status_code == 403
    assert client.post(f"/api/farms/{farm_id}/reject", headers=tech_hdr, json={"rejection_reason": "No"}).status_code == 403
    assert client.post(f"/api/farms/{farm_id}/approve", headers=owner_hdr).status_code == 403
    assert client.post(f"/api/farms/{farm_id}/reject", headers=owner_hdr, json={"rejection_reason": "No"}).status_code == 403

    # ADMIN -> 200 on DELETE farm, approve/reject farm & unassign
    admin_hdr = _hdr(["ADMIN"])
    assert client.delete(f"/api/farms/{farm_id}", headers=admin_hdr).status_code == 200
    assert client.post(f"/api/farms/{farm_id}/approve", headers=admin_hdr).status_code == 200
    assert client.post(f"/api/farms/{farm_id}/reject", headers=admin_hdr, json={"rejection_reason": "Incomplete"}).status_code == 200
    assert client.delete(f"/api/technicians/{tech_id}/farms/{farm_id}/assign", headers=admin_hdr).status_code == 200

    # Internal recipients endpoint must NOT be exposed publicly on Gateway
    assert client.get(f"/internal/v1/farms/{farm_id}/recipients", headers=admin_hdr).status_code in (403, 404)
