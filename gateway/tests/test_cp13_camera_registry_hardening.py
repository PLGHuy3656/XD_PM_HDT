"""CP13 Security & Data Integrity Hardening — Gateway camera registry regression (R3).

Reproduces every camera-registry case reported by the Claude targeted retest
(2026-11-14) against a Management mock that follows the hardened contract:
GET /api/cameras/{id} returns 200 only for a CAMERA the caller may access and a
uniform 404 "Camera not found" for unknown ids, other tenants' devices and
non-CAMERA devices.
"""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_gateway_app
from tests.test_auth_rbac import make_jwt_token

OWNER_A = "00000000-0000-0000-0000-0000000000a1"
OWNER_B = "00000000-0000-0000-0000-0000000000b1"
TECH_A = "00000000-0000-0000-0000-0000000000c1"
ADMIN = "00000000-0000-0000-0000-0000000000d1"
FARM_1 = "a18d8eee-cb1a-4b00-b375-d505eb8128d7"
FARM_2 = "f8fc4fa7-0d27-4e0b-89c0-e676e0e73469"
CAM1_UUID = "c0000001-0000-0000-0000-000000000001"
CAM2_UUID = "c0000002-0000-0000-0000-000000000002"
SENSOR_1 = "SWC-DEMO-NODE-001"
SENSOR_2 = "SWC-DEMO-NODE-002"

DEVICES = {
    "CAM-01": {"device_id": CAM1_UUID, "node_id": "CAM-01", "device_type": "CAMERA", "farm_id": FARM_1},
    CAM1_UUID: {"device_id": CAM1_UUID, "node_id": "CAM-01", "device_type": "CAMERA", "farm_id": FARM_1},
    "CAM-02": {"device_id": CAM2_UUID, "node_id": "CAM-02", "device_type": "CAMERA", "farm_id": FARM_2},
    CAM2_UUID: {"device_id": CAM2_UUID, "node_id": "CAM-02", "device_type": "CAMERA", "farm_id": FARM_2},
    SENSOR_1: {"device_id": "d1", "node_id": SENSOR_1, "device_type": "ENVIRONMENT_MONITOR", "farm_id": FARM_1},
    SENSOR_2: {"device_id": "d2", "node_id": SENSOR_2, "device_type": "ENVIRONMENT_MONITOR", "farm_id": FARM_2},
}
ACCESS = {OWNER_A: {FARM_1}, TECH_A: {FARM_1}, OWNER_B: {FARM_2}}


@pytest.fixture
def env():
    state = {"mgmt": "up", "legacy_non_camera_200": False}
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        calls.append(f"{request.method} {request.url.path}")
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        import jwt

        try:
            claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        except Exception:
            return httpx.Response(401, json={"detail": "bad token"})
        uid, roles = str(claims.get("sub")), claims.get("roles", [])

        if str(settings.management_service_url) in url:
            if state["mgmt"] == "down":
                raise httpx.ConnectError("down", request=request)
            if state["mgmt"] == "500" and "/api/cameras/" in url:
                return httpx.Response(500, json={"detail": "boom"})
            if "/api/auth/me" in url:
                return httpx.Response(200, json={"id": uid, "status": "ACTIVE", "roles": roles})
            if "/api/farms/" in url:
                fid = request.url.path.rsplit("/", 1)[-1]
                if "ADMIN" in roles or fid in ACCESS.get(uid, set()):
                    return httpx.Response(200, json={"farm_id": fid})
                return httpx.Response(403, json={"detail": "Forbidden"})
            if "/api/cameras/" in url:
                cid = request.url.path.rsplit("/", 1)[-1]
                dev = DEVICES.get(cid)
                visible = dev and ("ADMIN" in roles or dev["farm_id"] in ACCESS.get(uid, set()))
                if visible and (dev["device_type"] == "CAMERA" or state["legacy_non_camera_200"]):
                    return httpx.Response(200, json=dev)
                return httpx.Response(404, json={"detail": "Camera not found"})
            if "/api/devices/" in url:
                # Must never be used for camera authorization any more.
                return httpx.Response(200, json=DEVICES.get(request.url.path.rsplit("/", 1)[-1], {}))
        if str(settings.ai_service_url) in url:
            return httpx.Response(200, json={"path": request.url.path})
        return httpx.Response(404, json={"detail": "unexpected"})

    app = create_gateway_app()
    app.state.http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with TestClient(app) as client:
        yield client, calls, state


def _get(client, user, roles, camera, suffix="counts/latest"):
    token = make_jwt_token(user_id=user, roles=roles)
    return client.get(f"/api/v1/ai/cameras/{camera}/{suffix}", headers={"Authorization": f"Bearer {token}"})


def _ai_calls(calls):
    return [c for c in calls if c.split(" ", 1)[1].startswith("/api/v1/ai/")]


def _no_type_leak(resp):
    body = resp.text
    assert "ENVIRONMENT_MONITOR" not in body and "device_type" not in body and "is of type" not in body


@pytest.mark.parametrize(
    "user,roles,camera",
    [
        (OWNER_A, ["FARM_OWNER"], SENSOR_1),   # R1 own sensor
        (OWNER_A, ["FARM_OWNER"], SENSOR_2),   # R2 cross-tenant sensor
        (ADMIN, ["ADMIN"], SENSOR_1),          # R3 admin sensor
        (TECH_A, ["TECHNICIAN"], SENSOR_1),
        (OWNER_A, ["FARM_OWNER"], "CAM-99"),   # R9 unknown camera
        (ADMIN, ["ADMIN"], "CAM-FAKE-999"),    # R12 admin unregistered camera
    ],
)
def test_non_camera_or_unregistered_never_forwarded(env, user, roles, camera):
    client, calls, _ = env
    resp = _get(client, user, roles, camera)
    assert resp.status_code == 403
    _no_type_leak(resp)
    assert _ai_calls(calls) == []
    assert not any("/api/devices/" in c for c in calls), "no /api/devices fallback for cameras"


def test_cross_tenant_sensor_and_unknown_id_are_indistinguishable(env):
    client, _, _ = env
    a = _get(client, OWNER_A, ["FARM_OWNER"], SENSOR_2)
    b = _get(client, OWNER_A, ["FARM_OWNER"], "NO-SUCH-DEVICE")
    assert (a.status_code, a.json()) == (b.status_code, b.json()) == (403, a.json())


@pytest.mark.parametrize(
    "user,roles,camera,expected",
    [
        (OWNER_A, ["FARM_OWNER"], "CAM-01", 200),
        (OWNER_A, ["FARM_OWNER"], "CAM-02", 403),
        (OWNER_B, ["FARM_OWNER"], "CAM-02", 200),
        (TECH_A, ["TECHNICIAN"], "CAM-01", 200),
        (TECH_A, ["TECHNICIAN"], "CAM-02", 403),
        (ADMIN, ["ADMIN"], "CAM-02", 200),
    ],
)
def test_camera_ownership_matrix(env, user, roles, camera, expected):
    client, calls, _ = env
    assert _get(client, user, roles, camera).status_code == expected
    assert len(_ai_calls(calls)) == (1 if expected == 200 else 0)


@pytest.mark.parametrize("user,roles", [(OWNER_A, ["FARM_OWNER"]), (ADMIN, ["ADMIN"])])
@pytest.mark.parametrize("suffix", ["counts/latest", "counts", "detections/latest", "status"])
def test_uuid_is_canonicalized_to_node_id(env, user, roles, suffix):
    client, calls, _ = env
    resp = _get(client, user, roles, CAM1_UUID, suffix)
    assert resp.status_code == 200
    ai = _ai_calls(calls)
    assert ai == [f"GET /api/v1/ai/cameras/CAM-01/{suffix}"]
    assert CAM1_UUID not in ai[0]


def test_camera_detail_route_canonicalizes_uuid(env):
    client, calls, _ = env
    token = make_jwt_token(user_id=OWNER_A, roles=["FARM_OWNER"])
    resp = client.get(f"/api/v1/ai/cameras/{CAM1_UUID}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert _ai_calls(calls) == ["GET /api/v1/ai/cameras/CAM-01/status"]


def test_legacy_management_returning_sensor_200_is_still_denied(env):
    client, calls, state = env
    state["legacy_non_camera_200"] = True
    for user, roles in ((OWNER_A, ["FARM_OWNER"]), (ADMIN, ["ADMIN"])):
        resp = _get(client, user, roles, SENSOR_1)
        assert resp.status_code == 403
        _no_type_leak(resp)
    assert _ai_calls(calls) == []


@pytest.mark.parametrize("mode", ["down", "500"])
@pytest.mark.parametrize("user,roles", [(OWNER_A, ["FARM_OWNER"]), (ADMIN, ["ADMIN"])])
def test_management_failure_fails_closed(env, mode, user, roles):
    client, calls, state = env
    # "500": only the camera lookup fails; "down": Management unreachable (auth
    # introspection fails first). Both must fail closed without reaching AI.
    state["mgmt"] = mode
    resp = _get(client, user, roles, "CAM-01")
    if mode == "500":
        assert resp.status_code == 503
    else:
        assert resp.status_code in (401, 503)
    assert _ai_calls(calls) == []


def test_missing_token_is_401(env):
    client, calls, _ = env
    assert client.get("/api/v1/ai/cameras/CAM-01/counts/latest").status_code == 401
    assert _ai_calls(calls) == []
