"""
Live End-to-End Integration Tests for Gateway -> Analytics Service -> PostgreSQL analytics_db.

Tests (Phase 4):
1. Farm Owner accesses own farm summary (Live PostgreSQL data from analytics_db).
2. Farm Owner accesses own farm trends with query parameters.
3. Cross-tenant defense: Farm Owner blocked from accessing other farms (403 Forbidden).
4. Technician scoped access: permitted for assigned farm, blocked for unassigned farm.
5. Admin access: Admin permitted to view global trends (/api/v1/analytics/trends).
6. Non-admin blocked from global trends (Owner and Technician receive 403).
7. JWT authentication guards: missing, invalid, expired tokens receive 401.
8. Service unavailable: fail-closed when analytics_service_deployed is False or upstream down.
9. Database unavailable: controlled 503 DATABASE_UNAVAILABLE when database is down.
10. Query validation: invalid period string returns 400 INVALID_PERIOD.
11. Null safety: missing data preserved as JSON null, zero fabrication prevented.
"""
import os
import jwt
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
import httpx
import pytest
from starlette.testclient import TestClient

from app.config import settings
from app.main import create_gateway_app
from tests.conftest import make_jwt_token

# Real synchronized demo IDs in PostgreSQL 18 management_db and analytics_db
FARM_1_ID = "a18d8eee-cb1a-4b00-b375-d505eb8128d7"
FARM_1_OWNER_ID = "d632d08d-2a47-46f0-8798-83fd733024c3"

FARM_2_ID = "f8fc4fa7-0d27-4e0b-89c0-e676e0e73469"
FARM_2_OWNER_ID = "19072e30-d339-4ac8-8715-01340462aca1"

TECH_USER_ID = "77777777-7777-7777-7777-777777777777"
ADMIN_USER_ID = "99999999-9999-9999-9999-999999999999"

LIVE_ANALYTICS_URL = "http://127.0.0.1:8005"


@pytest.fixture(scope="module")
def live_e2e_client():
    """
    Sets up Gateway test client with:
    - Management Service mock for authentication introspection and farm authorization.
    - REAL passthrough HTTP forwarding to live Analytics Service on http://127.0.0.1:8005.
    """
    real_http_client = httpx.AsyncClient(timeout=10.0)

    async def gateway_upstream_router(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)

        # 1. Management Service Auth Introspection & Farm Authorization Mock
        if "8001" in url_str or "/api/auth/me" in url_str or "/api/farms" in url_str:
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return httpx.Response(status_code=401, json={"detail": "Missing bearer token"})

            token_str = auth_header.split("Bearer ", 1)[1]
            try:
                payload = jwt.decode(token_str, settings.jwt_secret, algorithms=["HS256"])
                caller_id = payload.get("sub")
                roles = payload.get("roles", [])
            except Exception:
                return httpx.Response(status_code=401, json={"detail": "Invalid token"})

            # Auth /api/auth/me introspection endpoint
            if "/api/auth/me" in url_str:
                return httpx.Response(
                    status_code=200,
                    json={
                        "id": caller_id,
                        "email": payload.get("email", "test@swiftletcare.vn"),
                        "full_name": "Test User",
                        "status": "ACTIVE",
                        "roles": roles,
                    },
                )

            # Farm Authorization /api/farms/{id}
            if "/api/farms/" in url_str:
                target_farm = url_str.split("/api/farms/")[-1].split("/")[0].split("?")[0]
                if "ADMIN" in roles:
                    return httpx.Response(status_code=200, json={"farm_id": target_farm, "owner_id": FARM_1_OWNER_ID})

                if caller_id == FARM_1_OWNER_ID:
                    if target_farm == FARM_1_ID:
                        return httpx.Response(status_code=200, json={"farm_id": FARM_1_ID, "owner_id": FARM_1_OWNER_ID})
                    return httpx.Response(status_code=403, json={"detail": "Forbidden: Farm not accessible to current user"})

                if caller_id == FARM_2_OWNER_ID:
                    if target_farm == FARM_2_ID:
                        return httpx.Response(status_code=200, json={"farm_id": FARM_2_ID, "owner_id": FARM_2_OWNER_ID})
                    return httpx.Response(status_code=403, json={"detail": "Forbidden: Farm not accessible to current user"})

                if caller_id == TECH_USER_ID:
                    # Technician assigned to Farm 1 only
                    if target_farm == FARM_1_ID:
                        return httpx.Response(status_code=200, json={"farm_id": FARM_1_ID, "assigned": True})
                    return httpx.Response(status_code=403, json={"detail": "Forbidden: Technician not assigned to farm"})

                return httpx.Response(status_code=403, json={"detail": "Forbidden"})

            # Fallback for /api/farms list (tenant-scoped)
            if url_str.rstrip("/").endswith("/api/farms"):
                all_farms = [
                    {"farm_id": FARM_1_ID, "owner_id": FARM_1_OWNER_ID},
                    {"farm_id": FARM_2_ID, "owner_id": FARM_2_OWNER_ID},
                ]
                if "ADMIN" in roles:
                    return httpx.Response(status_code=200, json=all_farms)
                if caller_id == FARM_1_OWNER_ID:
                    return httpx.Response(status_code=200, json=[all_farms[0]])
                if caller_id == FARM_2_OWNER_ID:
                    return httpx.Response(status_code=200, json=[all_farms[1]])
                if caller_id == TECH_USER_ID:
                    return httpx.Response(status_code=200, json=[all_farms[0]])
                return httpx.Response(status_code=200, json=[])

        # 2. Real Analytics Service Forwarding via HTTP socket to http://127.0.0.1:8005
        if "/api/v1/analytics" in url_str or "8005" in url_str:
            # Reconstruct request for live analytics service
            path_and_query = request.url.raw_path.decode("latin1")
            target_url = f"{LIVE_ANALYTICS_URL.rstrip('/')}{path_and_query}"
            forward_headers = dict(request.headers)
            forward_headers["host"] = "127.0.0.1:8005"
            content = await request.aread()

            upstream_req = real_http_client.build_request(
                method=request.method,
                url=target_url,
                headers=forward_headers,
                content=content if content else None,
            )
            return await real_http_client.send(upstream_req)

        return httpx.Response(status_code=404, json={"detail": "Not Found"})

    gateway_app = create_gateway_app()
    gateway_app.state.http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(gateway_upstream_router)
    )

    old_deployed = settings.analytics_service_deployed
    settings.analytics_service_deployed = True

    with TestClient(gateway_app) as client:
        yield client

    settings.analytics_service_deployed = old_deployed


def test_1_owner_accesses_own_farm_summary_live_postgres(live_e2e_client):
    """Farm Owner 1 queries own farm summary; verifies real PostgreSQL analytics_db data via Gateway."""
    token = make_jwt_token(user_id=FARM_1_OWNER_ID, roles=["FARM_OWNER"])
    resp = live_e2e_client.get(
        f"/api/v1/analytics/farms/{FARM_1_ID}/summary?period=today",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    # Verify authoritative data read from PostgreSQL dim_farms
    assert data["farmId"] == FARM_1_ID
    assert "Nhà yến Demo 01" in data["farmName"]
    assert data["period"] == "today"

    # Verify microclimate zones from PostgreSQL dim_zones
    assert len(data["microClimateScores"]) == 2
    zone_names = [z["name"] for z in data["microClimateScores"]]
    assert "Tầng 1" in zone_names
    assert "Tầng 2" in zone_names

    # Verify null safety (missing historical yield data is null, not 0)
    assert data["yieldSummary"] is None
    assert data["birdPerformance"]["returnRate"] is None


def test_2_owner_accesses_own_farm_trends_live_postgres(live_e2e_client):
    """Farm Owner 1 queries own farm trends with query parameters via Gateway."""
    token = make_jwt_token(user_id=FARM_1_OWNER_ID, roles=["FARM_OWNER"])
    resp = live_e2e_client.get(
        f"/api/v1/analytics/farms/{FARM_1_ID}/trends?period=today&metric=bird_entries",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["farmId"] == FARM_1_ID
    assert data["period"] == "today"
    assert "hourlyBirdActivity" in data
    assert "environmentComparison" in data


def test_3_cross_tenant_owner_blocked_from_other_farm(live_e2e_client):
    """Owner 1 attempting to view Farm 2 is authoritatively rejected with 403 Forbidden by Gateway."""
    token = make_jwt_token(user_id=FARM_1_OWNER_ID, roles=["FARM_OWNER"])
    resp = live_e2e_client.get(
        f"/api/v1/analytics/farms/{FARM_2_ID}/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert "Forbidden" in resp.json()["detail"]


def test_4_technician_scoped_access(live_e2e_client):
    """Technician permitted for assigned Farm 1, blocked for unassigned Farm 2 by Gateway."""
    tech_token = make_jwt_token(user_id=TECH_USER_ID, roles=["TECHNICIAN"])

    # Assigned Farm 1: 200 OK
    resp_ok = live_e2e_client.get(
        f"/api/v1/analytics/farms/{FARM_1_ID}/summary",
        headers={"Authorization": f"Bearer {tech_token}"},
    )
    assert resp_ok.status_code == 200
    assert "Nhà yến Demo 01" in resp_ok.json()["farmName"]

    # Unassigned Farm 2: 403 Forbidden
    resp_blocked = live_e2e_client.get(
        f"/api/v1/analytics/farms/{FARM_2_ID}/summary",
        headers={"Authorization": f"Bearer {tech_token}"},
    )
    assert resp_blocked.status_code == 403


def test_5_admin_accesses_global_trends_live_postgres(live_e2e_client):
    """Admin queries global system trends (/api/v1/analytics/trends) via Gateway."""
    admin_token = make_jwt_token(user_id=ADMIN_USER_ID, roles=["ADMIN"])
    resp = live_e2e_client.get(
        "/api/v1/analytics/trends?period=today",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["farmId"] is None
    assert data["farmName"] is None
    assert data["period"] == "today"


def test_6_non_admin_blocked_from_global_trends(live_e2e_client):
    """Non-admin callers (Farm Owner and Technician) are forbidden from global trends by Gateway."""
    owner_token = make_jwt_token(user_id=FARM_1_OWNER_ID, roles=["FARM_OWNER"])
    resp_owner = live_e2e_client.get(
        "/api/v1/analytics/trends",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp_owner.status_code == 403

    tech_token = make_jwt_token(user_id=TECH_USER_ID, roles=["TECHNICIAN"])
    resp_tech = live_e2e_client.get(
        "/api/v1/analytics/trends",
        headers={"Authorization": f"Bearer {tech_token}"},
    )
    assert resp_tech.status_code == 403


def test_7_jwt_missing_invalid_expired(live_e2e_client):
    """JWT authorization errors: missing, invalid, or expired tokens receive 401 from Gateway."""
    # 1. Missing Authorization header
    resp_missing = live_e2e_client.get(f"/api/v1/analytics/farms/{FARM_1_ID}/summary")
    assert resp_missing.status_code == 401

    # 2. Invalid / forged token
    resp_invalid = live_e2e_client.get(
        f"/api/v1/analytics/farms/{FARM_1_ID}/summary",
        headers={"Authorization": "Bearer forged-garbage-token-12345"},
    )
    assert resp_invalid.status_code == 401

    # 3. Expired token
    expired_token = make_jwt_token(
        user_id=FARM_1_OWNER_ID,
        roles=["FARM_OWNER"],
        expires_in_minutes=-10,
    )
    resp_expired = live_e2e_client.get(
        f"/api/v1/analytics/farms/{FARM_1_ID}/summary",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp_expired.status_code == 401


def test_8_service_unavailable_gate_and_connect_error():
    """Validates fail-closed deployment gate and upstream connect error."""
    admin_token = make_jwt_token(user_id=ADMIN_USER_ID, roles=["ADMIN"])
    headers = {"Authorization": f"Bearer {admin_token}"}

    async def mock_auth_only(request: httpx.Request):
        # Auth introspection passes
        if "/api/auth/me" in str(request.url):
            return httpx.Response(
                status_code=200,
                json={
                    "id": ADMIN_USER_ID,
                    "email": "admin@swiftletcare.vn",
                    "full_name": "Admin",
                    "status": "ACTIVE",
                    "roles": ["ADMIN"],
                },
            )
        # Analytics upstream connection error
        raise httpx.ConnectError("Connection refused", request=request)

    # Case 1: Deployment gate is False
    old_deployed = settings.analytics_service_deployed
    try:
        settings.analytics_service_deployed = False
        app = create_gateway_app()
        app.state.http_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_auth_only))
        with TestClient(app) as client:
            resp = client.get("/api/v1/analytics/trends", headers=headers)
            assert resp.status_code == 503
            assert "SERVICE_NOT_DEPLOYED" in resp.json()["detail"]
    finally:
        settings.analytics_service_deployed = old_deployed

    # Case 2: Deployment gate is True, but upstream is unreachable
    try:
        settings.analytics_service_deployed = True
        app = create_gateway_app()
        app.state.http_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_auth_only))
        with TestClient(app) as client:
            resp = client.get("/api/v1/analytics/trends", headers=headers)
            assert resp.status_code == 503
            assert "unreachable" in resp.json()["detail"].lower()
    finally:
        settings.analytics_service_deployed = old_deployed


def test_9_database_unavailable_error_handling(live_e2e_client):
    """
    Validates that when the analytics repository encounters a database connection error,
    it returns a controlled 503 DATABASE_UNAVAILABLE, forwarded cleanly by Gateway.
    """
    admin_token = make_jwt_token(user_id=ADMIN_USER_ID, roles=["ADMIN"])

    # Simulate upstream returning 503 DATABASE_UNAVAILABLE
    async def mock_db_down(request: httpx.Request):
        if "/api/auth/me" in str(request.url):
            return httpx.Response(status_code=200, json={"id": ADMIN_USER_ID, "status": "ACTIVE", "roles": ["ADMIN"]})
        if "/api/v1/analytics" in str(request.url):
            return httpx.Response(
                status_code=503,
                json={
                    "error": {
                        "code": "DATABASE_UNAVAILABLE",
                        "message": "Analytics database is temporarily unavailable. Please retry shortly.",
                    }
                },
            )
        return httpx.Response(status_code=404)

    app = create_gateway_app()
    app.state.http_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_db_down))
    old_deployed = settings.analytics_service_deployed
    try:
        settings.analytics_service_deployed = True
        with TestClient(app) as client:
            resp = client.get("/api/v1/analytics/trends", headers={"Authorization": f"Bearer {admin_token}"})
            assert resp.status_code == 503
            data = resp.json()
            assert data["error"]["code"] == "DATABASE_UNAVAILABLE"
    finally:
        settings.analytics_service_deployed = old_deployed


def test_10_invalid_query_parameter_returns_400(live_e2e_client):
    """Passing an invalid period parameter to live analytics returns 400 Bad Request with controlled error code."""
    token = make_jwt_token(user_id=FARM_1_OWNER_ID, roles=["FARM_OWNER"])
    resp = live_e2e_client.get(
        f"/api/v1/analytics/farms/{FARM_1_ID}/summary?period=invalid_era_century",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data["error"]["code"] == "INVALID_PERIOD"
