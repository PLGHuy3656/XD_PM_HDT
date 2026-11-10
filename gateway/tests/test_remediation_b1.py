"""Unit & Integration tests for CP11 Remediation Phase B1 & B1-FIX.

Covers:
1. P1-01: Query encoding remediation in proxy_ai_camera_counts (startTime/endTime URL encoding, injection prevention, +07:00 preservation, allowlisting, limit validation).
2. P2 Test Hardening:
   - Fail-closed mock upstream (404 on unexpected paths).
   - Exact upstream path & HTTP method verification.
   - Technician device detail route (self allowed, cross-technician 403, admin 200).
   - Authentication enforcement (missing/invalid JWT -> 401 on all 9 routes).
   - Role spoofing defense (forged roles in token neutralized by /me introspection).
   - Cross-tenant IDOR defense on all scoped routes.
   - Path traversal security on all 9 new routes (400 Bad Request).
"""
from __future__ import annotations

import urllib.parse
import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_gateway_app
from tests.conftest import make_jwt_token

FARM_A_ID = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
FARM_B_ID = "22222222-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
NODE_A1 = "NODE-A1-UUID"
NODE_B1 = "NODE-B1-UUID"
OWNER_A_ID = "33333333-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
OWNER_B_ID = "44444444-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
TECH_A_ID = "55555555-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TECH_B_ID = "66666666-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
ADMIN_ID = "99999999-9999-9999-9999-999999999999"
SPOOFED_USER_ID = "77777777-7777-7777-7777-777777777777"


@pytest.fixture
def b1_test_env():
    """Sets up an isolated Gateway TestClient with strict fail-closed upstream mocks."""
    recorded_requests: list[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        url_str = str(request.url)

        # Resolve caller identity from Authorization header
        auth_hdr = request.headers.get("authorization", "")
        caller_id = OWNER_A_ID
        caller_roles = ["FARM_OWNER"]
        if "Bearer " in auth_hdr:
            token_val = auth_hdr.split("Bearer ")[-1].strip()
            try:
                import jwt as pyjwt
                decoded = pyjwt.decode(token_val, options={"verify_signature": False})
                caller_id = decoded.get("sub", OWNER_A_ID)
                # Introspection rule: SPOOFED_USER_ID claims ADMIN in token, but /me returns FARM_OWNER
                if caller_id == SPOOFED_USER_ID:
                    caller_roles = ["FARM_OWNER"]
                else:
                    caller_roles = decoded.get("roles", ["FARM_OWNER"])
            except Exception:
                pass

        # 1. Management Service Mock (:8001)
        if "management-service" in url_str or ":8001" in url_str:
            if "/api/auth/me" in url_str:
                return httpx.Response(
                    200,
                    json={
                        "id": caller_id,
                        "email": f"{caller_id}@swiftletcare.vn",
                        "status": "ACTIVE",
                        "roles": caller_roles,
                    },
                )
            if f"/api/devices/{NODE_A1}" in url_str:
                if "ADMIN" in caller_roles or caller_id in (OWNER_A_ID, TECH_A_ID):
                    return httpx.Response(200, json={"id": NODE_A1, "farm_id": FARM_A_ID, "farmId": FARM_A_ID, "code": "NODE_A1"})
                return httpx.Response(403, json={"detail": "Forbidden: Device not accessible"})
            if f"/api/devices/{NODE_B1}" in url_str:
                if "ADMIN" in caller_roles or caller_id in (OWNER_B_ID, TECH_B_ID):
                    return httpx.Response(200, json={"id": NODE_B1, "farm_id": FARM_B_ID, "farmId": FARM_B_ID, "code": "NODE_B1"})
                return httpx.Response(403, json={"detail": "Forbidden: Device not accessible"})
            if f"/api/farms/{FARM_A_ID}" in url_str:
                if "ADMIN" in caller_roles or caller_id in (OWNER_A_ID, TECH_A_ID):
                    return httpx.Response(200, json={"id": FARM_A_ID, "owner_id": OWNER_A_ID, "ownerId": OWNER_A_ID, "code": "FARM_A"})
                return httpx.Response(403, json={"detail": "Forbidden: Farm not accessible"})
            if f"/api/farms/{FARM_B_ID}" in url_str:
                if "ADMIN" in caller_roles or caller_id in (OWNER_B_ID, TECH_B_ID):
                    return httpx.Response(200, json={"id": FARM_B_ID, "owner_id": OWNER_B_ID, "ownerId": OWNER_B_ID, "code": "FARM_B"})
                return httpx.Response(403, json={"detail": "Forbidden: Farm not accessible"})
            if f"/api/technicians/{TECH_A_ID}/farms/{FARM_A_ID}/devices/{NODE_A1}" in url_str:
                return httpx.Response(200, json={"deviceId": NODE_A1, "farmId": FARM_A_ID, "status": "ONLINE"})
            if f"/api/technicians/{TECH_B_ID}/farms/{FARM_B_ID}/devices/{NODE_B1}" in url_str:
                return httpx.Response(200, json={"deviceId": NODE_B1, "farmId": FARM_B_ID, "status": "ONLINE"})
            if f"/api/technicians/{TECH_A_ID}/farms/{FARM_A_ID}/devices" in url_str:
                return httpx.Response(200, json=[{"deviceId": NODE_A1, "farmId": FARM_A_ID}])
            if f"/api/technicians/{TECH_B_ID}/farms/{FARM_B_ID}/devices" in url_str:
                return httpx.Response(200, json=[{"deviceId": NODE_B1, "farmId": FARM_B_ID}])
            if f"/api/technicians/{TECH_A_ID}/farms" in url_str:
                return httpx.Response(200, json=[{"farmId": FARM_A_ID, "farmName": "Farm A", "isPrimary": True}])
            if f"/api/technicians/{TECH_B_ID}/farms" in url_str:
                return httpx.Response(200, json=[{"farmId": FARM_B_ID, "farmName": "Farm B", "isPrimary": True}])

        # 2. IoT Service Mock (:8002)
        if "iot-service" in url_str or ":8002" in url_str:
            if f"/devices/{NODE_A1}/commands" in url_str:
                return httpx.Response(200, json=[{"commandId": "cmd-001", "deviceId": NODE_A1, "action": "SET_RELAY", "status": "COMPLETED"}])
            if f"/devices/{NODE_B1}/commands" in url_str:
                return httpx.Response(200, json=[{"commandId": "cmd-002", "deviceId": NODE_B1, "action": "SET_RELAY", "status": "COMPLETED"}])
            if "/commands/cmd-001" in url_str:
                return httpx.Response(200, json={"commandId": "cmd-001", "deviceId": NODE_A1, "status": "COMPLETED"})

        # 3. AI Service Mock (:8003)
        if "ai-service" in url_str or ":8003" in url_str:
            if "/counts/latest" in url_str:
                return httpx.Response(200, json={"cameraId": "CAM-001", "inCount": 150, "outCount": 120, "netCount": 30})
            if "/counts" in url_str:
                return httpx.Response(200, json=[{"cameraId": "CAM-001", "inCount": 150, "outCount": 120, "netCount": 30}])
            if "/detections/latest" in url_str:
                return httpx.Response(200, json={"cameraId": "CAM-001", "detections": [{"class": "bird", "confidence": 0.94}]})
            if "/events/EVT-001" in url_str:
                return httpx.Response(200, json={"eventId": "EVT-001", "eventType": "PREDATOR_DETECTED", "severity": "HIGH"})
            if "/api/v1/ai/cameras" in url_str:
                return httpx.Response(200, json=[{"cameraId": "CAM-001", "status": "ONLINE"}])

        # Fail-closed default: unexpected upstream path receives 404
        return httpx.Response(404, json={"detail": f"Mock upstream endpoint not found: {request.method} {url_str}"})

    transport = httpx.MockTransport(mock_handler)
    mock_client = httpx.AsyncClient(transport=transport)

    test_app = create_gateway_app()
    test_app.state.http_client = mock_client

    with TestClient(test_app) as client:
        yield {
            "client": client,
            "requests": recorded_requests,
        }


# =============================================================================
# 1. P1-01: AI Camera Counts Query Encoding Remediation
# =============================================================================

def test_ai_counts_preserves_plus_in_timezone(b1_test_env):
    """P1-01 Fix: Timestamps with '+07:00' must be URL-encoded (%2B07:00), not sent as literal '+' which becomes space."""
    client = b1_test_env["client"]
    token = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])
    ts = "2026-11-01T08:00:00+07:00"

    resp = client.get(
        f"/api/v1/ai/cameras/CAM-001/counts?startTime={urllib.parse.quote(ts)}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    ai_calls = [r for r in b1_test_env["requests"] if "/counts" in str(r.url) and "/latest" not in str(r.url)]
    assert len(ai_calls) > 0
    upstream_url = str(ai_calls[-1].url)

    # Must contain %2B07%3A00 or %2B07:00
    assert "%2B07" in upstream_url or "%2B07%3A00" in upstream_url
    assert "+07:00" not in upstream_url  # Unencoded plus must not appear in raw query string

    # When decoded by upstream, it perfectly matches the original timestamp
    parsed_qs = urllib.parse.parse_qs(urllib.parse.urlparse(upstream_url).query)
    assert parsed_qs["startTime"][0] == ts


def test_ai_counts_prevents_parameter_injection_limit(b1_test_env):
    """P1-01 Fix: Attempting to inject '&limit=500' via startTime must be safely URL-encoded into value."""
    client = b1_test_env["client"]
    token = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])
    malicious_startTime = "2026-11-01T00:00:00Z&limit=500"

    resp = client.get(
        f"/api/v1/ai/cameras/CAM-001/counts?startTime={urllib.parse.quote(malicious_startTime)}&limit=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    ai_calls = [r for r in b1_test_env["requests"] if "/counts" in str(r.url) and "/latest" not in str(r.url)]
    upstream_url = str(ai_calls[-1].url)
    parsed_qs = urllib.parse.parse_qs(urllib.parse.urlparse(upstream_url).query)

    # Injected limit=500 must NOT exist as a separate parameter; limit must remain 10
    assert parsed_qs["limit"] == ["10"]
    # startTime must contain the literal '&limit=500' as part of its single value
    assert parsed_qs["startTime"][0] == malicious_startTime


def test_ai_counts_prevents_parameter_injection_camera_id(b1_test_env):
    """P1-01 Fix: Attempting to inject '&cameraId=OTHER' via endTime must be safely URL-encoded."""
    client = b1_test_env["client"]
    token = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])
    malicious_endTime = "2026-11-02T00:00:00Z&cameraId=CAM-ATTACKER"

    resp = client.get(
        f"/api/v1/ai/cameras/CAM-001/counts?endTime={urllib.parse.quote(malicious_endTime)}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    ai_calls = [r for r in b1_test_env["requests"] if "/counts" in str(r.url) and "/latest" not in str(r.url)]
    upstream_url = str(ai_calls[-1].url)
    parsed_qs = urllib.parse.parse_qs(urllib.parse.urlparse(upstream_url).query)

    # cameraId must NOT be injected into upstream query
    assert "cameraId" not in parsed_qs
    assert parsed_qs["endTime"][0] == malicious_endTime


def test_ai_counts_strips_non_allowlisted_query_params(b1_test_env):
    """P1-01 Fix: Client query parameters outside contract (e.g. bypass_flag) must NOT be forwarded upstream."""
    client = b1_test_env["client"]
    token = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])

    resp = client.get(
        "/api/v1/ai/cameras/CAM-001/counts?limit=25&unauthorized_flag=true&admin=1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    ai_calls = [r for r in b1_test_env["requests"] if "/counts" in str(r.url) and "/latest" not in str(r.url)]
    upstream_url = str(ai_calls[-1].url)
    parsed_qs = urllib.parse.parse_qs(urllib.parse.urlparse(upstream_url).query)

    assert parsed_qs == {"limit": ["25"]}


@pytest.mark.parametrize("invalid_limit", ["0", "501", "-1", "abc", "null"])
def test_ai_counts_limit_validation(b1_test_env, invalid_limit):
    """FastAPI validation rejects invalid limit values (ge=1, le=500) with 422 Unprocessable Entity."""
    client = b1_test_env["client"]
    token = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])

    resp = client.get(
        f"/api/v1/ai/cameras/CAM-001/counts?limit={invalid_limit}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_ai_counts_valid_canonical_query_integrity(b1_test_env):
    """Valid canonical query with all 3 parameters forwards unchanged."""
    client = b1_test_env["client"]
    token = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])

    resp = client.get(
        "/api/v1/ai/cameras/CAM-001/counts?limit=100&startTime=2026-11-01T00:00:00Z&endTime=2026-11-02T00:00:00Z",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    ai_calls = [r for r in b1_test_env["requests"] if "/counts" in str(r.url) and "/latest" not in str(r.url)]
    upstream_url = str(ai_calls[-1].url)
    parsed_qs = urllib.parse.parse_qs(urllib.parse.urlparse(upstream_url).query)

    assert parsed_qs["limit"] == ["100"]
    assert parsed_qs["startTime"] == ["2026-11-01T00:00:00Z"]
    assert parsed_qs["endTime"] == ["2026-11-02T00:00:00Z"]


# =============================================================================
# 2. NB-2: AI Camera Counts & Detections
# =============================================================================

def test_ai_counts_latest_admin_allowed(b1_test_env):
    """Admin can successfully retrieve latest AI counts with exact upstream path and method."""
    client = b1_test_env["client"]
    token = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])
    resp = client.get("/api/v1/ai/cameras/CAM-001/counts/latest", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["netCount"] == 30

    req = [r for r in b1_test_env["requests"] if "/counts/latest" in str(r.url)][-1]
    assert req.method == "GET"
    assert req.url.path == "/api/v1/ai/cameras/CAM-001/counts/latest"


def test_ai_counts_latest_non_admin_denied(b1_test_env):
    """Farm owners and technicians are blocked with 403 on counts/latest (fail closed)."""
    client = b1_test_env["client"]
    token_owner = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    resp_owner = client.get("/api/v1/ai/cameras/CAM-001/counts/latest", headers={"Authorization": f"Bearer {token_owner}"})
    assert resp_owner.status_code == 403
    assert "restricted to ADMIN" in resp_owner.json()["detail"]

    token_tech = make_jwt_token(user_id=TECH_A_ID, roles=["TECHNICIAN"])
    resp_tech = client.get("/api/v1/ai/cameras/CAM-001/counts/latest", headers={"Authorization": f"Bearer {token_tech}"})
    assert resp_tech.status_code == 403


def test_ai_counts_history_non_admin_denied(b1_test_env):
    """Non-admin callers cannot query historical counts."""
    client = b1_test_env["client"]
    token_owner = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    resp = client.get("/api/v1/ai/cameras/CAM-001/counts", headers={"Authorization": f"Bearer {token_owner}"})
    assert resp.status_code == 403


def test_ai_detections_latest_admin_allowed(b1_test_env):
    """Admin can retrieve latest camera detection results."""
    client = b1_test_env["client"]
    token = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])
    resp = client.get("/api/v1/ai/cameras/CAM-001/detections/latest", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["detections"][0]["class"] == "bird"

    req = [r for r in b1_test_env["requests"] if "/detections/latest" in str(r.url)][-1]
    assert req.method == "GET"
    assert req.url.path == "/api/v1/ai/cameras/CAM-001/detections/latest"


def test_ai_detections_latest_non_admin_denied(b1_test_env):
    """Non-admin callers cannot access latest detections."""
    client = b1_test_env["client"]
    token_owner = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    resp = client.get("/api/v1/ai/cameras/CAM-001/detections/latest", headers={"Authorization": f"Bearer {token_owner}"})
    assert resp.status_code == 403


# =============================================================================
# 3. NB-4: AI Event Detail
# =============================================================================

def test_ai_event_detail_admin_allowed(b1_test_env):
    """Admin can retrieve single AI event details."""
    client = b1_test_env["client"]
    token = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])
    resp = client.get("/api/v1/ai/events/EVT-001", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["eventId"] == "EVT-001"

    req = [r for r in b1_test_env["requests"] if "/events/EVT-001" in str(r.url)][-1]
    assert req.method == "GET"
    assert req.url.path == "/api/v1/ai/events/EVT-001"


def test_ai_event_detail_non_admin_denied(b1_test_env):
    """Non-admin callers are blocked on AI event detail pending resolver."""
    client = b1_test_env["client"]
    token_owner = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    resp = client.get("/api/v1/ai/events/EVT-001", headers={"Authorization": f"Bearer {token_owner}"})
    assert resp.status_code == 403
    assert "event detail is locked" in resp.json()["detail"]


# =============================================================================
# 4. NB-4: IoT Device Command History & Command Status
# =============================================================================

def test_iot_device_commands_authorized_owner_allowed(b1_test_env):
    """Owner A can query command history of their own NODE-A1."""
    client = b1_test_env["client"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    resp = client.get(f"/api/iot/devices/{NODE_A1}/commands?limit=20", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["commandId"] == "cmd-001"

    req = [r for r in b1_test_env["requests"] if f"/devices/{NODE_A1}/commands" in str(r.url)][-1]
    assert req.method == "GET"
    assert req.url.path == f"/api/iot/devices/{NODE_A1}/commands"
    assert "limit=20" in str(req.url)


def test_iot_device_commands_cross_tenant_denied(b1_test_env):
    """Owner A cannot query command history of Farm B's NODE-B1 (IDOR protection)."""
    client = b1_test_env["client"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    resp = client.get(f"/api/iot/devices/{NODE_B1}/commands", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 403


def test_iot_device_commands_admin_allowed_any(b1_test_env):
    """Admin can query command history on any device."""
    client = b1_test_env["client"]
    token_admin = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])
    resp = client.get(f"/api/iot/devices/{NODE_B1}/commands", headers={"Authorization": f"Bearer {token_admin}"})
    assert resp.status_code == 200


def test_iot_command_status_admin_allowed(b1_test_env):
    """Admin can query specific command lifecycle status."""
    client = b1_test_env["client"]
    token_admin = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])
    resp = client.get("/api/iot/commands/cmd-001", headers={"Authorization": f"Bearer {token_admin}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "COMPLETED"

    req = [r for r in b1_test_env["requests"] if "/commands/cmd-001" in str(r.url)][-1]
    assert req.method == "GET"
    assert req.url.path == "/api/iot/commands/cmd-001"


def test_iot_command_status_non_admin_denied(b1_test_env):
    """Non-admin callers cannot query /api/iot/commands/{id} (fail-closed pending resolver)."""
    client = b1_test_env["client"]
    token_owner = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    resp = client.get("/api/iot/commands/cmd-001", headers={"Authorization": f"Bearer {token_owner}"})
    assert resp.status_code == 403


# =============================================================================
# 5. NB-4: Technician Assigned Farms and Devices
# =============================================================================

def test_technician_farms_self_allowed(b1_test_env):
    """Technician A can query their own assigned farms."""
    client = b1_test_env["client"]
    token_tech_a = make_jwt_token(user_id=TECH_A_ID, roles=["TECHNICIAN"])
    resp = client.get(f"/api/technicians/{TECH_A_ID}/farms", headers={"Authorization": f"Bearer {token_tech_a}"})
    assert resp.status_code == 200
    assert resp.json()[0]["farmId"] == FARM_A_ID

    req = [r for r in b1_test_env["requests"] if f"/technicians/{TECH_A_ID}/farms" in str(r.url)][-1]
    assert req.method == "GET"
    assert req.url.path == f"/api/technicians/{TECH_A_ID}/farms"


def test_technician_farms_cross_tenant_denied(b1_test_env):
    """Technician A cannot query Technician B's assigned farms."""
    client = b1_test_env["client"]
    token_tech_a = make_jwt_token(user_id=TECH_A_ID, roles=["TECHNICIAN"])
    resp = client.get(f"/api/technicians/{TECH_B_ID}/farms", headers={"Authorization": f"Bearer {token_tech_a}"})
    assert resp.status_code == 403
    assert "Cannot access another technician" in resp.json()["detail"]


def test_technician_farms_admin_allowed(b1_test_env):
    """Admin can query any technician's assigned farms."""
    client = b1_test_env["client"]
    token_admin = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])
    resp = client.get(f"/api/technicians/{TECH_B_ID}/farms", headers={"Authorization": f"Bearer {token_admin}"})
    assert resp.status_code == 200


def test_technician_farm_devices_self_allowed(b1_test_env):
    """Technician A can query devices in their assigned farm."""
    client = b1_test_env["client"]
    token_tech_a = make_jwt_token(user_id=TECH_A_ID, roles=["TECHNICIAN"])
    resp = client.get(f"/api/technicians/{TECH_A_ID}/farms/{FARM_A_ID}/devices", headers={"Authorization": f"Bearer {token_tech_a}"})
    assert resp.status_code == 200

    req = [r for r in b1_test_env["requests"] if f"/technicians/{TECH_A_ID}/farms/{FARM_A_ID}/devices" in str(r.url)][-1]
    assert req.method == "GET"
    assert req.url.path == f"/api/technicians/{TECH_A_ID}/farms/{FARM_A_ID}/devices"


def test_technician_farm_devices_cross_tenant_denied(b1_test_env):
    """Technician A cannot query devices under Technician B's assignment."""
    client = b1_test_env["client"]
    token_tech_a = make_jwt_token(user_id=TECH_A_ID, roles=["TECHNICIAN"])
    resp = client.get(f"/api/technicians/{TECH_B_ID}/farms/{FARM_B_ID}/devices", headers={"Authorization": f"Bearer {token_tech_a}"})
    assert resp.status_code == 403


def test_technician_farm_device_detail_self_allowed(b1_test_env):
    """Technician A can query specific device detail in their assigned farm."""
    client = b1_test_env["client"]
    token_tech_a = make_jwt_token(user_id=TECH_A_ID, roles=["TECHNICIAN"])
    resp = client.get(
        f"/api/technicians/{TECH_A_ID}/farms/{FARM_A_ID}/devices/{NODE_A1}",
        headers={"Authorization": f"Bearer {token_tech_a}"},
    )
    assert resp.status_code == 200
    assert resp.json()["deviceId"] == NODE_A1

    req = [r for r in b1_test_env["requests"] if f"/technicians/{TECH_A_ID}/farms/{FARM_A_ID}/devices/{NODE_A1}" in str(r.url)][-1]
    assert req.method == "GET"
    assert req.url.path == f"/api/technicians/{TECH_A_ID}/farms/{FARM_A_ID}/devices/{NODE_A1}"


def test_technician_farm_device_detail_cross_tenant_denied(b1_test_env):
    """Technician A cannot query specific device detail under Technician B's assignment."""
    client = b1_test_env["client"]
    token_tech_a = make_jwt_token(user_id=TECH_A_ID, roles=["TECHNICIAN"])
    resp = client.get(
        f"/api/technicians/{TECH_B_ID}/farms/{FARM_B_ID}/devices/{NODE_B1}",
        headers={"Authorization": f"Bearer {token_tech_a}"},
    )
    assert resp.status_code == 403
    assert "Cannot access another technician" in resp.json()["detail"]


def test_technician_farm_device_detail_admin_allowed(b1_test_env):
    """Admin can query specific device detail under any technician assignment."""
    client = b1_test_env["client"]
    token_admin = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])
    resp = client.get(
        f"/api/technicians/{TECH_B_ID}/farms/{FARM_B_ID}/devices/{NODE_B1}",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert resp.status_code == 200
    assert resp.json()["deviceId"] == NODE_B1


# =============================================================================
# 6. Authentication & Role Spoofing Tests
# =============================================================================

@pytest.mark.parametrize(
    "route_path",
    [
        "/api/v1/ai/cameras/CAM-001/counts/latest",
        "/api/v1/ai/cameras/CAM-001/counts",
        "/api/v1/ai/cameras/CAM-001/detections/latest",
        "/api/v1/ai/events/EVT-001",
        f"/api/iot/devices/{NODE_A1}/commands",
        "/api/iot/commands/cmd-001",
        f"/api/technicians/{TECH_A_ID}/farms",
        f"/api/technicians/{TECH_A_ID}/farms/{FARM_A_ID}/devices",
        f"/api/technicians/{TECH_A_ID}/farms/{FARM_A_ID}/devices/{NODE_A1}",
    ],
)
def test_missing_or_invalid_jwt_returns_401_on_new_routes(b1_test_env, route_path):
    """Every new route rejects missing or invalid Bearer tokens with 401 Unauthorized."""
    client = b1_test_env["client"]

    # 1. Missing Authorization header
    resp_no_auth = client.get(route_path)
    assert resp_no_auth.status_code == 401

    # 2. Malformed token
    resp_bad_auth = client.get(route_path, headers={"Authorization": "Bearer bad.token.here"})
    assert resp_bad_auth.status_code == 401


def test_role_spoofing_prevented_by_me_introspection(b1_test_env):
    """A user forging roles=['ADMIN'] in their token cannot access admin routes; /me overrides to FARM_OWNER."""
    client = b1_test_env["client"]
    # Token claims ADMIN, but /me returns FARM_OWNER for SPOOFED_USER_ID
    forged_token = make_jwt_token(user_id=SPOOFED_USER_ID, roles=["ADMIN"])

    resp = client.get(
        "/api/v1/ai/cameras/CAM-001/counts/latest",
        headers={"Authorization": f"Bearer {forged_token}"},
    )
    assert resp.status_code == 403
    assert "restricted to ADMIN" in resp.json()["detail"]


# =============================================================================
# 7. Security & Path Traversal Guards on All 9 New Routes
# =============================================================================

@pytest.mark.parametrize(
    "attack_path",
    [
        "/api/v1/ai/cameras/..%2fadmin/counts/latest",
        "/api/v1/ai/cameras/CAM-001%23extra/counts",
        "/api/v1/ai/cameras/..%2fadmin/detections/latest",
        "/api/v1/ai/events/..%2fadmin",
        "/api/iot/devices/..%2fadmin/commands",
        "/api/iot/commands/..%2fadmin",
        "/api/technicians/..%2fadmin/farms",
        f"/api/technicians/{TECH_A_ID}/farms/..%2fadmin/devices",
        f"/api/technicians/{TECH_A_ID}/farms/{FARM_A_ID}/devices/..%2fadmin",
    ],
)
def test_path_traversal_blocked_on_all_9_routes(b1_test_env, attack_path):
    """Path traversal sequences on all 9 new routes must be rejected with 400 Bad Request."""
    client = b1_test_env["client"]
    token_admin = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])
    resp = client.get(attack_path, headers={"Authorization": f"Bearer {token_admin}"})
    assert resp.status_code == 400


# =============================================================================
# 8. P2-R1: Query Allowlist Empty-State Leak Prevention
# =============================================================================

def test_p2_r1_ai_counts_with_unallowlisted_params_forwards_empty_query(b1_test_env):
    """P2-R1 Probe 1: AI counts called with ?cameraId=OTHER&foo=1 (no allowlisted params) must forward EMPTY query."""
    client = b1_test_env["client"]
    token = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])

    resp = client.get(
        "/api/v1/ai/cameras/CAM-001/counts?cameraId=OTHER&foo=1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    ai_calls = [r for r in b1_test_env["requests"] if "/counts" in str(r.url) and "/latest" not in str(r.url)]
    assert len(ai_calls) > 0
    upstream_url = str(ai_calls[-1].url)

    # Must NOT have query string at all
    parsed = urllib.parse.urlparse(upstream_url)
    assert parsed.query == "", f"Expected empty query, got {parsed.query}"
    assert "cameraId" not in parsed.query
    assert "foo" not in parsed.query


def test_p2_r1_iot_command_history_with_unallowlisted_params_forwards_empty_query(b1_test_env):
    """P2-R1 Probe 2: IoT command history with ?evil=1&deviceId=OTHER (no limit) must forward EMPTY query."""
    client = b1_test_env["client"]
    token = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])

    resp = client.get(
        f"/api/iot/devices/{NODE_A1}/commands?evil=1&deviceId=OTHER",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    iot_calls = [r for r in b1_test_env["requests"] if f"/devices/{NODE_A1}/commands" in str(r.url)]
    assert len(iot_calls) > 0
    upstream_url = str(iot_calls[-1].url)

    parsed = urllib.parse.urlparse(upstream_url)
    assert parsed.query == "", f"Expected empty query, got {parsed.query}"
    assert "evil" not in parsed.query
    assert "deviceId" not in parsed.query


def test_p2_r1_ai_cameras_with_unallowlisted_params_forwards_empty_query(b1_test_env):
    """P2-R1 Probe 3: AI cameras list with ?evil=1&admin=1 (no farm_id) must forward EMPTY query."""
    client = b1_test_env["client"]
    token = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])

    resp = client.get(
        "/api/v1/ai/cameras?evil=1&admin=1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    cam_calls = [r for r in b1_test_env["requests"] if "/api/v1/ai/cameras" in str(r.url) and "/counts" not in str(r.url) and "/detections" not in str(r.url)]
    assert len(cam_calls) > 0
    upstream_url = str(cam_calls[-1].url)

    parsed = urllib.parse.urlparse(upstream_url)
    assert parsed.query == "", f"Expected empty query, got {parsed.query}"
    assert "evil" not in parsed.query
    assert "admin" not in parsed.query


def test_p2_r1_ai_cameras_with_valid_farm_id_forwards_canonical(b1_test_env):
    """P2-R1 Positive: AI cameras list with ?farmId=FARM_A_ID&evil=1 forwards ONLY farm_id=FARM_A_ID."""
    client = b1_test_env["client"]
    token = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])

    resp = client.get(
        f"/api/v1/ai/cameras?farmId={FARM_A_ID}&evil=1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    cam_calls = [r for r in b1_test_env["requests"] if "/api/v1/ai/cameras" in str(r.url) and "/counts" not in str(r.url)]
    upstream_url = str(cam_calls[-1].url)

    parsed = urllib.parse.urlparse(upstream_url)
    assert parsed.query == f"farm_id={FARM_A_ID}"
    assert "evil" not in parsed.query
