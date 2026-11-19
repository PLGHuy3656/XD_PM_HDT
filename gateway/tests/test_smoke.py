"""Smoke tests for SwiftletCare API Gateway (CP11 Phase 1 & CP11.3)."""
import httpx
from starlette.testclient import TestClient

from app.config import settings
from app.main import create_gateway_app
from tests.conftest import make_jwt_token


def test_smoke_full_lifecycle():
    """Smoke test verifying gateway startup, health check, correlation tracing,

    JWT authentication, and multi-service dispatch.
    """
    dispatched_services = set()
    admin_token = make_jwt_token(roles=["ADMIN"])
    auth_headers = {"Authorization": f"Bearer {admin_token}"}

    def mock_backend_router(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)

        # Mock Management auth introspection
        if "/api/auth/me" in url_str:
            return httpx.Response(
                status_code=200,
                headers={"Content-Type": "application/json"},
                json={
                    "id": "00000000-0000-0000-0000-000000000001",
                    "email": "admin@swiftletcare.vn",
                    "status": "ACTIVE",
                    "roles": ["ADMIN"],
                },
            )

        if str(settings.management_service_url) in url_str:
            dispatched_services.add("management")
        elif str(settings.iot_service_url) in url_str:
            dispatched_services.add("iot")
        elif str(settings.ai_service_url) in url_str:
            dispatched_services.add("ai")
        elif str(settings.notification_service_url) in url_str:
            dispatched_services.add("notification")
        elif str(settings.analytics_service_url) in url_str:
            dispatched_services.add("analytics")

        return httpx.Response(status_code=200, json={"status": "ok", "url": url_str})

    test_app = create_gateway_app()
    test_app.state.http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(mock_backend_router)
    )

    with TestClient(test_app) as client:
        # 1. Health check (Public)
        res = client.get("/health")
        assert res.status_code == 200
        cid = res.headers.get("X-Correlation-ID")
        assert cid is not None

        # 2. Call Management route (Protected)
        res = client.get("/api/farms", headers={"X-Correlation-ID": cid, **auth_headers})
        assert res.status_code == 200
        assert res.headers.get("X-Correlation-ID") == cid

        # 3. Call IoT route (Protected)
        res = client.get("/api/iot/devices/presence", headers={"X-Correlation-ID": cid, **auth_headers})
        assert res.status_code == 200

        # 4. Call AI route (Protected)
        res = client.get("/api/v1/ai/cameras", headers={"X-Correlation-ID": cid, **auth_headers})
        assert res.status_code == 200

        # 5. Call Notification route (Protected)
        res = client.get("/api/v1/alerts", headers={"X-Correlation-ID": cid, **auth_headers})
        assert res.status_code == 200

        # 6. Call Analytics route (Protected, when deployed)
        old_deployed = settings.analytics_service_deployed
        try:
            settings.analytics_service_deployed = True
            res = client.get("/api/v1/analytics/trends", headers={"X-Correlation-ID": cid, **auth_headers})
            assert res.status_code == 200
        finally:
            settings.analytics_service_deployed = old_deployed

        # 7. Verify all 5 upstreams received their respective requests
        assert dispatched_services == {"management", "iot", "ai", "notification", "analytics"}
