"""INT03: Gateway notification routing (list/read/read-all) — user scoping stays server-side."""
import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_gateway_app
from tests.test_auth_rbac import make_jwt_token

OWNER_A = "00000000-0000-0000-0000-00000000000a"
OWNER_B = "00000000-0000-0000-0000-00000000000b"
NOTIF_A = "11111111-2222-3333-4444-555555555555"


@pytest.fixture
def env():
    calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
        uid, roles = "anon", []
        if token:
            p = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
            uid, roles = str(p.get("sub")), p.get("roles", [])
        if str(settings.management_service_url) in url and "/api/auth/me" in url:
            return httpx.Response(200, json={"id": uid, "email": "x@t.dev", "status": "ACTIVE", "roles": roles})
        if str(settings.notification_service_url) in url:
            calls.append({"url": url, "method": request.method, "auth_sub": uid})
            # Simulate Notification Service ownership: only Owner A owns NOTIF_A
            if url.endswith(f"/api/notifications/{NOTIF_A}/read"):
                return httpx.Response(200 if uid == OWNER_A else 404, json={"status": "read"} if uid == OWNER_A else {"detail": "Notification not found"})
            if url.endswith("/api/notifications/read-all"):
                return httpx.Response(200, json={"updated_count": 1})
            if "/api/notifications" in url:
                return httpx.Response(200, json=[{"id": NOTIF_A, "title": "t", "category": "warning", "read_at": None}] if uid == OWNER_A else [])
        return httpx.Response(599, json={"detail": "unexpected"})

    app = create_gateway_app()
    app.state.http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with TestClient(app) as c:
        yield c, calls


def _h(uid):
    return {"Authorization": f"Bearer {make_jwt_token(user_id=uid, roles=['FARM_OWNER'])}"}


def test_list_forwards_to_user_scoped_endpoint_with_only_own_params(env):
    c, calls = env
    r = c.get(f"/api/v1/notifications?userId={OWNER_A}&limit=20&unread_only=true&foo=bar", headers=_h(OWNER_A))
    assert r.status_code == 200 and r.json()[0]["id"] == NOTIF_A
    up = calls[-1]["url"]
    assert "/api/notifications?" in up and "limit=20" in up and "unread_only=true" in up
    assert "userId" not in up and "foo" not in up and calls[-1]["auth_sub"] == OWNER_A


def test_list_for_another_user_rejected_before_upstream(env):
    c, calls = env
    assert c.get(f"/api/v1/notifications?userId={OWNER_A}", headers=_h(OWNER_B)).status_code == 403
    assert calls == []


def test_list_bad_limit_rejected(env):
    c, _ = env
    assert c.get(f"/api/v1/notifications?userId={OWNER_A}&limit=999", headers=_h(OWNER_A)).status_code == 400


def test_read_own_notification_forwarded(env):
    c, calls = env
    r = c.post(f"/api/v1/notifications/{NOTIF_A}/read", headers=_h(OWNER_A))
    assert r.status_code == 200 and calls[-1]["url"].endswith(f"/api/notifications/{NOTIF_A}/read")


def test_read_other_users_notification_is_404_from_owner_check(env):
    c, calls = env
    r = c.post(f"/api/v1/notifications/{NOTIF_A}/read", headers=_h(OWNER_B))
    assert r.status_code == 404 and calls[-1]["auth_sub"] == OWNER_B


def test_read_invalid_id_rejected_before_upstream(env):
    c, calls = env
    assert c.post("/api/v1/notifications/NOTIF-001/read", headers=_h(OWNER_A)).status_code == 400
    assert calls == []


def test_read_all_forwarded_and_requires_auth(env):
    c, calls = env
    assert c.post("/api/v1/notifications/read-all", headers=_h(OWNER_A), json={"user_id": OWNER_B}).status_code == 200
    assert calls[-1]["url"].endswith("/api/notifications/read-all") and calls[-1]["auth_sub"] == OWNER_A
    assert c.post("/api/v1/notifications/read-all").status_code == 401
