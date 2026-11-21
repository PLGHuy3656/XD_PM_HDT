"""INT03-R1: Gateway inspection-request routes — explicit, RBAC-gated, ids validated (fail closed)."""
import uuid
from unittest.mock import AsyncMock

from fastapi import Response
from fastapi.testclient import TestClient

import app.auth as auth_mod
import app.routes as r_mod
from app.main import app
from tests.conftest import make_jwt_token


def _hdr(roles):
    return {"Authorization": f"Bearer {make_jwt_token(roles=roles, email='u@test.local')}"}


def _setup(monkeypatch):
    monkeypatch.setattr(auth_mod, "is_token_revoked", lambda token: False)
    monkeypatch.setattr(
        auth_mod,
        "check_user_active_via_management",
        AsyncMock(side_effect=lambda user_id, token, *a, **kw: {"id": user_id, "roles": __import__("jwt").decode(token, options={"verify_signature": False}).get("roles", []), "status": "ACTIVE"}),
    )
    fwd = AsyncMock(return_value=Response(content=b'{"ok":true}', status_code=200, media_type="application/json"))
    monkeypatch.setattr(r_mod.proxy_handler, "forward", fwd)
    return fwd


def test_inspection_routes_rbac(monkeypatch):
    fwd = _setup(monkeypatch)
    c = TestClient(app)
    rid = str(uuid.uuid4())

    assert c.get("/api/inspection-requests").status_code == 401
    assert c.post(f"/api/inspection-requests/{rid}/accept").status_code == 401

    owner, tech, admin = _hdr(["FARM_OWNER"]), _hdr(["TECHNICIAN"]), _hdr(["ADMIN"])
    assert c.post("/api/inspection-requests", headers=owner, json={"farm_id": "x", "title": "abc"}).status_code == 200
    assert c.post("/api/inspection-requests", headers=tech, json={"farm_id": "x", "title": "abc"}).status_code == 403
    assert c.post("/api/inspection-requests", headers=admin, json={"farm_id": "x", "title": "abc"}).status_code == 403

    assert c.post(f"/api/inspection-requests/{rid}/accept", headers=owner).status_code == 403
    assert c.post(f"/api/inspection-requests/{rid}/assign", headers=tech, json={"technician_id": rid}).status_code == 403
    assert c.post(f"/api/inspection-requests/{rid}/cancel", headers=tech).status_code == 403
    assert c.post(f"/api/inspection-requests/{rid}/accept", headers=tech).status_code == 200
    assert c.post(f"/api/inspection-requests/{rid}/assign", headers=admin, json={"technician_id": rid}).status_code == 200

    # unknown action / malformed id fail closed without reaching upstream
    before = fwd.await_count
    assert c.post(f"/api/inspection-requests/{rid}/delete", headers=admin).status_code == 404
    assert c.get("/api/inspection-requests/not-a-uuid", headers=admin).status_code == 404
    assert c.post("/api/inspection-requests/not-a-uuid/accept", headers=tech).status_code == 404
    assert fwd.await_count == before

    # list forwards only whitelisted query params
    c.get("/api/inspection-requests?status=NEW&userId=someone-else&unassigned=true", headers=admin)
    q = fwd.await_args.kwargs.get("canonical_query")
    assert "status=NEW" in q and "unassigned=true" in q and "userId" not in q
