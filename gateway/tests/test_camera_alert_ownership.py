"""Tests for CP11 NB-2 (Camera Ownership) & NB-3 (Alert Ownership) resolution.

Verifies:
1. Valid Farm Owner access to owned cameras and alerts (200 OK).
2. Cross-tenant isolation: Farm Owner blocked on cameras and alerts of another farm (403 Forbidden).
3. Technician access based on farm assignment (200 for assigned, 403 for unassigned).
4. Admin global authority for both cameras and alerts (200 OK).
5. Missing camera / alert handling (fail-closed 403/404).
6. Upstream outage handling (503 Service Unavailable).
"""
import uuid
import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_gateway_app
from tests.test_auth_rbac import make_jwt_token

# Test identities
OWNER_A_ID = "00000000-0000-0000-0000-00000000000a"
OWNER_B_ID = "00000000-0000-0000-0000-00000000000b"
TECH_A_ID = "00000000-0000-0000-0000-00000000000c"
ADMIN_ID = "00000000-0000-0000-0000-00000000000d"

FARM_A_ID = "11111111-1111-1111-1111-111111111111"
FARM_B_ID = "22222222-2222-2222-2222-222222222222"

CAM_A1 = "CAM-01"
CAM_B1 = "CAM-02"

ALERT_A1 = "ALT-A1"
ALERT_B1 = "ALT-B1"


@pytest.fixture
def ownership_env():
    """Mock environment setting up Management, AI, and Notification services."""
    env_config = {
        "management_online": True,
        "notification_online": True,
        "ai_online": True,
    }
    recorded_hits = {
        "management": 0,
        "ai": 0,
        "notification": 0,
    }

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        auth_header = request.headers.get("Authorization", "")
        token_str = auth_header.replace("Bearer ", "").strip()

        # Decode token to extract caller
        caller_id = "anon"
        caller_roles = []
        if token_str:
            try:
                import jwt
                p = jwt.decode(token_str, settings.jwt_secret, algorithms=["HS256"])
                caller_id = str(p.get("sub", ""))
                caller_roles = p.get("roles", [])
            except Exception:
                return httpx.Response(401, json={"detail": "Invalid token"})

        # 1. Management Service Mock
        if str(settings.management_service_url) in url_str:
            if not env_config["management_online"]:
                raise httpx.ConnectError("Management service unreachable")

            recorded_hits["management"] += 1

            # Auth check /api/auth/me
            if "/api/auth/me" in url_str:
                return httpx.Response(200, json={
                    "id": caller_id,
                    "email": f"{caller_id}@test.dev",
                    "status": "ACTIVE",
                    "roles": caller_roles,
                })

            # Farm access check /api/farms/{id}
            if "/api/farms/" in url_str:
                target_farm = url_str.split("/api/farms/")[-1].split("/")[0].split("?")[0]
                if target_farm == FARM_A_ID:
                    if "ADMIN" in caller_roles or caller_id in (OWNER_A_ID, TECH_A_ID):
                        return httpx.Response(200, json={"farm_id": FARM_A_ID, "owner_id": OWNER_A_ID})
                    return httpx.Response(403, json={"detail": "Forbidden: Farm not accessible"})
                elif target_farm == FARM_B_ID:
                    if "ADMIN" in caller_roles or caller_id == OWNER_B_ID:
                        return httpx.Response(200, json={"farm_id": FARM_B_ID, "owner_id": OWNER_B_ID})
                    return httpx.Response(403, json={"detail": "Forbidden: Farm not accessible"})
                return httpx.Response(404, json={"detail": "Farm not found"})

            # Camera / Device check (/api/cameras/{id} or /api/devices/{id})
            if "/api/cameras/" in url_str or "/api/devices/" in url_str:
                prefix = "/api/cameras/" if "/api/cameras/" in url_str else "/api/devices/"
                target_cam = url_str.split(prefix)[-1].split("/")[0].split("?")[0]
                if target_cam == CAM_A1:
                    if "ADMIN" in caller_roles or caller_id in (OWNER_A_ID, TECH_A_ID):
                        return httpx.Response(200, json={
                            "device_id": str(uuid.uuid4()),
                            "node_id": CAM_A1,
                            "farm_id": FARM_A_ID,
                            "device_type": "CAMERA",
                        })
                    return httpx.Response(403, json={"detail": "Forbidden: User does not have access to this farm resource"})
                elif target_cam == CAM_B1:
                    if "ADMIN" in caller_roles or caller_id == OWNER_B_ID:
                        return httpx.Response(200, json={
                            "device_id": str(uuid.uuid4()),
                            "node_id": CAM_B1,
                            "farm_id": FARM_B_ID,
                            "device_type": "CAMERA",
                        })
                    return httpx.Response(403, json={"detail": "Forbidden: User does not have access to this farm resource"})
                return httpx.Response(404, json={"detail": "Camera not found"})

        # 2. Notification Service Mock
        if str(settings.notification_service_url) in url_str:
            if not env_config["notification_online"]:
                raise httpx.ConnectError("Notification service unreachable")

            # Metadata endpoint for auth guard
            if "/metadata" in url_str:
                target_alt = url_str.split("/api/v1/alerts/")[-1].split("/metadata")[0]
                if target_alt == ALERT_A1:
                    return httpx.Response(200, json={
                        "alertId": ALERT_A1,
                        "farmId": FARM_A_ID,
                        "status": "OPEN",
                        "severity": "HIGH",
                        "eventType": "HIGH_TEMPERATURE",
                    })
                elif target_alt == ALERT_B1:
                    return httpx.Response(200, json={
                        "alertId": ALERT_B1,
                        "farmId": FARM_B_ID,
                        "status": "OPEN",
                        "severity": "CRITICAL",
                        "eventType": "PREDATOR_DETECTED",
                    })
                return httpx.Response(404, json={"detail": "Alert not found"})

            recorded_hits["notification"] += 1
            # Actual downstream actions
            if "/acknowledge" in url_str or "/resolve" in url_str or request.method == "GET":
                return httpx.Response(200, json={"status": "OK", "alertId": url_str.split("/")[-2]})

        # 3. AI Service Mock
        if str(settings.ai_service_url) in url_str:
            if not env_config["ai_online"]:
                raise httpx.ConnectError("AI service unreachable")

            recorded_hits["ai"] += 1
            if "/counts/latest" in url_str:
                return httpx.Response(200, json={"cameraId": CAM_A1, "entryCount": 10, "exitCount": 2, "netChange": 8})
            if "/counts" in url_str:
                return httpx.Response(200, json=[{"cameraId": CAM_A1, "entryCount": 10, "exitCount": 2, "netChange": 8}])
            if "/detections/latest" in url_str:
                return httpx.Response(200, json={"cameraId": CAM_A1, "detections": []})
            if "/status" in url_str:
                return httpx.Response(200, json={"cameraId": CAM_A1, "status": "ONLINE", "fps": 25.0})

        return httpx.Response(200, json={"status": "fallback_ok"})

    app = create_gateway_app()
    app.state.http_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

    with TestClient(app) as client:
        yield {
            "client": client,
            "hits": recorded_hits,
            "config": env_config,
        }


# =============================================================================
# NB-2: Camera Ownership Tests
# =============================================================================

def test_owner_accesses_own_camera_counts_latest_allowed(ownership_env):
    """Owner A accessing counts/latest of CAM-01 (Farm A) succeeds (200 OK)."""
    client = ownership_env["client"]
    token = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    resp = client.get(f"/api/v1/ai/cameras/{CAM_A1}/counts/latest", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["cameraId"] == CAM_A1
    assert ownership_env["hits"]["ai"] == 1


def test_owner_accesses_own_camera_counts_history_allowed(ownership_env):
    """Owner A querying counts history of CAM-01 succeeds (200 OK)."""
    client = ownership_env["client"]
    token = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    resp = client.get(f"/api/v1/ai/cameras/{CAM_A1}/counts?limit=10", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert ownership_env["hits"]["ai"] == 1


def test_owner_accesses_own_camera_detections_latest_allowed(ownership_env):
    """Owner A querying detections/latest of CAM-01 succeeds (200 OK)."""
    client = ownership_env["client"]
    token = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    resp = client.get(f"/api/v1/ai/cameras/{CAM_A1}/detections/latest", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert "detections" in resp.json()
    assert ownership_env["hits"]["ai"] == 1


def test_owner_cross_farm_camera_access_denied(ownership_env):
    """Owner A attempting to access CAM-02 (Farm B) is blocked with 403 Forbidden."""
    client = ownership_env["client"]
    token = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    resp = client.get(f"/api/v1/ai/cameras/{CAM_B1}/counts/latest", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert "not authorized" in resp.json()["detail"].lower()
    # Downstream AI service must NEVER be reached
    assert ownership_env["hits"]["ai"] == 0


def test_technician_assigned_camera_access_allowed(ownership_env):
    """Technician assigned to Farm A can access CAM-01 (200 OK)."""
    client = ownership_env["client"]
    token = make_jwt_token(user_id=TECH_A_ID, roles=["TECHNICIAN"])
    resp = client.get(f"/api/v1/ai/cameras/{CAM_A1}/counts/latest", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert ownership_env["hits"]["ai"] == 1


def test_technician_unassigned_camera_access_denied(ownership_env):
    """Technician not assigned to Farm B is blocked on CAM-02 with 403 Forbidden."""
    client = ownership_env["client"]
    token = make_jwt_token(user_id=TECH_A_ID, roles=["TECHNICIAN"])
    resp = client.get(f"/api/v1/ai/cameras/{CAM_B1}/counts/latest", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert ownership_env["hits"]["ai"] == 0


def test_admin_camera_access_global_authority(ownership_env):
    """Admin has global access to all cameras across all farms."""
    client = ownership_env["client"]
    token = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])
    resp1 = client.get(f"/api/v1/ai/cameras/{CAM_A1}/counts/latest", headers={"Authorization": f"Bearer {token}"})
    assert resp1.status_code == 200
    resp2 = client.get(f"/api/v1/ai/cameras/{CAM_B1}/counts/latest", headers={"Authorization": f"Bearer {token}"})
    assert resp2.status_code == 200


def test_missing_camera_fails_closed(ownership_env):
    """Accessing an unresolvable / non-existent camera fails closed with 403."""
    client = ownership_env["client"]
    token = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    resp = client.get("/api/v1/ai/cameras/CAM-NONEXISTENT/counts/latest", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert ownership_env["hits"]["ai"] == 0


def test_management_outage_camera_access_fails_closed(ownership_env):
    """When Management Service is unreachable, camera access fails closed with 503."""
    client = ownership_env["client"]
    ownership_env["config"]["management_online"] = False
    token = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    resp = client.get(f"/api/v1/ai/cameras/{CAM_A1}/counts/latest", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 503
    assert "Service Unavailable" in resp.json()["detail"]
    assert ownership_env["hits"]["ai"] == 0


# =============================================================================
# NB-3: Alert Ownership Tests
# =============================================================================

def test_owner_accesses_own_alert_detail_allowed(ownership_env):
    """Owner A can retrieve detail for ALT-A1 (Farm A)."""
    client = ownership_env["client"]
    token = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    resp = client.get(f"/api/v1/alerts/{ALERT_A1}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert ownership_env["hits"]["notification"] == 1


def test_owner_acknowledges_own_alert_allowed(ownership_env):
    """Owner A can acknowledge ALT-A1 (Farm A)."""
    client = ownership_env["client"]
    token = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    resp = client.post(
        f"/api/v1/alerts/{ALERT_A1}/acknowledge",
        headers={"Authorization": f"Bearer {token}"},
        json={"actorId": OWNER_A_ID},
    )
    assert resp.status_code == 200
    assert ownership_env["hits"]["notification"] == 1


def test_owner_resolves_own_alert_allowed(ownership_env):
    """Owner A can resolve ALT-A1 (Farm A)."""
    client = ownership_env["client"]
    token = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    resp = client.post(
        f"/api/v1/alerts/{ALERT_A1}/resolve",
        headers={"Authorization": f"Bearer {token}"},
        json={"actorId": OWNER_A_ID, "resolutionNote": "Fixed problem"},
    )
    assert resp.status_code == 200
    assert ownership_env["hits"]["notification"] == 1


def test_owner_cross_tenant_alert_access_denied(ownership_env):
    """Owner A attempting to acknowledge ALT-B1 (Farm B) is blocked with 403 Forbidden."""
    client = ownership_env["client"]
    token = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    resp = client.post(
        f"/api/v1/alerts/{ALERT_B1}/acknowledge",
        headers={"Authorization": f"Bearer {token}"},
        json={"actorId": OWNER_A_ID},
    )
    assert resp.status_code == 403
    # Downstream action must NEVER be dispatched
    assert ownership_env["hits"]["notification"] == 0


def test_technician_assigned_alert_access_allowed(ownership_env):
    """Technician assigned to Farm A can acknowledge ALT-A1."""
    client = ownership_env["client"]
    token = make_jwt_token(user_id=TECH_A_ID, roles=["TECHNICIAN"])
    resp = client.post(
        f"/api/v1/alerts/{ALERT_A1}/acknowledge",
        headers={"Authorization": f"Bearer {token}"},
        json={"actorId": TECH_A_ID},
    )
    assert resp.status_code == 200
    assert ownership_env["hits"]["notification"] == 1


def test_technician_unassigned_alert_access_denied(ownership_env):
    """Technician not assigned to Farm B is blocked on ALT-B1 with 403 Forbidden."""
    client = ownership_env["client"]
    token = make_jwt_token(user_id=TECH_A_ID, roles=["TECHNICIAN"])
    resp = client.post(
        f"/api/v1/alerts/{ALERT_B1}/acknowledge",
        headers={"Authorization": f"Bearer {token}"},
        json={"actorId": TECH_A_ID},
    )
    assert resp.status_code == 403
    assert ownership_env["hits"]["notification"] == 0


def test_admin_alert_access_global_authority(ownership_env):
    """Admin has global authority to acknowledge alerts across all farms."""
    client = ownership_env["client"]
    token = make_jwt_token(user_id=ADMIN_ID, roles=["ADMIN"])
    resp = client.post(
        f"/api/v1/alerts/{ALERT_B1}/acknowledge",
        headers={"Authorization": f"Bearer {token}"},
        json={"actorId": ADMIN_ID},
    )
    assert resp.status_code == 200
    assert ownership_env["hits"]["notification"] == 1


def test_missing_alert_fails_closed(ownership_env):
    """Accessing an unresolvable / non-existent alert fails closed with 403."""
    client = ownership_env["client"]
    token = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    resp = client.post(
        "/api/v1/alerts/ALT-NONEXISTENT/acknowledge",
        headers={"Authorization": f"Bearer {token}"},
        json={"actorId": OWNER_A_ID},
    )
    assert resp.status_code == 403
    assert ownership_env["hits"]["notification"] == 0


def test_notification_outage_alert_access_fails_closed(ownership_env):
    """When Notification Service is unreachable, alert action fails closed with 503."""
    client = ownership_env["client"]
    ownership_env["config"]["notification_online"] = False
    token = make_jwt_token(user_id=OWNER_A_ID, roles=["FARM_OWNER"])
    resp = client.post(
        f"/api/v1/alerts/{ALERT_A1}/acknowledge",
        headers={"Authorization": f"Bearer {token}"},
        json={"actorId": OWNER_A_ID},
    )
    assert resp.status_code == 503
    assert "Service Unavailable" in resp.json()["detail"]
    assert ownership_env["hits"]["notification"] == 0
