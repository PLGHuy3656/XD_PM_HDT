"""INT03-R2: Targeted Gateway tests for /api/v1/notifications/fcm-tokens (POST & DELETE)."""
import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_gateway_app
from tests.test_auth_rbac import make_jwt_token

OWNER_A = "11111111-1111-1111-1111-111111111111"
OWNER_B = "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def env(monkeypatch):
    from app import auth as gw_auth

    monkeypatch.setattr(gw_auth, "is_token_revoked", lambda _tok: False)
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
            return httpx.Response(204)
        return httpx.Response(404)

    app = create_gateway_app()
    app.state.http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with TestClient(app) as client:
        yield client, calls


def _headers(uid: str, role: str = "FARM_OWNER"):
    return {"Authorization": f"Bearer {make_jwt_token(user_id=uid, roles=[role])}"}


def test_fcm_token_register_requires_auth(env):
    client, _ = env
    res = client.post("/api/v1/notifications/fcm-tokens", json={"token": "tok-1234567890", "platform": "web"})
    assert res.status_code == 401


def test_fcm_token_unregister_requires_auth(env):
    client, _ = env
    res = client.request("DELETE", "/api/v1/notifications/fcm-tokens", json={"token": "tok-1234567890"})
    assert res.status_code == 401


def test_fcm_token_register_rejects_foreign_user_id(env):
    client, calls = env
    res = client.post(
        "/api/v1/notifications/fcm-tokens",
        headers=_headers(OWNER_A),
        json={"token": "tok-1234567890", "platform": "web", "userId": OWNER_B},
    )
    assert res.status_code == 403
    assert calls == []


def test_fcm_token_register_and_unregister_forward_to_notification_service(env):
    client, calls = env
    r_post = client.post(
        "/api/v1/notifications/fcm-tokens",
        headers=_headers(OWNER_A),
        json={"token": "tok-1234567890", "platform": "web"},
    )
    assert r_post.status_code == 204

    r_del = client.request(
        "DELETE",
        "/api/v1/notifications/fcm-tokens",
        headers=_headers(OWNER_A),
        json={"token": "tok-1234567890"},
    )
    assert r_del.status_code == 204
    assert [(c["method"], c["url"].split(str(settings.notification_service_url))[-1]) for c in calls] == [
        ("POST", "/api/notifications/fcm-tokens"),
        ("DELETE", "/api/notifications/fcm-tokens"),
    ]
