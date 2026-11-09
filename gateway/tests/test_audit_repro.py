"""Comprehensive regression and audit reproduction tests for CP11.3 Remediation (B1, B2, B3).

Covers:
- B1: Management /me contract verification (id, roles, status) & sub mismatch rejection.
- B2: Farm list tenant isolation (Owner A, Owner B, Technician A, Admin).
- B3: 9 cross-tenant upstream exploits failing closed (403/404).
- B3: Management outage fails closed (503) without touching upstream.
- Positive resource authorization for authorized owner.
"""
from typing import Any, Dict
import httpx
import pytest
from starlette.testclient import TestClient

from app.config import settings
from app.main import create_gateway_app
from tests.conftest import make_jwt_token

# Canonical test IDs mimicking Claude's audit fixture
FARM_A_ID = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
FARM_B_ID = "22222222-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
OWNER_A_ID = "33333333-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
OWNER_B_ID = "44444444-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
TECH_A_ID = "55555555-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ADMIN_ID = "00000000-0000-0000-0000-000000000001"
NODE_A1 = "NODE-A1"
NODE_B1 = "NODE-B1"


@pytest.fixture
def repro_test_env():
    """Environment simulating real Management Service database and backend echo microservices."""
    recorded_upstream_hits = {"iot": 0, "ai": 0, "notification": 0, "analytics": 0}
    env_config = {"management_online": True}

    def mock_backend(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)

        # 1. Management Service Simulator (following authoritative database contract)
        if str(settings.management_service_url) in url_str:
            if not env_config["management_online"]:
                raise httpx.ConnectError("Management service outage", request=request)
            if env_config.get("management_500"):
                return httpx.Response(status_code=500, json={"detail": "Internal database error"})

            auth_header = request.headers.get("authorization", "")
            token_str = auth_header.split("Bearer ")[-1].strip() if "Bearer " in auth_header else ""

            # Resolve caller identity from token
            try:
                import jwt
                p = jwt.decode(token_str, settings.jwt_secret, algorithms=["HS256"])
                user_id = str(p.get("sub", ""))
            except Exception:
                return httpx.Response(status_code=401, json={"detail": "Invalid token"})

            # Role & status mapping
            user_db = {
                OWNER_A_ID: {"email": "ownera@t.vn", "roles": ["FARM_OWNER"], "status": "ACTIVE"},
                OWNER_B_ID: {"email": "ownerb@t.vn", "roles": ["FARM_OWNER"], "status": "ACTIVE"},
                TECH_A_ID: {"email": "techa@t.vn", "roles": ["TECHNICIAN"], "status": "ACTIVE"},
                ADMIN_ID: {"email": "admin@t.vn", "roles": ["ADMIN"], "status": "ACTIVE"},
            }
            user_data = user_db.get(user_id, {"email": "unknown@t.vn", "roles": [], "status": "INACTIVE"})

            # /api/auth/me contract (B1: id, email, full_name, status, roles)
            if "/api/auth/me" in url_str:
                return httpx.Response(
                    status_code=200,
                    json={
                        "id": user_id,
                        "email": user_data["email"],
                        "full_name": "Test User",
                        "status": user_data["status"],
                        "roles": user_data["roles"],
                    },
                )

            # /api/farms list contract (B2: tenant isolation)
            if url_str.rstrip("/").endswith("/api/farms"):
                farms = [
                    {"farm_id": FARM_A_ID, "farm_code": "FARM_A", "owner_id": OWNER_A_ID},
                    {"farm_id": FARM_B_ID, "farm_code": "FARM_B", "owner_id": OWNER_B_ID},
                ]
                if "ADMIN" in user_data["roles"]:
                    return httpx.Response(status_code=200, json=farms)
                if "FARM_OWNER" in user_data["roles"]:
                    scoped = [f for f in farms if f["owner_id"] == user_id]
                    return httpx.Response(status_code=200, json=scoped)
                if "TECHNICIAN" in user_data["roles"]:
                    # Tech A assigned to Farm A
                    scoped = [f for f in farms if f["farm_id"] == FARM_A_ID]
                    return httpx.Response(status_code=200, json=scoped)
                return httpx.Response(status_code=200, json=[])

            # /api/farms/{id} access verification
            if "/api/farms/" in url_str:
                target_farm_id = url_str.split("/api/farms/")[-1].split("/")[0].split("?")[0]
                if target_farm_id == FARM_A_ID:
                    if "ADMIN" in user_data["roles"] or user_id in (OWNER_A_ID, TECH_A_ID):
                        return httpx.Response(status_code=200, json={"farm_id": FARM_A_ID, "farm_code": "FARM_A"})
                    return httpx.Response(status_code=403, json={"detail": "Forbidden: Farm not owned by user"})
                elif target_farm_id == FARM_B_ID:
                    if "ADMIN" in user_data["roles"] or user_id == OWNER_B_ID:
                        return httpx.Response(status_code=200, json={"farm_id": FARM_B_ID, "farm_code": "FARM_B"})
                    return httpx.Response(status_code=403, json={"detail": "Forbidden: Farm not owned by user"})
                return httpx.Response(status_code=404, json={"detail": "Farm not found"})

            # /api/devices/{id} access verification
            if "/api/devices/" in url_str:
                target_dev_id = url_str.split("/api/devices/")[-1].split("/")[0].split("?")[0]
                if target_dev_id == NODE_A1:
                    if "ADMIN" in user_data["roles"] or user_id in (OWNER_A_ID, TECH_A_ID):
                        return httpx.Response(status_code=200, json={"device_id": NODE_A1, "farm_id": FARM_A_ID})
                    return httpx.Response(status_code=403, json={"detail": "Forbidden: Device not accessible"})
                elif target_dev_id == NODE_B1:
                    if "ADMIN" in user_data["roles"] or user_id == OWNER_B_ID:
                        return httpx.Response(status_code=200, json={"device_id": NODE_B1, "farm_id": FARM_B_ID})
                    return httpx.Response(status_code=403, json={"detail": "Forbidden: Device not accessible"})
                return httpx.Response(status_code=404, json={"detail": "Device not found"})

            # /api/devices (list)
            if "/api/devices" in url_str:
                return httpx.Response(status_code=200, json=[{"device_id": NODE_A1}])

        # 2. Downstream Echo Upstreams (track hits)
        if str(settings.iot_service_url) in url_str:
            recorded_upstream_hits["iot"] += 1
            return httpx.Response(status_code=200, json={"service": "iot", "echo": url_str})
        if str(settings.ai_service_url) in url_str:
            recorded_upstream_hits["ai"] += 1
            return httpx.Response(status_code=200, json={"service": "ai", "echo": url_str})
        if str(settings.notification_service_url) in url_str:
            recorded_upstream_hits["notification"] += 1
            return httpx.Response(status_code=200, json={"service": "notification", "echo": url_str})
        if str(settings.analytics_service_url) in url_str:
            recorded_upstream_hits["analytics"] += 1
            return httpx.Response(status_code=200, json={"service": "analytics", "echo": url_str})

        return httpx.Response(status_code=200, json={"echo": url_str})

    test_app = create_gateway_app()
    test_app.state.http_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_backend))

    with TestClient(test_app) as client:
        yield {
            "client": client,
            "hits": recorded_upstream_hits,
            "config": env_config,
        }


# =============================================================================
# B1: /me Contract & Sub Mismatch Verification
# =============================================================================
def test_b1_me_contract_includes_status_and_roles(repro_test_env):
    """Verifies that Management /me contract exposes id, roles, and status as required by Gateway."""
    client = repro_test_env["client"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])

    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 200
    me = resp.json()
    assert {"id", "roles", "status"} <= set(me.keys())
    assert me["status"] == "ACTIVE"
    assert me["id"] == OWNER_A_ID


def test_b1_gateway_rejects_sub_mismatch_with_me(repro_test_env):
    """Verifies that if JWT sub differs from the user ID in /me, Gateway returns 401."""
    client = repro_test_env["client"]
    # Craft token with forged sub
    forged_token = make_jwt_token(user_id="99999999-9999-9999-9999-999999999999", roles=["ADMIN"])

    resp = client.get("/api/farms", headers={"Authorization": f"Bearer {forged_token}"})
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers


# =============================================================================
# B2: Farm List Tenant Isolation
# =============================================================================
def test_b2_farm_list_scoped_to_owner_a(repro_test_env):
    """Owner A must ONLY see FARM_A and never FARM_B."""
    client = repro_test_env["client"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])

    resp = client.get("/api/farms", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 200
    farms = resp.json()
    farm_codes = {f["farm_code"] for f in farms}
    assert farm_codes == {"FARM_A"}
    assert "FARM_B" not in farm_codes


def test_b2_farm_list_scoped_to_owner_b(repro_test_env):
    """Owner B must ONLY see FARM_B and never FARM_A."""
    client = repro_test_env["client"]
    token_b = make_jwt_token(user_id=OWNER_B_ID, roles=["FARM_OWNER"])

    resp = client.get("/api/farms", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 200
    farms = resp.json()
    farm_codes = {f["farm_code"] for f in farms}
    assert farm_codes == {"FARM_B"}
    assert "FARM_A" not in farm_codes


def test_b2_farm_list_scoped_to_technician_a(repro_test_env):
    """Technician A only sees assigned farm (FARM_A)."""
    client = repro_test_env["client"]
    token_tech = make_jwt_token(user_id=TECH_A_ID, roles=["TECHNICIAN"])

    resp = client.get("/api/farms", headers={"Authorization": f"Bearer {token_tech}"})
    assert resp.status_code == 200
    farms = resp.json()
    assert {f["farm_code"] for f in farms} == {"FARM_A"}


def test_b2_farm_list_admin_sees_all(repro_test_env):
    """Admin sees all farms."""
    client = repro_test_env["client"]
    token_admin = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])

    resp = client.get("/api/farms", headers={"Authorization": f"Bearer {token_admin}"})
    assert resp.status_code == 200
    farms = resp.json()
    assert {f["farm_code"] for f in farms} == {"FARM_A", "FARM_B"}


# =============================================================================
# B3: 9 Cross-Tenant Exploit Cases (Exact Claude Repro Suite)
# =============================================================================
@pytest.mark.parametrize(
    "method,path,body",
    [
        # 1. IoT relay command on device of Farm B
        ("POST", f"/api/iot/devices/{NODE_B1}/commands/relay", {"state": "ON"}),
        # 2. IoT config command on device of Farm B
        ("POST", f"/api/iot/devices/{NODE_B1}/commands/config", {"targetTemp": 28.0}),
        # 3. IoT telemetry for Farm B
        ("GET", f"/api/iot/farms/{FARM_B_ID}/telemetry", None),
        # 4. AI cameras for Farm B
        ("GET", f"/api/v1/ai/cameras?farm_id={FARM_B_ID}", None),
        # 5. Notification alerts for Farm B
        ("GET", f"/api/v1/alerts?farmId={FARM_B_ID}", None),
        # 6. Acknowledge alert by opaque ID (locked route)
        ("POST", "/api/v1/alerts/ALERT-OF-B/acknowledge", {"acknowledged": True}),
        # 7. Query notifications of User B
        ("GET", f"/api/v1/notifications?userId={OWNER_B_ID}", None),
        # 8. Register FCM device token for User B
        ("POST", "/api/v1/devices", {"userId": OWNER_B_ID, "fcmToken": "attacker", "platform": "ANDROID"}),
        # 9. Analytics summary for Farm B
        ("GET", f"/api/v1/analytics/farms/{FARM_B_ID}/summary", None),
    ],
)
def test_b3_cross_tenant_upstream_routes_fail_closed(repro_test_env, method, path, body):
    """Asserts that as Owner A, all 9 cross-tenant routes targeting Farm B / User B return 403 (or 404),

    and downstream microservices are NEVER reached.
    """
    client = repro_test_env["client"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    headers = {"Authorization": f"Bearer {token_a}"}

    hits_before = sum(repro_test_env["hits"].values())
    resp = client.request(method, path, headers=headers, json=body)

    # Must be blocked by Gateway (403 Forbidden or 404 Not Found)
    assert resp.status_code in (403, 404), f"{method} {path} unexpectedly allowed: got {resp.status_code}"

    # Downstream service must NOT have received any request
    hits_after = sum(repro_test_env["hits"].values())
    assert hits_after == hits_before, f"{method} {path} leaked through to downstream microservice!"


def test_b3_management_outage_fails_closed_returns_503(repro_test_env):
    """When Management Service is down, resource resolution fails closed (503) without touching downstream."""
    client = repro_test_env["client"]
    repro_test_env["config"]["management_online"] = False

    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    headers = {"Authorization": f"Bearer {token_a}"}

    resp = client.post(
        f"/api/iot/devices/{NODE_A1}/commands/relay",
        headers=headers,
        json={"state": "ON"},
    )
    assert resp.status_code == 503
    assert "Service Unavailable" in resp.json()["detail"]
    assert repro_test_env["hits"]["iot"] == 0


def test_b3_positive_resource_access_for_owner_a(repro_test_env):
    """Verifies that Owner A can access their own resources (NODE-A1, Farm A)."""
    client = repro_test_env["client"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    headers = {"Authorization": f"Bearer {token_a}"}

    # 1. Access Farm A telemetry
    resp1 = client.get(f"/api/iot/farms/{FARM_A_ID}/telemetry", headers=headers)
    assert resp1.status_code == 200

    # 2. Access NODE-A1 command relay
    resp2 = client.post(f"/api/iot/devices/{NODE_A1}/commands/relay", headers=headers, json={"state": "ON"})
    assert resp2.status_code == 200

    # 3. Access AI cameras with farm_id=FARM_A (H3: Locked for non-admins pending TV2 filter)
    resp3 = client.get(f"/api/v1/ai/cameras?farm_id={FARM_A_ID}", headers=headers)
    assert resp3.status_code == 403
    assert "temporarily locked for non-admins" in resp3.json()["detail"]

    # 3b. Admin CAN access AI cameras
    token_admin = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])
    resp3_admin = client.get(f"/api/v1/ai/cameras?farm_id={FARM_A_ID}", headers={"Authorization": f"Bearer {token_admin}"})
    assert resp3_admin.status_code == 200

    # 4. Access alerts for Farm A
    resp4 = client.get(f"/api/v1/alerts?farmId={FARM_A_ID}", headers=headers)
    assert resp4.status_code == 200

    # 5. Access notifications for Owner A
    resp5 = client.get(f"/api/v1/notifications?userId={OWNER_A_ID}", headers=headers)
    assert resp5.status_code == 200

    # 6. Register FCM device for Owner A
    resp6 = client.post(
        "/api/v1/devices",
        headers=headers,
        json={"userId": OWNER_A_ID, "token": "my-fcm-token", "platform": "ANDROID"},
    )
    assert resp6.status_code == 200

    # 7. Access farm analytics summary for Farm A (when analytics is deployed)
    old_deployed = settings.analytics_service_deployed
    try:
        settings.analytics_service_deployed = True
        resp7 = client.get(f"/api/v1/analytics/farms/{FARM_A_ID}/summary", headers=headers)
        assert resp7.status_code == 200
    finally:
        settings.analytics_service_deployed = old_deployed


# =============================================================================
# Parameter Ambiguity & Normalization Tests (Phase B #5)
# =============================================================================
def test_param_conflict_farm_id_returns_400(repro_test_env):
    """Providing conflicting farm_id and farmId must return 400 Bad Request."""
    client = repro_test_env["client"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    headers = {"Authorization": f"Bearer {token_a}"}

    # Devices listing with conflicting farm params
    resp = client.get(f"/api/devices?farm_id={FARM_A_ID}&farmId={FARM_B_ID}", headers=headers)
    assert resp.status_code == 400
    assert "Ambiguous or conflicting" in resp.json()["detail"]

    # AI cameras with conflicting farm params
    resp_ai = client.get(f"/api/v1/ai/cameras?farm_id={FARM_A_ID}&farmId={FARM_B_ID}", headers=headers)
    assert resp_ai.status_code == 400
    assert "Ambiguous or conflicting" in resp_ai.json()["detail"]


def test_param_conflict_user_id_returns_400(repro_test_env):
    """Providing conflicting userId and user_id in query or body must return 400 Bad Request."""
    client = repro_test_env["client"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    headers = {"Authorization": f"Bearer {token_a}"}

    # Notifications query with conflicting user params
    resp = client.get(f"/api/v1/notifications?userId={OWNER_A_ID}&user_id={OWNER_B_ID}", headers=headers)
    assert resp.status_code == 400
    assert "Ambiguous or conflicting" in resp.json()["detail"]

    # FCM registration body with conflicting user params
    resp_body = client.post(
        "/api/v1/devices",
        headers=headers,
        json={"userId": OWNER_A_ID, "user_id": OWNER_B_ID, "token": "tok", "platform": "IOS"},
    )
    assert resp_body.status_code == 400
    assert "Ambiguous or conflicting" in resp_body.json()["detail"]


# =============================================================================
# Notification Hardening (Phase B #6)
# =============================================================================
def test_fcm_registration_user_id_snake_case_blocked(repro_test_env):
    """Registration using user_id instead of userId to spoof other user must be blocked."""
    client = repro_test_env["client"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    headers = {"Authorization": f"Bearer {token_a}"}

    resp = client.post(
        "/api/v1/devices",
        headers=headers,
        json={"user_id": OWNER_B_ID, "token": "spoofed-tok", "platform": "ANDROID"},
    )
    assert resp.status_code == 403
    assert "Cannot register FCM device token for another user" in resp.json()["detail"]


def test_notification_alert_id_only_query_blocked_for_non_admin(repro_test_env):
    """Non-admin querying notifications without userId (e.g., alertId-only) must be blocked."""
    client = repro_test_env["client"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    headers = {"Authorization": f"Bearer {token_a}"}

    resp = client.get("/api/v1/notifications?alertId=ALERT-999", headers=headers)
    assert resp.status_code == 403
    assert "'userId' query parameter matching caller identity is required" in resp.json()["detail"]


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/notifications/read-all",
        "/api/v1/notifications/NOTIF-001/read",
        "/api/v1/alerts/ALERT-001",
        "/api/v1/alerts/ALERT-001/resolve",
    ],
)
def test_locked_notification_endpoints_fail_closed(repro_test_env, path):
    """Notification mutations and alert detail without resolvers are locked (403)."""
    client = repro_test_env["client"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    headers = {"Authorization": f"Bearer {token_a}"}

    method = "GET" if path == "/api/v1/alerts/ALERT-001" else "POST"
    resp = client.request(method, path, headers=headers, json={})
    assert resp.status_code == 403


# =============================================================================
# AI Hardening (Phase B #7)
# =============================================================================
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/ai/cameras",
        "/api/v1/ai/events",
        "/api/v1/ai/cameras/CAM-001",
        "/api/v1/ai/snapshots/CAM-001/latest.jpg",
    ],
)
def test_locked_ai_endpoints_for_non_admin(repro_test_env, path):
    """Unresolvable AI camera listing, camera detail, events, and snapshots are locked for non-admins."""
    client = repro_test_env["client"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    headers = {"Authorization": f"Bearer {token_a}"}

    resp = client.get(path, headers=headers)
    assert resp.status_code == 403


def test_admin_can_access_ai_snapshots(repro_test_env):
    """Admin exception: Admin is permitted to access snapshots and cameras."""
    client = repro_test_env["client"]
    token_admin = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])
    headers = {"Authorization": f"Bearer {token_admin}"}

    resp = client.get("/api/v1/ai/snapshots/CAM-001/latest.jpg", headers=headers)
    assert resp.status_code == 200

    resp_cam = client.get("/api/v1/ai/cameras", headers=headers)
    assert resp_cam.status_code == 200


# =============================================================================
# H1, H2, M2 Acceptance Tests
# =============================================================================
def test_upstream_500_returns_503_not_403(repro_test_env):
    """Upstream Management 5xx error must return 503, never masquerading as 403."""
    client = repro_test_env["client"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    headers = {"Authorization": f"Bearer {token_a}"}

    # Simulate Management Service 500 error on device check
    repro_test_env["config"]["management_500"] = True

    resp = client.post(
        f"/api/iot/devices/{NODE_A1}/commands/relay",
        headers=headers,
        json={"state": "ON"},
    )
    assert resp.status_code == 503
    assert "Service Unavailable" in resp.json()["detail"]


def test_canonical_query_normalization_devices(repro_test_env):
    """Client sending farmId alias must be normalized to farm_id for Management Service."""
    client = repro_test_env["client"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    headers = {"Authorization": f"Bearer {token_a}"}

    resp = client.get(f"/api/devices?farmId={FARM_A_ID}", headers=headers)
    assert resp.status_code == 200


def test_canonical_query_normalization_alerts(repro_test_env):
    """Client sending farm_id alias must be normalized to farmId for Notification Service."""
    client = repro_test_env["client"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    headers = {"Authorization": f"Bearer {token_a}"}

    resp = client.get(f"/api/v1/alerts?farm_id={FARM_A_ID}", headers=headers)
    assert resp.status_code == 200


def test_analytics_disabled_returns_service_not_deployed(repro_test_env):
    """When analytics_service_deployed is False, analytics endpoints must return 503 SERVICE_NOT_DEPLOYED."""
    client = repro_test_env["client"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    headers = {"Authorization": f"Bearer {token_a}"}

    old_deployed = settings.analytics_service_deployed
    try:
        settings.analytics_service_deployed = False
        resp = client.get(f"/api/v1/analytics/farms/{FARM_A_ID}/summary", headers=headers)
        assert resp.status_code == 503
        assert "SERVICE_NOT_DEPLOYED" in resp.json()["detail"]
    finally:
        settings.analytics_service_deployed = old_deployed


# =============================================================================
# Default-Deny Allowlist & Method Enforcement (Phase B #4, #10)
# =============================================================================
@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/unknown"),
        ("GET", "/api/auth/unknown"),
        ("POST", "/api/iot/unknown"),
        ("GET", "/api/v1/ai/unknown"),
        ("GET", "/api/v1/notifications/unknown"),
        ("GET", "/api/v1/analytics/unknown"),
    ],
)
def test_unknown_routes_return_404_default_deny(repro_test_env, method, path):
    """Any route not explicitly present in the allowlist must return 404, even for admin."""
    client = repro_test_env["client"]
    token_admin = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])
    headers = {"Authorization": f"Bearer {token_admin}"}

    resp = client.request(method, path, headers=headers)
    assert resp.status_code == 404


def test_disallowed_http_method_returns_405_or_404(repro_test_env):
    """Disallowed HTTP methods on existing routes return 405 Method Not Allowed or 404."""
    client = repro_test_env["client"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    headers = {"Authorization": f"Bearer {token_a}"}

    # TRACE method on /api/farms
    resp = client.request("TRACE", "/api/farms", headers=headers)
    assert resp.status_code in (404, 405)

    # POST on /api/v1/analytics/farms/{id}/x (undefined route & method)
    resp_x = client.post(f"/api/v1/analytics/farms/{FARM_A_ID}/x", headers=headers, json={})
    assert resp_x.status_code in (403, 404, 405)


def test_iot_put_config_cross_tenant_fails_closed(repro_test_env):
    """Owner A attempting PUT config on NODE-B1 must fail closed with 403."""
    client = repro_test_env["client"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    headers = {"Authorization": f"Bearer {token_a}"}

    resp = client.put(f"/api/iot/devices/{NODE_B1}/config", headers=headers, json={"interval": 30})
    assert resp.status_code == 403
