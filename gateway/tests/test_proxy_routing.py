"""Unit & regression tests for reverse proxy routing, header forwarding, security guards,

B1 path traversal, ambiguous delimiters (%3f, %23), B2 gzip preservation, and B3 multi-cookie/hop-by-hop handling.
"""
import gzip
import httpx
import jwt
import pytest
from starlette.testclient import TestClient

from app.config import settings
from app.main import create_gateway_app
from tests.conftest import make_jwt_token


@pytest.fixture
def auth_headers():
    token = make_jwt_token(roles=["ADMIN"], email="admin@swiftletcare.vn")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def proxy_test_setup():
    """Sets up a test gateway app with a mock transport to capture upstream requests."""
    recorded_requests = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)

        # Timeout simulation
        if "simulate-timeout" in str(request.url):
            raise httpx.ReadTimeout("Mock read timeout", request=request)

        # Connect error simulation
        if "simulate-down" in str(request.url):
            raise httpx.ConnectError("Mock connection refused", request=request)

        # Management Auth Introspection (GET /api/auth/me)
        if "/api/auth/me" in str(request.url):
            auth_val = request.headers.get("authorization", "")
            token_str = auth_val.split("Bearer ")[-1].strip() if "Bearer " in auth_val else ""
            try:
                p = jwt.decode(token_str, settings.jwt_secret, algorithms=["HS256"])
                return httpx.Response(
                    status_code=200,
                    headers={"Content-Type": "application/json"},
                    json={
                        "id": p.get("sub", "00000000-0000-0000-0000-000000000001"),
                        "email": p.get("email", "admin@swiftletcare.vn"),
                        "full_name": "Mock Admin User",
                        "status": "ACTIVE",
                        "roles": p.get("roles", ["ADMIN"]),
                    },
                )
            except Exception:
                return httpx.Response(
                    status_code=401,
                    headers={"Content-Type": "application/json"},
                    json={"detail": "Invalid or expired token"},
                )

        # Gzip simulation endpoint (B2)
        if "test-gzip-endpoint" in str(request.url):
            raw_text = b'{"status": "ok", "message": "swiftletcare-compressed-data"}' * 15
            compressed = gzip.compress(raw_text)
            return httpx.Response(
                status_code=200,
                headers=[
                    (b"content-type", b"application/json"),
                    (b"content-encoding", b"gzip"),
                    (b"content-length", str(len(compressed)).encode("ascii")),
                ],
                stream=httpx.ByteStream(compressed),
            )

        # Multi-cookie simulation endpoint (B3)
        if "test-multi-cookie" in str(request.url):
            return httpx.Response(
                status_code=200,
                headers=[
                    (b"content-type", b"application/json"),
                    (b"set-cookie", b"session_id=swc_sess_12345; Path=/; HttpOnly"),
                    (b"set-cookie", b"csrf_token=swc_csrf_67890; Path=/; SameSite=Lax"),
                    (b"x-preserved", b"custom-value"),
                ],
                json={"cookies": "set"},
            )

        # Hop-by-hop simulation endpoint (B3)
        if "test-hop-by-hop" in str(request.url):
            return httpx.Response(
                status_code=200,
                headers=[
                    (b"content-type", b"application/json"),
                    (b"connection", b"close, X-Dynamic-Hop"),
                    (b"x-dynamic-hop", b"secret-token-do-not-forward"),
                    (b"keep-alive", b"timeout=5"),
                    (b"x-standard-kept", b"kept-value"),
                ],
                json={"hop": "tested"},
            )

        # Standard echo response
        return httpx.Response(
            status_code=200,
            headers={"Content-Type": "application/json", "X-Upstream-Server": "mock-backend"},
            json={
                "echo_url": str(request.url),
                "echo_method": request.method,
                "echo_headers": dict(request.headers),
                "echo_body": request.read().decode("utf-8", errors="ignore"),
            },
        )

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    test_app = create_gateway_app()
    test_app.state.http_client = mock_client

    with TestClient(test_app) as client:
        yield client, recorded_requests


# =============================================================================
# Standard Route Forwarding Tests
# =============================================================================
def test_routes_management_auth_login(proxy_test_setup):
    client, recorded = proxy_test_setup
    payload = {"username": "admin@swiftletcare.vn", "password": "securePassword123"}
    response = client.post("/api/auth/login", json=payload)

    assert response.status_code == 200
    assert len(recorded) == 1
    req = recorded[0]
    assert req.method == "POST"
    assert "/api/auth/login" in str(req.url)
    assert req.headers.get("X-Correlation-ID") is not None


def test_routes_management_farms(proxy_test_setup, auth_headers):
    client, recorded = proxy_test_setup
    response = client.get("/api/farms?active=true", headers=auth_headers)

    assert response.status_code == 200
    # 2 requests: 1 introspection /api/auth/me + 1 forward /api/farms
    farm_reqs = [r for r in recorded if "/api/farms" in str(r.url)]
    assert len(farm_reqs) == 1
    req = farm_reqs[0]
    assert req.method == "GET"
    assert "active=true" in str(req.url)
    assert "Bearer" in req.headers.get("Authorization", "")


def test_routes_iot_telemetry_latest(proxy_test_setup, auth_headers):
    client, recorded = proxy_test_setup
    response = client.get("/api/iot/devices/SWC-DEVICE-01/telemetry/latest", headers=auth_headers)

    assert response.status_code == 200
    iot_reqs = [r for r in recorded if "/api/iot/devices/SWC-DEVICE-01/telemetry/latest" in str(r.url)]
    assert len(iot_reqs) == 1
    req = iot_reqs[0]
    assert req.method == "GET"


def test_routes_iot_command_relay(proxy_test_setup, auth_headers):
    client, recorded = proxy_test_setup
    body = {"target": "RELAY_HUMIDIFIER", "state": "ON"}
    response = client.post("/api/iot/devices/SWC-DEVICE-01/commands/relay", json=body, headers=auth_headers)

    assert response.status_code == 200
    cmd_reqs = [r for r in recorded if "/api/iot/devices/SWC-DEVICE-01/commands/relay" in str(r.url)]
    assert len(cmd_reqs) == 1
    req = cmd_reqs[0]
    assert req.method == "POST"


def test_routes_ai_cameras(proxy_test_setup, auth_headers):
    client, recorded = proxy_test_setup
    response = client.get("/api/v1/ai/cameras", headers=auth_headers)

    assert response.status_code == 200
    ai_reqs = [r for r in recorded if "/api/v1/ai/cameras" in str(r.url)]
    assert len(ai_reqs) == 1
    req = ai_reqs[0]
    assert req.method == "GET"


def test_routes_notification_alerts(proxy_test_setup, auth_headers):
    client, recorded = proxy_test_setup
    response = client.get("/api/v1/alerts", headers=auth_headers)

    assert response.status_code == 200
    alert_reqs = [r for r in recorded if "/api/v1/alerts" in str(r.url)]
    assert len(alert_reqs) == 1
    req = alert_reqs[0]
    assert req.method == "GET"


def test_routes_analytics_target(proxy_test_setup, auth_headers):
    client, recorded = proxy_test_setup
    old_deployed = settings.analytics_service_deployed
    try:
        settings.analytics_service_deployed = True
        response = client.get("/api/v1/analytics/trends", headers=auth_headers)

        assert response.status_code == 200
        analytics_reqs = [r for r in recorded if "/api/v1/analytics/trends" in str(r.url)]
        assert len(analytics_reqs) == 1
        req = analytics_reqs[0]
        assert req.method == "GET"
    finally:
        settings.analytics_service_deployed = old_deployed


# =============================================================================
# B1 Regression Tests: Path Traversal, Encoded Delimiters, & Prefix Boundary
# =============================================================================
@pytest.mark.parametrize(
    "dangerous_path",
    [
        "/api/auth/..%2f..%2finternal/runtime/run",
        "/api/v1/ai/%2e%2e/internal/v1/runtime/run",
        "/api/v1/ai/%2e%2e%2finternal",
        "/api/v1/ai/..%5c..%5cinternal",
        "/api/auth/%252e%252e/internal",
        "/api/farms//internal",
        "/api/farms/..;internal",
        "/api/farms/%00internal",
        "/api/farms/..%2F..%2Finternal",
        "/api/farms/..",
        "/api/farms/../something",
        "/api/farms/farm1\\test",
        # Phase A: Ambiguous delimiter payloads (%3f, %23)
        "/api/farms%3f/internal",
        "/api/farms%23/internal",
        "/api/farms%3fparam=1",
        "/api/farms%23section",
        "/api/auth/login%3fparam=1",
        "/api/auth/login%23hash",
    ],
)
def test_b1_rejects_dangerous_path_encodings_and_traversal(proxy_test_setup, dangerous_path, auth_headers):
    client, recorded = proxy_test_setup
    response = client.get(dangerous_path, headers=auth_headers)

    # Must reject with 400 Bad Request or 403 Forbidden
    assert response.status_code in (400, 403, 404), f"Failed for {dangerous_path}: got {response.status_code}"
    # Critical: No upstream service request should ever be made
    upstream_target_reqs = [r for r in recorded if not str(r.url).endswith("/api/auth/me")]
    assert len(upstream_target_reqs) == 0


@pytest.mark.parametrize(
    "internal_path",
    [
        "/api/v1/ai/internal/v1/runtime/run",
        "/api/v1/alerts/internal/ai",
        "/api/auth/internal/reset-all",
        "/api/iot/internal/restart",
    ],
)
def test_b1_blocks_internal_endpoints_with_forbidden(proxy_test_setup, internal_path, auth_headers):
    client, recorded = proxy_test_setup
    response = client.post(internal_path, json={"trigger": True}, headers=auth_headers)

    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]
    upstream_target_reqs = [r for r in recorded if not str(r.url).endswith("/api/auth/me")]
    assert len(upstream_target_reqs) == 0


# =============================================================================
# B2 Regression Tests: Gzip Streaming Preservation
# =============================================================================
def test_b2_gzip_streaming_preserves_content_encoding_and_raw_bytes(proxy_test_setup, auth_headers):
    client, recorded = proxy_test_setup
    response = client.get("/api/farms/test-gzip-endpoint", headers=auth_headers)

    assert response.status_code == 200
    assert response.headers.get("content-encoding") == "gzip"

    expected_chunk = b'{"status": "ok", "message": "swiftletcare-compressed-data"}'
    assert expected_chunk in response.content


# =============================================================================
# B3 Regression Tests: Multi-Valued Headers & Hop-by-Hop Filtering
# =============================================================================
def test_b3_preserves_multiple_set_cookie_headers(proxy_test_setup, auth_headers):
    client, recorded = proxy_test_setup
    response = client.get("/api/farms/test-multi-cookie", headers=auth_headers)

    assert response.status_code == 200
    # Must preserve multiple distinct Set-Cookie headers
    cookies = response.headers.get_list("set-cookie")
    assert len(cookies) == 2
    assert any("session_id=swc_sess_12345" in c for c in cookies)
    assert any("csrf_token=swc_csrf_67890" in c for c in cookies)
    assert response.headers.get("x-preserved") == "custom-value"


def test_b3_strips_standard_and_dynamic_connection_hop_by_hop_headers(proxy_test_setup, auth_headers):
    client, recorded = proxy_test_setup
    headers = {
        **auth_headers,
        "Connection": "close, X-Client-Private",
        "X-Client-Private": "do-not-leak",
        "Keep-Alive": "timeout=10",
        "X-Regular-Header": "regular-data",
    }
    response = client.get("/api/farms/test-hop-by-hop", headers=headers)

    assert response.status_code == 200
    # Verify upstream received request with hop-by-hop headers stripped
    farm_reqs = [r for r in recorded if "test-hop-by-hop" in str(r.url)]
    assert len(farm_reqs) == 1
    req = farm_reqs[0]
    assert "x-client-private" not in req.headers
    assert "keep-alive" not in req.headers
    assert req.headers.get("x-regular-header") == "regular-data"

    # Verify response to client has response hop-by-hop headers stripped
    assert "x-dynamic-hop" not in response.headers
    assert "connection" not in response.headers
    assert "keep-alive" not in response.headers
    assert response.headers.get("x-standard-kept") == "kept-value"


# =============================================================================
# Error Normalization Tests
# =============================================================================
def test_upstream_connection_failure_returns_503(proxy_test_setup, auth_headers):
    client, _ = proxy_test_setup
    response = client.get("/api/farms/simulate-down", headers=auth_headers)

    assert response.status_code == 503
    data = response.json()
    assert "Service Unavailable" in data["detail"]
    assert response.headers.get("X-Correlation-ID") is not None


def test_upstream_timeout_returns_504(proxy_test_setup, auth_headers):
    client, _ = proxy_test_setup
    response = client.get("/api/farms/simulate-timeout", headers=auth_headers)

    assert response.status_code == 504
    data = response.json()
    assert "Gateway Timeout" in data["detail"]
    assert response.headers.get("X-Correlation-ID") is not None
