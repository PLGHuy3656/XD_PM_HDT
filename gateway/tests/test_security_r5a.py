"""Tests for CP11.3-R5-A: Gateway Security Configuration Hardening.

Covers:
1. Missing JWT_SECRET raises validation error / fails startup.
2. Invalid JWT_SECRET (empty, whitespace, <16 chars) fails validation without leaking secret in message.
3. Explicit valid JWT_SECRET loads successfully.
4. Missing ENVIRONMENT does not enable Analytics (default fail-closed).
5. Missing ANALYTICS_SERVICE_DEPLOYED leaves flag False.
6. Analytics disabled (False) returns 503 SERVICE_NOT_DEPLOYED.
7. Analytics enabled (True) forwards to upstream.
8. Zero upstream forwarding when Analytics is disabled.
9. Security / RBAC checks execute BEFORE deployment check (no information leakage).
"""
import os
import httpx
import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

from app.config import GatewaySettings, settings
from app.main import create_gateway_app
from tests.conftest import make_jwt_token

VALID_TEST_SECRET = "super-secret-key-at-least-32-chars-long"
SHORT_TEST_SECRET = "short-secret"
FARM_A_ID = "00000000-0000-0000-0000-00000000000a"
FARM_B_ID = "00000000-0000-0000-0000-00000000000b"
OWNER_A_ID = "11111111-1111-1111-1111-111111111111"
OWNER_B_ID = "22222222-2222-2222-2222-222222222222"
ADMIN_ID = "99999999-9999-9999-9999-999999999999"


# =============================================================================
# 1. JWT Secret Validation Tests (Fail-Fast & Non-Leaking)
# =============================================================================

def test_missing_jwt_secret_fails_validation(monkeypatch):
    """Missing JWT_SECRET must raise ValidationError and prevent Gateway startup."""
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ValidationError) as exc_info:
        GatewaySettings(_env_file=None)
    err_str = str(exc_info.value)
    assert "jwt_secret" in err_str.lower()


@pytest.mark.parametrize(
    "bad_secret,expected_msg",
    [
        ("", "must not be empty or blank"),
        ("   ", "must not be empty or blank"),
        ("short-key", "must be at least 16 characters long"),
        ("123456789012345", "must be at least 16 characters long"),  # 15 chars
    ],
)
def test_invalid_jwt_secret_fails_validation(monkeypatch, bad_secret, expected_msg):
    """Invalid JWT_SECRET (empty, whitespace, <16 chars) must fail validation without leaking secret in message."""
    monkeypatch.setenv("JWT_SECRET", bad_secret)
    with pytest.raises(ValidationError) as exc_info:
        GatewaySettings(_env_file=None)
    err_msg = exc_info.value.errors()[0]["msg"]
    assert expected_msg in err_msg
    # Verify that secret value itself is never leaked into our custom validation error message
    if bad_secret.strip():
        assert bad_secret not in err_msg


def test_valid_jwt_secret_passes_validation(monkeypatch):
    """Explicit valid JWT_SECRET (>= 16 characters) loads successfully."""
    monkeypatch.setenv("JWT_SECRET", VALID_TEST_SECRET)
    cfg = GatewaySettings(_env_file=None)
    assert cfg.jwt_secret == VALID_TEST_SECRET


def test_create_gateway_app_fails_fast_on_invalid_secret(monkeypatch):
    """create_gateway_app() raises RuntimeError if jwt_secret is somehow missing or invalid."""
    old_secret = settings.jwt_secret
    try:
        settings.jwt_secret = ""
        with pytest.raises(RuntimeError) as exc_info:
            create_gateway_app()
        assert "JWT_SECRET must be explicitly configured" in str(exc_info.value)
    finally:
        settings.jwt_secret = old_secret


# =============================================================================
# 2. Analytics Fail-Closed Deployment Flag Configuration Tests
# =============================================================================

def test_missing_environment_leaves_analytics_disabled(monkeypatch):
    """Missing or non-existent ENVIRONMENT does not enable Analytics (default fail-closed)."""
    monkeypatch.setenv("JWT_SECRET", VALID_TEST_SECRET)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("ANALYTICS_SERVICE_DEPLOYED", raising=False)
    cfg = GatewaySettings(_env_file=None)
    assert cfg.analytics_service_deployed is False


def test_missing_analytics_deployment_flag_defaults_to_false(monkeypatch):
    """When ANALYTICS_SERVICE_DEPLOYED is omitted, it defaults to False."""
    monkeypatch.setenv("JWT_SECRET", VALID_TEST_SECRET)
    monkeypatch.delenv("ANALYTICS_SERVICE_DEPLOYED", raising=False)
    cfg = GatewaySettings(_env_file=None)
    assert cfg.analytics_service_deployed is False


def test_explicit_analytics_deployment_flag_enabled(monkeypatch):
    """Explicitly setting ANALYTICS_SERVICE_DEPLOYED=true enables the flag."""
    monkeypatch.setenv("JWT_SECRET", VALID_TEST_SECRET)
    monkeypatch.setenv("ANALYTICS_SERVICE_DEPLOYED", "true")
    cfg = GatewaySettings(_env_file=None)
    assert cfg.analytics_service_deployed is True


# =============================================================================
# 3. Analytics Proxy Fail-Closed Runtime Behavior & Zero-Hit Tests
# =============================================================================

@pytest.fixture
def analytics_test_client():
    """Builds a test client with a mock upstream to record forwarded requests."""
    upstream_hits = []

    def mock_backend(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        upstream_hits.append(request)

        auth_hdr = request.headers.get("authorization", "")

        # Mock Management auth introspection
        if "/api/auth/me" in url_str:
            user_id = OWNER_A_ID
            roles = ["FARM_OWNER"]
            auth_hdr = request.headers.get("authorization", "")
            if auth_hdr.startswith("Bearer "):
                token_val = auth_hdr.split(" ", 1)[1]
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

        # Mock Farm access resolution (Management Service)
        if f"/api/farms/{FARM_A_ID}" in url_str:
            return httpx.Response(
                status_code=200,
                json={"id": FARM_A_ID, "owner_id": OWNER_A_ID, "name": "Farm Alpha"},
            )
        if f"/api/farms/{FARM_B_ID}" in url_str:
            # Owner A is accessing Farm B -> Management returns 403 Forbidden
            return httpx.Response(
                status_code=403,
                json={"detail": "Forbidden: Farm not accessible to current user"},
            )

        # Analytics responses
        if "/api/v1/analytics" in url_str:
            return httpx.Response(status_code=200, json={"analytics": "ok"})

        return httpx.Response(status_code=200, json={"status": "ok"})

    app_instance = create_gateway_app()
    app_instance.state.http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(mock_backend)
    )

    with TestClient(app_instance) as client:
        yield client, upstream_hits


def test_analytics_disabled_returns_503_and_zero_upstream_hits(analytics_test_client):
    """When analytics_service_deployed=False, all analytics routes return 503 and zero upstream hits."""
    client, hits = analytics_test_client
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    token_admin = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    old_deployed = settings.analytics_service_deployed
    try:
        settings.analytics_service_deployed = False

        # 1. Farm summary
        resp1 = client.get(f"/api/v1/analytics/farms/{FARM_A_ID}/summary", headers=headers_a)
        assert resp1.status_code == 503
        assert resp1.json()["detail"] == "SERVICE_NOT_DEPLOYED: Analytics Service is not yet deployed"

        # 2. Farm trends
        resp2 = client.get(f"/api/v1/analytics/farms/{FARM_A_ID}/trends", headers=headers_a)
        assert resp2.status_code == 503
        assert resp2.json()["detail"] == "SERVICE_NOT_DEPLOYED: Analytics Service is not yet deployed"

        # 3. Global trends (Admin)
        resp3 = client.get("/api/v1/analytics/trends", headers=headers_admin)
        assert resp3.status_code == 503
        assert resp3.json()["detail"] == "SERVICE_NOT_DEPLOYED: Analytics Service is not yet deployed"

        # Verify ZERO upstream analytics requests reached the backend
        analytics_forwarded = [h for h in hits if "/api/v1/analytics" in str(h.url)]
        assert len(analytics_forwarded) == 0

    finally:
        settings.analytics_service_deployed = old_deployed


def test_analytics_enabled_forwards_to_upstream(analytics_test_client):
    """When analytics_service_deployed=True, analytics routes forward to upstream."""
    client, hits = analytics_test_client
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    headers_a = {"Authorization": f"Bearer {token_a}"}

    old_deployed = settings.analytics_service_deployed
    try:
        settings.analytics_service_deployed = True

        resp = client.get(f"/api/v1/analytics/farms/{FARM_A_ID}/summary", headers=headers_a)
        assert resp.status_code == 200
        assert resp.json() == {"analytics": "ok"}

        analytics_forwarded = [h for h in hits if "/api/v1/analytics" in str(h.url)]
        assert len(analytics_forwarded) == 1
    finally:
        settings.analytics_service_deployed = old_deployed


# =============================================================================
# 4. Security Priority Tests (Auth & RBAC Before Deployment Check)
# =============================================================================

def test_unauthenticated_request_fails_before_deployment_check(analytics_test_client):
    """Unauthenticated request must receive 401, NOT 503 (no deployment state discovery)."""
    client, hits = analytics_test_client

    old_deployed = settings.analytics_service_deployed
    try:
        settings.analytics_service_deployed = False

        # No Authorization header on farm summary
        resp = client.get(f"/api/v1/analytics/farms/{FARM_A_ID}/summary")
        assert resp.status_code == 401

        # Global trends without auth
        resp_global = client.get("/api/v1/analytics/trends")
        assert resp_global.status_code == 401

        # Zero analytics hits
        analytics_forwarded = [h for h in hits if "/api/v1/analytics" in str(h.url)]
        assert len(analytics_forwarded) == 0
    finally:
        settings.analytics_service_deployed = old_deployed


def test_cross_tenant_access_fails_before_deployment_check(analytics_test_client):
    """Cross-farm access (Owner A calling Farm B) must receive 403, NOT 503."""
    client, hits = analytics_test_client
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    headers_a = {"Authorization": f"Bearer {token_a}"}

    old_deployed = settings.analytics_service_deployed
    try:
        settings.analytics_service_deployed = False

        # Owner A attempts to access Farm B analytics
        resp = client.get(f"/api/v1/analytics/farms/{FARM_B_ID}/summary", headers=headers_a)
        assert resp.status_code == 403
        assert "Forbidden" in resp.json()["detail"] or "authorized" in resp.json()["detail"]

        # Ensure no analytics forwarding occurred
        analytics_forwarded = [h for h in hits if "/api/v1/analytics" in str(h.url)]
        assert len(analytics_forwarded) == 0
    finally:
        settings.analytics_service_deployed = old_deployed


def test_non_admin_global_trends_fails_before_deployment_check(analytics_test_client):
    """Non-admin caller accessing global analytics trends must receive 403, NOT 503."""
    client, hits = analytics_test_client
    token_a = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    headers_a = {"Authorization": f"Bearer {token_a}"}

    old_deployed = settings.analytics_service_deployed
    try:
        settings.analytics_service_deployed = False

        # Non-admin attempts global trends
        resp = client.get("/api/v1/analytics/trends", headers=headers_a)
        assert resp.status_code == 403
        assert "ADMIN" in resp.json()["detail"]

        # Ensure no analytics forwarding occurred
        analytics_forwarded = [h for h in hits if "/api/v1/analytics" in str(h.url)]
        assert len(analytics_forwarded) == 0
    finally:
        settings.analytics_service_deployed = old_deployed
