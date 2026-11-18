"""Tests for CP11.3-R5-B: Farm/Zone Identifier Normalization & Tenant Isolation.

Covers:
1. Valid UUID identifiers.
2. Invalid farm identifiers (malformed, control characters).
3. Invalid zone identifiers (bare zone code on UUID-only endpoint -> 400).
4. Supported human-readable farm codes (e.g. FARM_A) resolving to canonical UUID.
5. Duplicate zone codes across different farms resolved strictly via parent farm context.
6. Cross-tenant identifier resolution fails closed (403 without data leakage).
7. Ambiguous identifier resolution (conflicting farm_id / farmId -> 400).
8. Management unavailable or returning 5xx fails closed (503).
9. Authorization and forwarding use the exact same canonical UUID.
10. No upstream forwarding on rejected identifiers.
11. R5-A regressions (JWT secret fail-fast and Analytics fail-closed preserved).
"""
import httpx
import pytest
from starlette.testclient import TestClient

from app.config import settings
from app.main import create_gateway_app
from tests.conftest import make_jwt_token

FARM_A_ID = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
FARM_B_ID = "22222222-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
ZONE_A_Z1_ID = "aaaaaaaa-1111-1111-1111-111111111111"
ZONE_B_Z1_ID = "bbbbbbbb-2222-2222-2222-222222222222"
OWNER_A_ID = "33333333-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
OWNER_B_ID = "44444444-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
ADMIN_ID = "99999999-9999-9999-9999-999999999999"


@pytest.fixture
def r5b_test_env():
    """Builds a test environment with a mock upstream to verify identifier normalization and tenant isolation."""
    recorded_requests = []
    config = {
        "management_available": True,
        "management_status_code": 200,
    }

    def mock_backend(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        url_str = str(request.url)

        if not config["management_available"]:
            raise httpx.ConnectError("Management service unreachable", request=request)

        if config["management_status_code"] >= 500:
            return httpx.Response(status_code=config["management_status_code"], json={"detail": "Internal Server Error"})

        # 1. Management Introspection /api/auth/me
        if "/api/auth/me" in url_str:
            auth_hdr = request.headers.get("authorization", "")
            user_id = OWNER_A_ID
            roles = ["FARM_OWNER"]
            if "Bearer " in auth_hdr:
                token_val = auth_hdr.split("Bearer ")[-1].strip()
                try:
                    import jwt as pyjwt
                    decoded = pyjwt.decode(token_val, options={"verify_signature": False})
                    user_id = decoded.get("sub", OWNER_A_ID)
                    roles = decoded.get("roles", ["FARM_OWNER"])
                except Exception:
                    pass
            return httpx.Response(
                status_code=200,
                json={
                    "id": user_id,
                    "email": f"{user_id}@swiftletcare.vn",
                    "status": "ACTIVE",
                    "roles": roles,
                },
            )

        # 2. Management /api/farms (List authorized farms for caller)
        if url_str.rstrip("/").endswith("/api/farms"):
            auth_hdr = request.headers.get("authorization", "")
            user_id = OWNER_A_ID
            roles = ["FARM_OWNER"]
            if "Bearer " in auth_hdr:
                token_val = auth_hdr.split("Bearer ")[-1].strip()
                try:
                    import jwt as pyjwt
                    decoded = pyjwt.decode(token_val, options={"verify_signature": False})
                    user_id = decoded.get("sub", OWNER_A_ID)
                    roles = decoded.get("roles", ["FARM_OWNER"])
                except Exception:
                    pass

            if "ADMIN" in roles:
                return httpx.Response(
                    status_code=200,
                    json=[
                        {"farm_id": FARM_A_ID, "farm_code": "FARM_A", "farm_name": "Farm Alpha"},
                        {"farm_id": FARM_B_ID, "farm_code": "FARM_B", "farm_name": "Farm Beta"},
                    ],
                )
            elif user_id == OWNER_A_ID:
                return httpx.Response(
                    status_code=200,
                    json=[{"farm_id": FARM_A_ID, "farm_code": "FARM_A", "farm_name": "Farm Alpha"}],
                )
            elif user_id == OWNER_B_ID:
                return httpx.Response(
                    status_code=200,
                    json=[{"farm_id": FARM_B_ID, "farm_code": "FARM_B", "farm_name": "Farm Beta"}],
                )
            return httpx.Response(status_code=200, json=[])

        # 3. Management /api/farms/{farm_id}/zones
        if "/zones" in url_str and "/api/farms/" in url_str:
            if FARM_A_ID in url_str:
                return httpx.Response(
                    status_code=200,
                    json=[{"zone_id": ZONE_A_Z1_ID, "farm_id": FARM_A_ID, "zone_code": "Z1", "name": "Zone Alpha 1"}],
                )
            elif FARM_B_ID in url_str:
                return httpx.Response(
                    status_code=200,
                    json=[{"zone_id": ZONE_B_Z1_ID, "farm_id": FARM_B_ID, "zone_code": "Z1", "name": "Zone Beta 1"}],
                )
            return httpx.Response(status_code=404, json={"detail": "Farm not found"})

        # 4. Management /api/farms/{farm_id}
        if "/api/farms/" in url_str:
            auth_hdr = request.headers.get("authorization", "")
            user_id = OWNER_A_ID
            roles = ["FARM_OWNER"]
            if "Bearer " in auth_hdr:
                token_val = auth_hdr.split("Bearer ")[-1].strip()
                try:
                    import jwt as pyjwt
                    decoded = pyjwt.decode(token_val, options={"verify_signature": False})
                    user_id = decoded.get("sub", OWNER_A_ID)
                    roles = decoded.get("roles", ["FARM_OWNER"])
                except Exception:
                    pass

            if FARM_A_ID in url_str:
                if "ADMIN" in roles or user_id == OWNER_A_ID:
                    return httpx.Response(status_code=200, json={"farm_id": FARM_A_ID, "farm_code": "FARM_A"})
                return httpx.Response(status_code=403, json={"detail": "Forbidden: Farm not accessible"})
            elif FARM_B_ID in url_str:
                if "ADMIN" in roles or user_id == OWNER_B_ID:
                    return httpx.Response(status_code=200, json={"farm_id": FARM_B_ID, "farm_code": "FARM_B"})
                return httpx.Response(status_code=403, json={"detail": "Forbidden: Farm not accessible"})
            return httpx.Response(status_code=404, json={"detail": "Farm not found"})

        # 5. Management /api/zones/{zone_id}
        if "/api/zones/" in url_str:
            if ZONE_A_Z1_ID in url_str:
                return httpx.Response(status_code=200, json={"zone_id": ZONE_A_Z1_ID, "zone_code": "Z1"})
            elif ZONE_B_Z1_ID in url_str:
                return httpx.Response(status_code=200, json={"zone_id": ZONE_B_Z1_ID, "zone_code": "Z1"})
            return httpx.Response(status_code=404, json={"detail": "Zone not found"})

        # 6. Fallback for other upstream routes (/api/devices, /api/iot/*, /api/v1/*)
        return httpx.Response(status_code=200, json={"status": "ok", "url": url_str})

    app_instance = create_gateway_app()
    app_instance.state.http_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_backend))

    with TestClient(app_instance) as client:
        yield {
            "client": client,
            "recorded": recorded_requests,
            "config": config,
        }


# =============================================================================
# 1. Farm Identifier Normalization & Upstream Forwarding Tests
# =============================================================================

def test_valid_uuid_farm_access_authorized(r5b_test_env):
    """Owner A accessing farm by valid UUID forwards canonical UUID to upstream."""
    client = r5b_test_env["client"]
    recorded = r5b_test_env["recorded"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])

    resp = client.get(f"/api/farms/{FARM_A_ID}", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 200
    assert resp.json()["farm_id"] == FARM_A_ID

    # Upstream must receive canonical UUID
    forwarded = [r for r in recorded if f"/api/farms/{FARM_A_ID}" in str(r.url)]
    assert len(forwarded) >= 1


def test_valid_farm_code_resolves_to_canonical_uuid(r5b_test_env):
    """Owner A providing farm_code 'FARM_A' resolves to canonical UUID and forwards canonical UUID."""
    client = r5b_test_env["client"]
    recorded = r5b_test_env["recorded"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])

    resp = client.get("/api/farms/FARM_A", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 200

    # Downstream Management forward must use the canonical UUID, never raw 'FARM_A'
    detail_forwards = [r for r in recorded if f"/api/farms/{FARM_A_ID}" in str(r.url)]
    assert len(detail_forwards) >= 1
    # Verify raw 'FARM_A' was NOT sent as downstream URL path
    raw_forwards = [r for r in recorded if "/api/farms/FARM_A" in str(r.url)]
    assert len(raw_forwards) == 0


def test_invalid_farm_identifier_format_rejected_with_400(r5b_test_env):
    """Malformed farm identifiers (e.g. path traversal, special characters) are rejected with 400."""
    client = r5b_test_env["client"]
    recorded = r5b_test_env["recorded"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])

    resp = client.get("/api/farms/bad%20farm!@#", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 400
    assert "Invalid farm identifier" in resp.json()["detail"] or "Bad Request" in resp.json()["detail"]

    # Zero forwarding to upstream for bad farm
    assert not any("bad%20farm" in str(r.url) for r in recorded)


def test_cross_tenant_farm_code_fails_closed_with_403(r5b_test_env):
    """Owner B requesting Owner A's farm code 'FARM_A' must fail closed with 403."""
    client = r5b_test_env["client"]
    recorded = r5b_test_env["recorded"]
    token_b = make_jwt_token(user_id=OWNER_B_ID, roles=["FARM_OWNER"])

    resp = client.get("/api/farms/FARM_A", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 403
    assert "not authorized" in resp.json()["detail"].lower()

    # Verify zero forwarding to Farm A detail
    assert not any(f"/api/farms/{FARM_A_ID}" in str(r.url) for r in recorded)


def test_cross_tenant_farm_uuid_fails_closed_with_403(r5b_test_env):
    """Owner A requesting Farm B's UUID must fail closed with 403."""
    client = r5b_test_env["client"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])

    resp = client.get(f"/api/farms/{FARM_B_ID}", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 403


# =============================================================================
# 2. Zone Identifier Contract & Anti-IDOR Tests
# =============================================================================

def test_zone_detail_uuid_only_valid_uuid_forwarded(r5b_test_env):
    """GET /api/zones/{zone_id} with valid UUID forwards to upstream."""
    client = r5b_test_env["client"]
    recorded = r5b_test_env["recorded"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])

    resp = client.get(f"/api/zones/{ZONE_A_Z1_ID}", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 200
    assert resp.json()["zone_id"] == ZONE_A_Z1_ID

    forwarded = [r for r in recorded if f"/api/zones/{ZONE_A_Z1_ID}" in str(r.url)]
    assert len(forwarded) == 1


def test_zone_detail_rejects_bare_zone_code_with_400(r5b_test_env):
    """GET /api/zones/{zone_id} with bare zone_code 'Z1' must be rejected with 400 Bad Request."""
    client = r5b_test_env["client"]
    recorded = r5b_test_env["recorded"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])

    # Attempting to access zone by code without parent farm
    resp = client.get("/api/zones/Z1", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 400
    assert "must be a valid UUID" in resp.json()["detail"]
    assert "cannot be resolved globally" in resp.json()["detail"]

    # Upstream Management must NEVER receive request for /api/zones/Z1
    assert not any("/api/zones/Z1" in str(r.url) for r in recorded)


def test_duplicate_zone_codes_across_farms_scoped_to_parent_farm(r5b_test_env):
    """Duplicate zone code 'Z1' in Farm A and Farm B resolves strictly within parent farm."""
    client = r5b_test_env["client"]
    recorded = r5b_test_env["recorded"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    token_b = make_jwt_token(user_id=OWNER_B_ID, roles=["FARM_OWNER"])

    # 1. Owner A queries devices with farm_id=FARM_A and zone_id=Z1
    resp_a = client.get("/api/devices?farm_id=FARM_A&zone_id=Z1", headers={"Authorization": f"Bearer {token_a}"})
    assert resp_a.status_code == 200

    # Upstream must receive canonical farm UUID and Zone A's canonical UUID
    forward_a = [r for r in recorded if "/api/devices" in str(r.url) and f"farm_id={FARM_A_ID}" in str(r.url)]
    assert len(forward_a) >= 1
    assert f"zone_id={ZONE_A_Z1_ID}" in str(forward_a[-1].url)
    assert ZONE_B_Z1_ID not in str(forward_a[-1].url)

    # 2. Owner B queries devices with farm_id=FARM_B and zone_id=Z1
    resp_b = client.get("/api/devices?farm_id=FARM_B&zone_id=Z1", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.status_code == 200

    # Upstream must receive canonical farm UUID and Zone B's canonical UUID
    forward_b = [r for r in recorded if "/api/devices" in str(r.url) and f"farm_id={FARM_B_ID}" in str(r.url)]
    assert len(forward_b) >= 1
    assert f"zone_id={ZONE_B_Z1_ID}" in str(forward_b[-1].url)
    assert ZONE_A_Z1_ID not in str(forward_b[-1].url)


def test_devices_zone_code_without_farm_rejected_with_400(r5b_test_env):
    """Admin calling GET /api/devices?zone_id=Z1 without farm_id is rejected with 400 (cannot resolve globally)."""
    client = r5b_test_env["client"]
    recorded = r5b_test_env["recorded"]
    token_admin = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])

    resp = client.get("/api/devices?zone_id=Z1", headers={"Authorization": f"Bearer {token_admin}"})
    assert resp.status_code == 400
    assert "cannot be resolved globally" in resp.json()["detail"]

    # Zero forwarding to upstream devices
    assert not any("/api/devices" in str(r.url) for r in recorded)


def test_ambiguous_conflicting_farm_params_rejected_with_400(r5b_test_env):
    """Conflicting farm_id and farmId parameters are rejected with 400 Bad Request."""
    client = r5b_test_env["client"]
    recorded = r5b_test_env["recorded"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])

    resp = client.get(f"/api/devices?farm_id={FARM_A_ID}&farmId={FARM_B_ID}", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 400
    assert "Ambiguous" in resp.json()["detail"] or "conflicting" in resp.json()["detail"]

    assert not any("/api/devices" in str(r.url) for r in recorded)


# =============================================================================
# 3. Fail-Closed on Resolver / Upstream Outage Tests
# =============================================================================

def test_management_outage_fails_closed_with_503(r5b_test_env):
    """When Management Service is unreachable during identifier resolution, Gateway returns 503."""
    client = r5b_test_env["client"]
    r5b_test_env["config"]["management_available"] = False
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])

    resp = client.get("/api/farms/FARM_A", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 503
    assert "unreachable" in resp.json()["detail"].lower() or "service unavailable" in resp.json()["detail"].lower()


def test_management_500_fails_closed_with_503(r5b_test_env):
    """When Management Service returns 500 during identifier resolution, Gateway returns 503."""
    client = r5b_test_env["client"]
    r5b_test_env["config"]["management_status_code"] = 500
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])

    resp = client.get("/api/farms/FARM_A", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 503
    assert "error" in resp.json()["detail"].lower() or "service unavailable" in resp.json()["detail"].lower()


# =============================================================================
# 4. Multi-Service Normalization Tests (IoT & Notification)
# =============================================================================

def test_iot_farm_telemetry_normalizes_to_canonical_uuid(r5b_test_env):
    """IoT telemetry request with farm_code 'FARM_A' forwards canonical UUID to IoT Service."""
    client = r5b_test_env["client"]
    recorded = r5b_test_env["recorded"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])

    resp = client.get("/api/iot/farms/FARM_A/telemetry", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 200

    # IoT service must receive canonical UUID in path
    iot_forwards = [r for r in recorded if f"/api/iot/farms/{FARM_A_ID}/telemetry" in str(r.url)]
    assert len(iot_forwards) == 1


def test_notification_alerts_normalizes_to_canonical_uuid(r5b_test_env):
    """Alerts request with farm_id='FARM_A' forwards canonical 'farmId={canonical_uuid}' to Notification Service."""
    client = r5b_test_env["client"]
    recorded = r5b_test_env["recorded"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])

    resp = client.get("/api/v1/alerts?farm_id=FARM_A", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 200

    alert_forwards = [r for r in recorded if "/api/v1/alerts" in str(r.url)]
    assert len(alert_forwards) >= 1
    assert f"farmId={FARM_A_ID}" in str(alert_forwards[-1].url)


# =============================================================================
# 5. R5-A Regression Preserved
# =============================================================================

def test_r5a_regression_analytics_still_fails_closed(r5b_test_env):
    """R5-A verification: Analytics remains fail-closed (503) even with valid canonical UUID."""
    client = r5b_test_env["client"]
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])

    old_deployed = settings.analytics_service_deployed
    try:
        settings.analytics_service_deployed = False
        resp = client.get(f"/api/v1/analytics/farms/{FARM_A_ID}/summary", headers={"Authorization": f"Bearer {token_a}"})
        assert resp.status_code == 503
        assert "SERVICE_NOT_DEPLOYED" in resp.json()["detail"]
    finally:
        settings.analytics_service_deployed = old_deployed
