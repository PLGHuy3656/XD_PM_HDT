"""Tests for JWT Authentication, Management Introspection, Header Sanitization,

and Role-Based Access Control (RBAC) (CP11.3).
"""
import httpx
import jwt
import pytest
from starlette.testclient import TestClient

from app.config import settings
from app.main import create_gateway_app
from tests.conftest import make_jwt_token


@pytest.fixture
def auth_mock_env():
    """Provides a gateway TestClient backed by a mock upstream with configurable auth responses."""
    recorded_requests = []
    config = {
        "user_status": "ACTIVE",
        "management_available": True,
        "introspection_status_code": 200,
    }

    def mock_handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)

        # 1. Management Introspection Endpoint (/api/auth/me)
        if "/api/auth/me" in str(request.url):
            if not config["management_available"]:
                raise httpx.ConnectError("Management service down", request=request)

            if config["introspection_status_code"] != 200:
                return httpx.Response(
                    status_code=config["introspection_status_code"],
                    headers={"Content-Type": "application/json"},
                    json={"detail": "Introspection failed or account inactive"},
                )

            auth_val = request.headers.get("authorization", "")
            token_str = auth_val.split("Bearer ")[-1].strip() if "Bearer " in auth_val else ""
            try:
                p = jwt.decode(token_str, settings.jwt_secret, algorithms=["HS256"])
                return httpx.Response(
                    status_code=200,
                    headers={"Content-Type": "application/json"},
                    json={
                        "id": p.get("sub", "00000000-0000-0000-0000-000000000001"),
                        "email": p.get("email", "user@swiftletcare.vn"),
                        "full_name": "Test User",
                        "status": config["user_status"],
                        "roles": p.get("roles", ["ADMIN"]),
                    },
                )
            except Exception:
                return httpx.Response(
                    status_code=401,
                    headers={"Content-Type": "application/json"},
                    json={"detail": "Invalid token in introspection"},
                )

        # 2. Public Login
        if "/api/auth/login" in str(request.url):
            return httpx.Response(
                status_code=200,
                headers={"Content-Type": "application/json"},
                json={
                    "access_token": make_jwt_token(roles=["ADMIN"]),
                    "token_type": "bearer",
                    "expires_in": 3600,
                },
            )

        # 3. General upstream echo
        return httpx.Response(
            status_code=200,
            headers={"Content-Type": "application/json"},
            json={
                "url": str(request.url),
                "headers": dict(request.headers),
                "user_id": request.headers.get("x-user-id"),
                "roles": request.headers.get("x-user-roles"),
            },
        )

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    test_app = create_gateway_app()
    test_app.state.http_client = mock_client

    with TestClient(test_app) as client:
        yield {
            "client": client,
            "recorded": recorded_requests,
            "config": config,
        }


# =============================================================================
# 1. Public Endpoints
# =============================================================================
def test_public_login_allowed_without_token(auth_mock_env):
    client = auth_mock_env["client"]
    recorded = auth_mock_env["recorded"]

    payload = {"email": "user@swiftletcare.vn", "password": "securepassword"}
    resp = client.post("/api/auth/login", json=payload)

    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert len(recorded) == 1
    assert "/api/auth/login" in str(recorded[0].url)


def test_public_health_allowed_without_token(auth_mock_env):
    client = auth_mock_env["client"]
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# =============================================================================
# 2. Missing & Invalid Tokens (401)
# =============================================================================
@pytest.mark.parametrize(
    "protected_url",
    [
        "/api/farms",
        "/api/devices?farm_id=farm-01",
        "/api/zones/zone-1",
        "/api/iot/devices/SWC-01/telemetry/latest",
        "/api/v1/ai/cameras",
        "/api/v1/alerts",
        "/api/v1/notifications",
        "/api/v1/analytics/trends",
    ],
)
def test_missing_token_returns_401(auth_mock_env, protected_url):
    client = auth_mock_env["client"]
    recorded = auth_mock_env["recorded"]

    resp = client.get(protected_url)
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers
    assert "Authentication required" in resp.json()["detail"]
    assert len(recorded) == 0


def test_invalid_signature_returns_401(auth_mock_env):
    client = auth_mock_env["client"]
    bad_token = make_jwt_token(secret="completely-wrong-secret-key-32bytes-length!")

    resp = client.get("/api/farms", headers={"Authorization": f"Bearer {bad_token}"})
    assert resp.status_code == 401
    assert "Invalid token signature" in resp.json()["detail"]


def test_expired_token_returns_401(auth_mock_env):
    client = auth_mock_env["client"]
    expired_token = make_jwt_token(expires_in_minutes=-10)

    resp = client.get("/api/farms", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
    assert "Authentication token has expired" in resp.json()["detail"]


def test_malformed_token_header_returns_401(auth_mock_env):
    client = auth_mock_env["client"]

    # Not Bearer
    resp = client.get("/api/farms", headers={"Authorization": "Basic 123456"})
    assert resp.status_code == 401

    # Empty token
    resp = client.get("/api/farms", headers={"Authorization": "Bearer "})
    assert resp.status_code == 401


# =============================================================================
# 3. Active Account Verification & Fail Closed
# =============================================================================
def test_inactive_user_returns_401(auth_mock_env):
    client = auth_mock_env["client"]
    auth_mock_env["config"]["user_status"] = "INACTIVE"
    token = make_jwt_token(roles=["ADMIN"])

    resp = client.get("/api/farms", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert "not active" in resp.json()["detail"].lower()


def test_management_introspection_unavailable_fails_closed(auth_mock_env):
    client = auth_mock_env["client"]
    auth_mock_env["config"]["management_available"] = False
    token = make_jwt_token(roles=["ADMIN"])

    resp = client.get("/api/farms", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 503
    assert "unreachable" in resp.json()["detail"].lower()


# =============================================================================
# 4. RBAC Role Restrictions (403 vs 200)
# =============================================================================
def test_technician_assignment_requires_admin(auth_mock_env):
    client = auth_mock_env["client"]
    tech_id = "11111111-1111-1111-1111-111111111111"
    farm_id = "33333333-3333-3333-3333-333333333333"
    assign_url = f"/api/technicians/{tech_id}/farms/{farm_id}/assign"

    # 1. Non-admin (TECHNICIAN) -> 403 Forbidden
    tech_token = make_jwt_token(user_id=tech_id, roles=["TECHNICIAN"])
    resp = client.post(assign_url, headers={"Authorization": f"Bearer {tech_token}"})
    assert resp.status_code == 403
    assert "Forbidden" in resp.json()["detail"]

    # 2. Non-admin (FARM_OWNER) -> 403 Forbidden
    owner_token = make_jwt_token(user_id="22222222-2222-2222-2222-222222222222", roles=["FARM_OWNER"])
    resp = client.post(assign_url, headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 403

    # 3. ADMIN -> 200 OK
    admin_token = make_jwt_token(roles=["ADMIN"])
    resp = client.post(assign_url, headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200


def test_technicians_list_forbidden_for_farm_owner(auth_mock_env):
    client = auth_mock_env["client"]

    # Farm owner cannot list all technicians
    owner_token = make_jwt_token(roles=["FARM_OWNER"])
    resp = client.get("/api/technicians", headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 403

    # Technician can list technicians
    tech_token = make_jwt_token(roles=["TECHNICIAN"])
    resp = client.get("/api/technicians", headers={"Authorization": f"Bearer {tech_token}"})
    assert resp.status_code == 200


def test_technician_cannot_access_other_technician_profile(auth_mock_env):
    client = auth_mock_env["client"]
    my_tech_id = "11111111-1111-1111-1111-111111111111"
    other_tech_id = "99999999-9999-9999-9999-999999999999"

    my_token = make_jwt_token(user_id=my_tech_id, roles=["TECHNICIAN"])

    # 1. Access other technician -> 403
    resp = client.get(f"/api/technicians/{other_tech_id}", headers={"Authorization": f"Bearer {my_token}"})
    assert resp.status_code == 403
    assert "Cannot access another technician" in resp.json()["detail"]

    # 2. Access self -> 200
    resp = client.get(f"/api/technicians/{my_tech_id}", headers={"Authorization": f"Bearer {my_token}"})
    assert resp.status_code == 200

    # 3. Admin access other technician -> 200
    admin_token = make_jwt_token(roles=["ADMIN"])
    resp = client.get(f"/api/technicians/{other_tech_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200


# =============================================================================
# 5. Cross-Tenant Farm Isolation Protection
# =============================================================================
def test_cross_tenant_device_listing_without_farm_id_rejected_for_non_admin(auth_mock_env):
    client = auth_mock_env["client"]

    owner_token = make_jwt_token(roles=["FARM_OWNER"])

    # 1. Non-admin calls GET /api/devices without farm_id -> Fail closed with 403
    resp = client.get("/api/devices", headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 403
    assert "farm_id" in resp.json()["detail"]

    # 2. Non-admin provides farm_id -> 200 OK (passed to upstream for resource verification)
    resp = client.get("/api/devices?farm_id=farm-uuid-123", headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 200

    # 3. Admin calls GET /api/devices without farm_id -> 200 OK
    admin_token = make_jwt_token(roles=["ADMIN"])
    resp = client.get("/api/devices", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200


# =============================================================================
# 6. Identity Header Sanitization & Spoofing Prevention
# =============================================================================
def test_forged_identity_headers_stripped_and_sanitized(auth_mock_env):
    client = auth_mock_env["client"]
    recorded = auth_mock_env["recorded"]

    tech_id = "11111111-1111-1111-1111-111111111111"
    token = make_jwt_token(user_id=tech_id, roles=["TECHNICIAN"], email="tech@swiftletcare.vn")

    # Attacker tries to spoof ADMIN identity via custom headers
    spoofed_headers = {
        "Authorization": f"Bearer {token}",
        "X-User-Id": "forged-admin-uuid",
        "X-User-Roles": "ADMIN",
        "X-User-Email": "hacker@evil.com",
        "X-Internal-Secret": "leaked-internal-token",
        "X-Service-Name": "gateway-bypass",
        "X-Forwarded-For": "10.0.0.1",
    }

    resp = client.get("/api/farms", headers=spoofed_headers)
    assert resp.status_code == 200

    # Find the forwarded request to upstream /api/farms
    farm_reqs = [r for r in recorded if "/api/farms" in str(r.url)]
    assert len(farm_reqs) == 1
    upstream_req = farm_reqs[0]

    # Verify spoofed headers were stripped
    assert upstream_req.headers.get("x-user-id") == tech_id
    assert upstream_req.headers.get("x-user-roles") == "TECHNICIAN"
    assert upstream_req.headers.get("x-user-email") == "tech@swiftletcare.vn"
    assert "x-internal-secret" not in upstream_req.headers
    assert "x-service-name" not in upstream_req.headers
    assert upstream_req.headers.get("x-forwarded-for") != "10.0.0.1"


# =============================================================================
# 7. Path Ambiguity Regression (%3f, %23)
# =============================================================================
@pytest.mark.parametrize(
    "ambiguous_url",
    [
        "/api/farms%3f/internal",
        "/api/farms%23/internal",
        "/api/farms%3fparam=1",
        "/api/farms%23section",
    ],
)
def test_path_ambiguity_percent3f_and_percent23_rejected(auth_mock_env, ambiguous_url):
    client = auth_mock_env["client"]
    recorded = auth_mock_env["recorded"]
    token = make_jwt_token(roles=["ADMIN"])

    resp = client.get(ambiguous_url, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400
    assert "ambiguous path delimiters" in resp.json()["detail"].lower()
    upstream_reqs = [r for r in recorded if not str(r.url).endswith("/api/auth/me")]
    assert len(upstream_reqs) == 0
