"""Real TCP socket integration tests for API Gateway (CP11.2 & CP11.3).

Spins up a fake upstream service and the API Gateway on real OS TCP sockets via uvicorn.
Verifies wire-level behavior:
- B1: Path traversal / encoded path rejection & internal blocking over real sockets.
- B2: Gzip streaming wire preservation (raw compressed bytes over TCP socket).
- B3: Multi-valued Set-Cookie header preservation and RFC 7230 hop-by-hop stripping.
- CP11.3: Real socket JWT authentication, Management /api/auth/me introspection, and RBAC enforcement.
"""
import gzip
import json
import socket
import threading
import time
from typing import AsyncIterator, List, Tuple
import httpx
import jwt
import pytest
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from app.config import settings
from app.main import create_gateway_app
from tests.conftest import make_jwt_token


def get_free_port() -> int:
    """Finds an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class UvicornTestServer(uvicorn.Server):
    """Subclass of Uvicorn Server disabling default OS signal handlers for clean threading."""

    def install_signal_handlers(self) -> None:
        pass


@pytest.fixture(scope="module")
def socket_servers():
    """Starts fake upstream server and gateway server on separate real TCP ports."""
    upstream_port = get_free_port()
    gateway_port = get_free_port()

    # Track hits on internal endpoints to ensure they are never reached
    upstream_hits = {"internal": 0, "normal": 0, "last_user_id_forwarded": None}

    # 1. Fake upstream endpoints
    async def handle_auth_login(request: Request) -> Response:
        upstream_hits["normal"] += 1
        admin_tok = make_jwt_token(roles=["ADMIN"], email="admin@swiftletcare.vn")
        return JSONResponse({"access_token": admin_tok, "token_type": "bearer", "expires_in": 3600})

    async def handle_auth_me(request: Request) -> Response:
        upstream_hits["normal"] += 1
        auth_header = request.headers.get("authorization", "")
        token = auth_header.split("Bearer ")[-1].strip() if "Bearer " in auth_header else ""
        try:
            p = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
            user_id = p.get("sub", "00000000-0000-0000-0000-000000000001")
            roles = p.get("roles", ["ADMIN"])
            email = p.get("email", "test@swiftletcare.vn")
            return JSONResponse({
                "id": user_id,
                "email": email,
                "full_name": "Socket Introspected User",
                "status": "ACTIVE",
                "roles": roles,
            })
        except Exception:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

    async def handle_gzip_data(request: Request) -> Response:
        upstream_hits["normal"] += 1
        raw_dict = {"status": "ok", "message": "swiftletcare-compressed-data", "items": list(range(100))}
        raw_bytes = json.dumps(raw_dict).encode("utf-8")
        compressed_bytes = gzip.compress(raw_bytes)

        async def _stream():
            yield compressed_bytes

        resp = StreamingResponse(_stream(), status_code=200, media_type="application/json")
        resp.raw_headers = [
            (b"content-type", b"application/json"),
            (b"content-encoding", b"gzip"),
            (b"content-length", str(len(compressed_bytes)).encode("ascii")),
            (b"x-upstream-origin", b"fake-upstream"),
        ]
        return resp

    async def handle_multi_cookie(request: Request) -> Response:
        upstream_hits["normal"] += 1
        resp = JSONResponse({"cookies": "set"})
        resp.raw_headers = [
            (b"content-type", b"application/json"),
            (b"set-cookie", b"session_id=swc_sock_12345; Path=/; HttpOnly; SameSite=Lax"),
            (b"set-cookie", b"csrf_token=swc_csrf_67890; Path=/; Secure"),
            (b"x-custom-preserved", b"custom-header-value"),
        ]
        return resp

    async def handle_hop_by_hop(request: Request) -> Response:
        upstream_hits["normal"] += 1
        resp = JSONResponse({"hop": "filtered"})
        resp.raw_headers = [
            (b"content-type", b"application/json"),
            (b"connection", b"close, X-Dynamic-Hop"),
            (b"x-dynamic-hop", b"strip-dynamic-hop-header"),
            (b"keep-alive", b"timeout=5, max=1000"),
            (b"x-surviving-header", b"survived-through-gateway"),
        ]
        return resp

    async def handle_internal(request: Request) -> Response:
        upstream_hits["internal"] += 1
        return JSONResponse({"secret": "unauthorized_internal_data"}, status_code=200)

    async def handle_farms_root(request: Request) -> Response:
        upstream_hits["normal"] += 1
        upstream_hits["last_user_id_forwarded"] = request.headers.get("x-user-id")
        return JSONResponse({"farms": ["farm-north-1", "farm-south-2"]})

    async def handle_assign_tech(request: Request) -> Response:
        upstream_hits["normal"] += 1
        return JSONResponse({"status": "assigned"})

    upstream_routes = [
        Route("/api/auth/login", handle_auth_login, methods=["POST"]),
        Route("/api/auth/me", handle_auth_me, methods=["GET"]),
        Route("/api/farms/gzip-data", handle_gzip_data, methods=["GET"]),
        Route("/api/farms/multi-cookie", handle_multi_cookie, methods=["GET"]),
        Route("/api/farms/hop-by-hop", handle_hop_by_hop, methods=["GET"]),
        Route("/api/farms", handle_farms_root, methods=["GET"]),
        Route("/api/technicians/{tech_id}/farms/{farm_id}/assign", handle_assign_tech, methods=["POST"]),
        Route("/internal/v1/runtime/run", handle_internal, methods=["GET", "POST"]),
    ]

    upstream_app = Starlette(routes=upstream_routes)
    upstream_config = uvicorn.Config(
        app=upstream_app,
        host="127.0.0.1",
        port=upstream_port,
        log_level="error",
        access_log=False,
    )
    upstream_server = UvicornTestServer(config=upstream_config)
    upstream_thread = threading.Thread(target=upstream_server.run, daemon=True)
    upstream_thread.start()

    while not upstream_server.started:
        time.sleep(0.02)

    # 2. Configure Gateway upstream to fake upstream
    orig_management_url = settings.management_service_url
    settings.management_service_url = f"http://127.0.0.1:{upstream_port}"

    gateway_app = create_gateway_app()
    gateway_config = uvicorn.Config(
        app=gateway_app,
        host="127.0.0.1",
        port=gateway_port,
        log_level="error",
        access_log=False,
    )
    gateway_server = UvicornTestServer(config=gateway_config)
    gateway_thread = threading.Thread(target=gateway_server.run, daemon=True)
    gateway_thread.start()

    while not gateway_server.started:
        time.sleep(0.02)

    yield {
        "gateway_url": f"http://127.0.0.1:{gateway_port}",
        "upstream_url": f"http://127.0.0.1:{upstream_port}",
        "upstream_hits": upstream_hits,
    }

    # Teardown
    gateway_server.should_exit = True
    upstream_server.should_exit = True
    gateway_thread.join(timeout=2)
    upstream_thread.join(timeout=2)
    settings.management_service_url = orig_management_url


def test_b2_real_socket_gzip_wire_preservation(socket_servers):
    """B2: Tests over a real TCP socket that gzip compressed bytes are streamed as-is.

    Verifies both raw wire byte verification (magic byte 0x1f 0x8b) and httpx client decoding.
    """
    gateway_url = socket_servers["gateway_url"]
    admin_token = make_jwt_token(roles=["ADMIN"])
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Request without automatic decompression to inspect raw bytes over the socket
    with httpx.Client(base_url=gateway_url) as client:
        # 1. Normal client receiving gzip
        resp = client.get("/api/farms/gzip-data", headers=headers)
        assert resp.status_code == 200
        assert resp.headers.get("content-encoding") == "gzip"
        # httpx client successfully decompresses without DecodingError
        payload = resp.json()
        assert payload["message"] == "swiftletcare-compressed-data"
        assert len(payload["items"]) == 100

    # 2. Inspect raw bytes over socket using socket connection directly
    # to guarantee Gateway did NOT send plaintext with gzip header
    parsed_port = int(gateway_url.split(":")[-1])
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(("127.0.0.1", parsed_port))
        raw_req = (
            f"GET /api/farms/gzip-data HTTP/1.1\r\n"
            f"Host: 127.0.0.1\r\n"
            f"Authorization: Bearer {admin_token}\r\n"
            f"Accept-Encoding: gzip\r\n"
            f"Connection: close\r\n\r\n"
        ).encode("latin1")
        sock.sendall(raw_req)

        raw_response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            raw_response += chunk

        # Split headers and body
        header_part, _, body_part = raw_response.partition(b"\r\n\r\n")
        assert b"content-encoding: gzip" in header_part.lower()

        # The body over the wire MUST be genuine gzip (RFC 1952 magic bytes 0x1f, 0x8b)
        magic_idx = body_part.find(b"\x1f\x8b")
        assert magic_idx != -1, "Raw wire body does not contain gzip magic bytes 0x1f 0x8b!"
        decompressed_wire = gzip.decompress(body_part[magic_idx:])
        assert b"swiftletcare-compressed-data" in decompressed_wire


def test_b3_real_socket_multi_cookie_preservation(socket_servers):
    """B3: Tests that multiple Set-Cookie headers are preserved as distinct headers over real TCP socket."""
    gateway_url = socket_servers["gateway_url"]
    admin_token = make_jwt_token(roles=["ADMIN"])
    headers = {"Authorization": f"Bearer {admin_token}"}

    with httpx.Client(base_url=gateway_url) as client:
        resp = client.get("/api/farms/multi-cookie", headers=headers)
        assert resp.status_code == 200

        # Verify multiple cookies received
        set_cookies = resp.headers.get_list("set-cookie")
        assert len(set_cookies) == 2, f"Expected 2 Set-Cookie headers, got: {set_cookies}"

        has_session = any("session_id=swc_sock_12345" in c for c in set_cookies)
        has_csrf = any("csrf_token=swc_csrf_67890" in c for c in set_cookies)
        assert has_session, "Missing session_id Set-Cookie header"
        assert has_csrf, "Missing csrf_token Set-Cookie header"

        # Verify regular custom header survived
        assert resp.headers.get("x-custom-preserved") == "custom-header-value"


def test_b3_real_socket_hop_by_hop_stripping(socket_servers):
    """B3: Tests that standard and dynamic (RFC 7230 §6.1) hop-by-hop headers are stripped over real socket."""
    gateway_url = socket_servers["gateway_url"]
    admin_token = make_jwt_token(roles=["ADMIN"])
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "Connection": "close, X-Dynamic-Hop",
        "X-Dynamic-Hop": "strip-dynamic-hop-header",
        "Keep-Alive": "timeout=5",
        "X-Surviving-Header": "survived-through-gateway",
    }

    with httpx.Client(base_url=gateway_url) as client:
        resp = client.get("/api/farms/hop-by-hop", headers=headers)
        assert resp.status_code == 200

        # Hop-by-hop headers must NOT be present in gateway response
        assert "x-dynamic-hop" not in resp.headers
        assert "keep-alive" not in resp.headers

        # Non hop-by-hop header must survive
        assert resp.headers.get("x-surviving-header") == "survived-through-gateway"


@pytest.mark.parametrize(
    "payload",
    [
        "/api/farms/..%2f..%2finternal/v1/runtime/run",
        "/api/farms/%2e%2e/%2e%2e/internal/v1/runtime/run",
        "/api/farms/..%5c..%5cinternal/v1/runtime/run",
        "/api/farms//internal/v1/runtime/run",
        "/api/farms/..;internal",
        "/api/farms/%00internal",
    ],
)
def test_b1_real_socket_path_traversal_rejection(socket_servers, payload):
    """B1: Tests over real TCP sockets that traversal and dangerous encodings are rejected (400/403/404)

    and upstream /internal endpoint is never touched.
    """
    gateway_url = socket_servers["gateway_url"]
    upstream_hits_before = socket_servers["upstream_hits"]["internal"]

    # Use raw socket to ensure client-side httpx doesn't pre-normalize paths
    parsed_port = int(gateway_url.split(":")[-1])
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(("127.0.0.1", parsed_port))
        req = (
            f"GET {payload} HTTP/1.1\r\n"
            f"Host: 127.0.0.1\r\n"
            f"Connection: close\r\n\r\n"
        ).encode("latin1")
        sock.sendall(req)

        raw_response = sock.recv(4096).decode("latin1", errors="ignore")
        first_line = raw_response.split("\r\n")[0]
        status_code = int(first_line.split()[1])
        assert status_code in (400, 403, 404), f"Expected 400/403/404 for payload {payload}, got {status_code}"

    # Upstream internal endpoint must never have been hit
    upstream_hits_after = socket_servers["upstream_hits"]["internal"]
    assert upstream_hits_after == upstream_hits_before, f"Upstream internal hit occurred with payload {payload}!"


def test_b1_real_socket_direct_internal_forbidden(socket_servers):
    """B1: Tests that direct access to /internal via normal path routing returns 403 Forbidden."""
    gateway_url = socket_servers["gateway_url"]
    upstream_hits_before = socket_servers["upstream_hits"]["internal"]
    admin_token = make_jwt_token(roles=["ADMIN"])

    with httpx.Client(base_url=gateway_url) as client:
        resp = client.get("/api/farms/internal/test", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 403
        assert "Forbidden" in resp.json()["detail"]

    assert socket_servers["upstream_hits"]["internal"] == upstream_hits_before


# =============================================================================
# CP11.3: Real Socket JWT Authentication & RBAC Tests
# =============================================================================
def test_socket_public_login_and_authenticated_request_flow(socket_servers):
    """Verifies complete end-to-end flow over real TCP socket:

    1. Login without token to get access token.
    2. Use token to access protected /api/farms endpoint.
    """
    gateway_url = socket_servers["gateway_url"]

    with httpx.Client(base_url=gateway_url) as client:
        # Step 1: Public login
        login_resp = client.post("/api/auth/login", json={"email": "admin@swiftletcare.vn", "password": "pass"})
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        # Step 2: Access protected route with Bearer token
        farms_resp = client.get("/api/farms", headers={"Authorization": f"Bearer {token}"})
        assert farms_resp.status_code == 200
        assert "farms" in farms_resp.json()


def test_socket_missing_token_returns_401(socket_servers):
    """Verifies that accessing protected endpoints over real socket without token yields 401."""
    gateway_url = socket_servers["gateway_url"]

    with httpx.Client(base_url=gateway_url) as client:
        resp = client.get("/api/farms")
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers


def test_socket_rbac_technician_assign_admin_only(socket_servers):
    """Verifies that admin-only assign endpoint returns 403 for technician over real TCP socket."""
    gateway_url = socket_servers["gateway_url"]
    tech_id = "11111111-1111-1111-1111-111111111111"
    farm_id = "33333333-3333-3333-3333-333333333333"
    assign_url = f"/api/technicians/{tech_id}/farms/{farm_id}/assign"

    with httpx.Client(base_url=gateway_url) as client:
        # 1. Technician token -> 403 Forbidden
        tech_token = make_jwt_token(user_id=tech_id, roles=["TECHNICIAN"])
        resp = client.post(assign_url, headers={"Authorization": f"Bearer {tech_token}"})
        assert resp.status_code == 403
        assert "Insufficient role permissions" in resp.json()["detail"]

        # 2. Admin token -> 200 OK
        admin_token = make_jwt_token(roles=["ADMIN"])
        resp_admin = client.post(assign_url, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp_admin.status_code == 200


def test_socket_header_sanitization_over_wire(socket_servers):
    """Verifies that forged identity headers sent over real TCP socket are stripped."""
    gateway_url = socket_servers["gateway_url"]
    real_user_id = "55555555-5555-5555-5555-555555555555"
    token = make_jwt_token(user_id=real_user_id, roles=["ADMIN"])

    spoofed_headers = {
        "Authorization": f"Bearer {token}",
        "X-User-Id": "attacker-spoofed-id",
        "X-User-Roles": "SUPER_ADMIN",
        "X-Internal-Secret": "leak",
    }

    with httpx.Client(base_url=gateway_url) as client:
        resp = client.get("/api/farms", headers=spoofed_headers)
        assert resp.status_code == 200

        # Verify upstream received the authenticated user ID and NOT the spoofed one
        assert socket_servers["upstream_hits"]["last_user_id_forwarded"] == real_user_id
