"""Contract Parity and Remediation Verification Tests (CP11.3-R5-C).

Verifies the findings from Claude Independent Security Re-Audit Round 4:
1. IoT /presence/history canonical endpoint and /history legacy alias.
2. IoT PUT /config vs POST /commands/config (501 fail-fast with guidance for authorized caller; 403 for cross-tenant).
3. IoT farm telemetry upstream dependency documentation and forwarding integrity.
4. Notification GET /api/v1/devices (501 Not Implemented for caller; 403 for cross-tenant user_id spoofing).
5. AI camera detail and status forwarding to upstream /api/v1/ai/cameras/{cameraId}/status for admin; 403 locked for non-admin.
"""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_jwt_token
from app.config import settings
from app.main import create_gateway_app

FARM_A_ID = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
FARM_B_ID = "22222222-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
NODE_A1 = "NODE-A1-UUID"
NODE_B1 = "NODE-B1-UUID"
OWNER_A_ID = "33333333-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
OWNER_B_ID = "44444444-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
ADMIN_ID = "99999999-9999-9999-9999-999999999999"


@pytest.fixture
def parity_test_env():
    """Sets up an isolated Gateway TestClient with mock upstream transport capturing requests."""
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
                caller_roles = decoded.get("roles", ["FARM_OWNER"])
            except Exception:
                pass

        # Mock Management Service
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
                if "ADMIN" in caller_roles or caller_id == OWNER_A_ID:
                    return httpx.Response(200, json={"id": NODE_A1, "farm_id": FARM_A_ID, "farmId": FARM_A_ID, "code": "NODE_A1"})
                return httpx.Response(403, json={"detail": "Forbidden: Device not accessible"})
            if f"/api/devices/{NODE_B1}" in url_str:
                if "ADMIN" in caller_roles or caller_id == OWNER_B_ID:
                    return httpx.Response(200, json={"id": NODE_B1, "farm_id": FARM_B_ID, "farmId": FARM_B_ID, "code": "NODE_B1"})
                return httpx.Response(403, json={"detail": "Forbidden: Device not accessible"})
            if f"/api/farms/{FARM_A_ID}" in url_str:
                if "ADMIN" in caller_roles or caller_id == OWNER_A_ID:
                    return httpx.Response(200, json={"id": FARM_A_ID, "owner_id": OWNER_A_ID, "ownerId": OWNER_A_ID, "code": "FARM_A"})
                return httpx.Response(403, json={"detail": "Forbidden: Farm not accessible"})
            if f"/api/farms/{FARM_B_ID}" in url_str:
                if "ADMIN" in caller_roles or caller_id == OWNER_B_ID:
                    return httpx.Response(200, json={"id": FARM_B_ID, "owner_id": OWNER_B_ID, "ownerId": OWNER_B_ID, "code": "FARM_B"})
                return httpx.Response(403, json={"detail": "Forbidden: Farm not accessible"})

        # Mock IoT Service
        if "iot-service" in url_str or ":8002" in url_str:
            if "/presence/history" in url_str:
                return httpx.Response(200, json=[{"deviceId": NODE_A1, "status": "ONLINE", "timestamp": "2026-11-07T00:00:00Z"}])
            if "/commands/config" in url_str and request.method == "POST":
                return httpx.Response(202, json={"commandId": "cmd-123", "status": "PENDING"})
            if "/telemetry" in url_str:
                return httpx.Response(200, json=[{"temperature": 27.5, "humidity": 85.0}])

        # Mock AI Service
        if "ai-service" in url_str or ":8003" in url_str:
            if "/status" in url_str:
                return httpx.Response(200, json={"cameraId": "CAM-001", "status": "RUNNING", "fps": 25.0})

        # Default fallback
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(mock_handler)
    mock_client = httpx.AsyncClient(transport=transport)

    test_app = create_gateway_app()
    test_app.state.http_client = mock_client

    client = TestClient(test_app)
    return {
        "client": client,
        "recorded": recorded_requests,
    }


# =============================================================================
# Case 1: IoT /presence/history & /history Parity
# =============================================================================

def test_iot_presence_history_canonical_route_forwards(parity_test_env):
    """Canonical GET /api/iot/devices/{device_id}/presence/history forwards to upstream presence/history."""
    client = parity_test_env["client"]
    recorded = parity_test_env["recorded"]
    token = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])

    resp = client.get(
        f"/api/iot/devices/{NODE_A1}/presence/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == [{"deviceId": NODE_A1, "status": "ONLINE", "timestamp": "2026-11-07T00:00:00Z"}]

    iot_calls = [r for r in recorded if f"/api/iot/devices/{NODE_A1}/presence/history" in str(r.url)]
    assert len(iot_calls) == 1
    assert iot_calls[0].method == "GET"


def test_iot_history_legacy_alias_maps_to_presence_history(parity_test_env):
    """Legacy alias GET /api/iot/devices/{device_id}/history forwards to upstream presence/history."""
    client = parity_test_env["client"]
    recorded = parity_test_env["recorded"]
    token = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])

    resp = client.get(
        f"/api/iot/devices/{NODE_A1}/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == [{"deviceId": NODE_A1, "status": "ONLINE", "timestamp": "2026-11-07T00:00:00Z"}]

    iot_calls = [r for r in recorded if f"/api/iot/devices/{NODE_A1}/presence/history" in str(r.url)]
    assert len(iot_calls) == 1
    assert iot_calls[0].method == "GET"


def test_iot_presence_history_cross_tenant_fails_closed(parity_test_env):
    """Owner B cannot access presence history for Owner A's device."""
    client = parity_test_env["client"]
    token_b = make_jwt_token(user_id=OWNER_B_ID, roles=["FARM_OWNER"])

    resp = client.get(
        f"/api/iot/devices/{NODE_A1}/presence/history",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 403


# =============================================================================
# Case 2: IoT PUT /config vs POST /commands/config
# =============================================================================

def test_iot_commands_config_post_forwards_correctly(parity_test_env):
    """Primary endpoint POST /api/iot/devices/{device_id}/commands/config forwards to upstream."""
    client = parity_test_env["client"]
    recorded = parity_test_env["recorded"]
    token = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])

    resp = client.post(
        f"/api/iot/devices/{NODE_A1}/commands/config",
        headers={"Authorization": f"Bearer {token}"},
        json={"targetTemp": 28.5, "targetHum": 85.0, "isAutoMode": True},
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "PENDING"

    iot_calls = [r for r in recorded if f"/api/iot/devices/{NODE_A1}/commands/config" in str(r.url)]
    assert len(iot_calls) == 1
    assert iot_calls[0].method == "POST"


def test_iot_put_config_returns_501_for_authorized_caller(parity_test_env):
    """Authorized owner calling PUT /config gets 501 Not Implemented directing to POST /commands/config."""
    client = parity_test_env["client"]
    token = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])

    resp = client.put(
        f"/api/iot/devices/{NODE_A1}/config",
        headers={"Authorization": f"Bearer {token}"},
        json={"targetTemp": 28.5},
    )
    assert resp.status_code == 501
    assert "NOT_IMPLEMENTED" in resp.json()["detail"]
    assert "commands/config" in resp.json()["detail"]


def test_iot_put_config_cross_tenant_returns_403_before_501(parity_test_env):
    """Tenant isolation guard executes before 501; unauthorized caller gets 403, not 501."""
    client = parity_test_env["client"]
    token_b = make_jwt_token(user_id=OWNER_B_ID, roles=["FARM_OWNER"])

    resp = client.put(
        f"/api/iot/devices/{NODE_A1}/config",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"targetTemp": 28.5},
    )
    assert resp.status_code == 403


# =============================================================================
# Case 4: Notification GET /api/v1/devices
# =============================================================================

def test_notification_get_devices_returns_501_for_own_user(parity_test_env):
    """User querying their own devices receives 501 Not Implemented (upstream lacks GET /devices)."""
    client = parity_test_env["client"]
    token = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])

    resp = client.get(
        "/api/v1/devices",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 501
    assert "NOT_IMPLEMENTED" in resp.json()["detail"]


def test_notification_get_devices_cross_tenant_spoofing_returns_403(parity_test_env):
    """Attempting to list devices for another user returns 403 Forbidden before 501."""
    client = parity_test_env["client"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])

    resp = client.get(
        f"/api/v1/devices?userId={OWNER_B_ID}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 403
    assert "Cannot list notification devices for another user" in resp.json()["detail"]


# =============================================================================
# Case 5: AI Camera Detail & Status Parity
# =============================================================================

def test_ai_camera_detail_admin_forwards_to_status(parity_test_env):
    """Admin calling GET /api/v1/ai/cameras/{camera_id} forwards to upstream /api/v1/ai/cameras/{camera_id}/status."""
    client = parity_test_env["client"]
    recorded = parity_test_env["recorded"]
    token_admin = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])

    resp = client.get(
        "/api/v1/ai/cameras/CAM-001",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "RUNNING"

    ai_calls = [r for r in recorded if "/api/v1/ai/cameras/CAM-001/status" in str(r.url)]
    assert len(ai_calls) == 1
    assert ai_calls[0].method == "GET"


def test_ai_camera_status_direct_admin_forwards_to_status(parity_test_env):
    """Admin calling GET /api/v1/ai/cameras/{camera_id}/status forwards to upstream /api/v1/ai/cameras/{camera_id}/status."""
    client = parity_test_env["client"]
    recorded = parity_test_env["recorded"]
    token_admin = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])

    resp = client.get(
        "/api/v1/ai/cameras/CAM-001/status",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "RUNNING"

    ai_calls = [r for r in recorded if "/api/v1/ai/cameras/CAM-001/status" in str(r.url)]
    assert len(ai_calls) == 1
    assert ai_calls[0].method == "GET"


def test_ai_camera_status_non_admin_fails_closed(parity_test_env):
    """Non-admin calling GET /api/v1/ai/cameras/{camera_id}/status returns 403 Forbidden."""
    client = parity_test_env["client"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])

    resp = client.get(
        "/api/v1/ai/cameras/CAM-001/status",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 403
    assert "locked pending camera-to-farm resolver" in resp.json()["detail"]
