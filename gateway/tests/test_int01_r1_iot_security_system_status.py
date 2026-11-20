"""INT01-R1 Gateway tests: IoT service-to-service key injection, command RBAC negative paths,
and GET /api/system/status (HEALTHY / DEGRADED / UNAVAILABLE / NOT_DEPLOYED, down + recovery).
"""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_gateway_app
from tests.conftest import make_jwt_token

FARM_A = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
FARM_B = "22222222-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
NODE_A = "SWC-INT01-NODE-01"
OWNER_A = "33333333-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
OWNER_B = "44444444-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
TECH_A = "55555555-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TECH_B = "66666666-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
ADMIN = "99999999-9999-9999-9999-999999999999"
IOT_KEY = "gw-int01-r1-internal-service-key-32-chars!!"


def _bearer(user_id: str, role: str) -> dict:
    return {"Authorization": f"Bearer {make_jwt_token(user_id=user_id, roles=[role])}"}


class Upstreams:
    """Fail-closed mock of Management + IoT (+ optional health probes)."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.iot_runtime: dict | None = {"status": "ok", "service": "iot-service", "mqtt": "connected"}
        self.iot_down = False
        self.management_down = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        auth = request.headers.get("authorization", "")
        caller, roles = OWNER_A, ["FARM_OWNER"]
        if "Bearer " in auth:
            import jwt as pyjwt

            claims = pyjwt.decode(auth.split("Bearer ")[-1], options={"verify_signature": False})
            caller, roles = claims.get("sub"), claims.get("roles", [])

        if ":8001" in url:
            if self.management_down:
                raise httpx.ConnectError("management down")
            if url.endswith("/health"):
                return httpx.Response(200, json={"status": "ok"})
            if "/api/auth/me" in url:
                return httpx.Response(200, json={"id": caller, "email": "x@y.z", "status": "ACTIVE", "roles": roles})
            if f"/api/devices/{NODE_A}" in url:
                if "ADMIN" in roles or caller in (OWNER_A, TECH_A):
                    return httpx.Response(200, json={"id": NODE_A, "farm_id": FARM_A, "farmId": FARM_A})
                return httpx.Response(403, json={"detail": "Forbidden"})
            if "/api/devices/FORGED-NODE" in url:
                return httpx.Response(404, json={"detail": "Device not found"})
        if ":8002" in url:
            if self.iot_down:
                raise httpx.ConnectError("iot down")
            if url.endswith("/health/runtime"):
                if self.iot_runtime is None:
                    return httpx.Response(404, json={"detail": "Not Found"})
                return httpx.Response(200, json=self.iot_runtime)
            if url.endswith("/health"):
                return httpx.Response(200, json={"status": "ok", "service": "iot-service"})
            if "/commands/relay" in url or "/commands/config" in url:
                return httpx.Response(202, json={"commandId": "c-1", "deviceId": NODE_A, "status": "PUBLISHED", "isTerminal": False})
            if "/api/iot/commands/c-1" in url:
                return httpx.Response(200, json={"commandId": "c-1", "deviceId": NODE_A, "status": "TIMEOUT", "isTerminal": True})
        return httpx.Response(404, json={"detail": f"unexpected {request.method} {url}"})

    def iot_calls(self) -> list[httpx.Request]:
        return [r for r in self.requests if ":8002" in str(r.url)]


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setattr(settings, "iot_internal_service_key", IOT_KEY)
    up = Upstreams()
    app = create_gateway_app()
    app.state.http_client = httpx.AsyncClient(transport=httpx.MockTransport(up.handler))
    with TestClient(app) as client:
        yield client, up


# ---------------------------------------------------------------- key injection
def test_authorized_relay_command_forwards_gateway_key_and_strips_forged_key(env):
    client, up = env
    headers = {**_bearer(OWNER_A, "FARM_OWNER"), "X-Internal-Service-Key": "forged-by-browser"}
    r = client.post(f"/api/iot/devices/{NODE_A}/commands/relay", json={"target": "misting", "state": 1}, headers=headers)
    assert r.status_code == 202
    iot = up.iot_calls()[-1]
    assert iot.headers.get("x-internal-service-key") == IOT_KEY
    assert iot.headers.get_list("x-internal-service-key") == [IOT_KEY]


def test_management_upstream_never_receives_iot_key(env):
    client, up = env
    client.post(f"/api/iot/devices/{NODE_A}/commands/relay", json={"target": "fan", "state": 0}, headers=_bearer(OWNER_A, "FARM_OWNER"))
    for req in up.requests:
        if ":8001" in str(req.url):
            assert "x-internal-service-key" not in req.headers


def test_owner_command_status_lookup_sends_key_and_returns_server_terminal_state(env):
    client, up = env
    r = client.get("/api/iot/commands/c-1", headers=_bearer(OWNER_A, "FARM_OWNER"))
    assert r.status_code == 200 and r.json()["status"] == "TIMEOUT" and r.json()["isTerminal"] is True
    assert up.iot_calls()[-1].headers.get("x-internal-service-key") == IOT_KEY


# ---------------------------------------------------------------- command negative paths
def test_unauthenticated_command_rejected_before_iot(env):
    client, up = env
    r = client.post(f"/api/iot/devices/{NODE_A}/commands/relay", json={"target": "fan", "state": 1})
    assert r.status_code == 401
    assert up.iot_calls() == []


def test_cross_farm_owner_command_denied_before_iot(env):
    client, up = env
    r = client.post(f"/api/iot/devices/{NODE_A}/commands/relay", json={"target": "fan", "state": 1}, headers=_bearer(OWNER_B, "FARM_OWNER"))
    assert r.status_code == 403
    assert up.iot_calls() == []


def test_unassigned_technician_command_denied_and_assigned_allowed(env):
    client, up = env
    denied = client.post(f"/api/iot/devices/{NODE_A}/commands/config",
                         json={"targetTemp": 28.0, "targetHum": 80.0, "isAutoMode": False}, headers=_bearer(TECH_B, "TECHNICIAN"))
    assert denied.status_code == 403
    assert up.iot_calls() == []
    ok = client.post(f"/api/iot/devices/{NODE_A}/commands/config",
                     json={"targetTemp": 28.0, "targetHum": 80.0, "isAutoMode": False}, headers=_bearer(TECH_A, "TECHNICIAN"))
    assert ok.status_code == 202


def test_forged_device_identifier_never_reaches_iot(env):
    client, up = env
    r = client.post("/api/iot/devices/FORGED-NODE/commands/relay", json={"target": "fan", "state": 1}, headers=_bearer(OWNER_A, "FARM_OWNER"))
    assert r.status_code in (403, 404)
    assert up.iot_calls() == []


def test_cross_farm_command_status_denied(env):
    client, _ = env
    assert client.get("/api/iot/commands/c-1", headers=_bearer(OWNER_B, "FARM_OWNER")).status_code == 403


# ---------------------------------------------------------------- system status
def _services(client) -> dict:
    r = client.get("/api/system/status", headers=_bearer(ADMIN, "ADMIN"))
    assert r.status_code == 200
    body = r.json()
    assert "services" in body and "checkedAt" in body
    text = r.text
    assert "http://" not in text and IOT_KEY not in text  # no URLs / secrets leaked
    return {s["id"]: s for s in body["services"]}


def test_system_status_requires_admin(env):
    client, _ = env
    assert client.get("/api/system/status").status_code == 401
    assert client.get("/api/system/status", headers=_bearer(OWNER_A, "FARM_OWNER")).status_code == 403
    assert client.get("/api/system/status", headers=_bearer(TECH_A, "TECHNICIAN")).status_code == 403


def test_system_status_int01_scope(env, monkeypatch):
    client, _ = env
    monkeypatch.setattr(settings, "iot_service_deployed", True)
    monkeypatch.setattr(settings, "ai_service_deployed", False)
    monkeypatch.setattr(settings, "notification_service_deployed", False)
    monkeypatch.setattr(settings, "analytics_service_deployed", False)
    s = _services(client)
    assert s["gateway"]["status"] == "HEALTHY"
    assert s["management"]["status"] == "HEALTHY"
    assert s["iot"]["status"] == "HEALTHY" and s["iot"]["deployed"] is True
    for sid in ("ai", "notification", "analytics"):
        assert s[sid]["status"] == "NOT_DEPLOYED" and s[sid]["deployed"] is False


def test_system_status_iot_degraded_when_mqtt_disconnected(env, monkeypatch):
    client, up = env
    monkeypatch.setattr(settings, "iot_service_deployed", True)
    up.iot_runtime = {"status": "degraded", "service": "iot-service", "mqtt": "disconnected"}
    assert _services(client)["iot"]["status"] == "DEGRADED"


def test_system_status_legacy_iot_without_runtime_endpoint_is_degraded_not_healthy(env, monkeypatch):
    client, up = env
    monkeypatch.setattr(settings, "iot_service_deployed", True)
    up.iot_runtime = None
    assert _services(client)["iot"]["status"] == "DEGRADED"


def test_system_status_iot_down_then_recovery(env, monkeypatch):
    client, up = env
    monkeypatch.setattr(settings, "iot_service_deployed", True)
    up.iot_down = True
    assert _services(client)["iot"]["status"] == "UNAVAILABLE"
    up.iot_down = False
    assert _services(client)["iot"]["status"] == "HEALTHY"


def test_system_status_management_unavailable(env, monkeypatch):
    client, up = env
    s_before = _services(client)
    assert s_before["management"]["status"] == "HEALTHY"
    # ADMIN JWT is validated via /api/auth/me on Management, so a Management outage is fail-closed (503)
    up.management_down = True
    r = client.get("/api/system/status", headers=_bearer(ADMIN, "ADMIN"))
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert {s["id"]: s for s in r.json()["services"]}["management"]["status"] == "UNAVAILABLE"
