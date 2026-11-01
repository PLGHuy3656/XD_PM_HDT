from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx

from app.config.settings import settings
from app.routes import management_gateway_router


def test_management_gateway_forwards_login_and_response(monkeypatch):
    captured = {}
    upstream_response = httpx.Response(
        200,
        json={"access_token": "test-token"},
    )

    class FakeAsyncClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            return False

        async def request(self, method, url, **kwargs):
            captured.update(method=method, url=url, **kwargs)
            return upstream_response

    monkeypatch.setattr(settings, "management_service_url", "http://management")
    monkeypatch.setattr(
        management_gateway_router.httpx,
        "AsyncClient",
        FakeAsyncClient,
    )
    app = FastAPI()
    app.include_router(management_gateway_router.router)

    with TestClient(app) as client:
        response = client.post(
            "/api/management/auth/login?source=web",
            json={"email": "owner@example.test", "password": "test"},
        )

    assert response.status_code == 200
    assert response.json() == {"access_token": "test-token"}
    assert captured["method"] == "POST"
    assert captured["url"] == "http://management/api/auth/login"
    assert captured["params"] == [("source", "web")]
    assert captured["headers"]["content-type"] == "application/json"
    assert captured["timeout"] == 10.0


def test_management_gateway_rejects_unknown_resource(monkeypatch):
    app = FastAPI()
    app.include_router(management_gateway_router.router)

    with TestClient(app) as client:
        response = client.get("/api/management/admin/secrets")

    assert response.status_code == 404
