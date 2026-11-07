import uuid
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core.security import create_access_token
from app.database import get_connection
from app.main import app


def is_postgres_available() -> bool:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                return cur.fetchone() is not None
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not is_postgres_available(),
    reason="Live PostgreSQL management_db container is not available",
)


@pytest.fixture(scope="module")
def seeded_multitenant_env():
    """
    Seeds a realistic multi-tenant fixture directly into live PostgreSQL management_db:
    - Owner A (FARM_OWNER) with Farm A
    - Owner B (FARM_OWNER) with Farm B
    - Two distinct zones in Farm A and Farm B sharing the EXACT SAME zone_code: 'ZONE_COLLISION'
    - Device A in Farm A, Device B in Farm B
    - Field technician with INACTIVE assignment (is_active = FALSE) to Farm B
    - Automatic cleanup in finally block ensuring zero leftover test artifacts.
    """
    client = TestClient(app)
    run_suffix = uuid.uuid4().hex[:8]

    # Identifiers
    owner_a_id = str(uuid.uuid4())
    owner_b_id = str(uuid.uuid4())
    tech_id = str(uuid.uuid4())

    farm_a_id = str(uuid.uuid4())
    farm_b_id = str(uuid.uuid4())
    farm_a_code = f"FA_CODE_{run_suffix}"
    farm_b_code = f"FB_CODE_{run_suffix}"

    zone_a_id = str(uuid.uuid4())
    zone_b_id = str(uuid.uuid4())
    colliding_zone_code = f"ZONE_COLLISION_{run_suffix}"

    dev_a_id = str(uuid.uuid4())
    dev_b_id = str(uuid.uuid4())
    node_a = f"NODE_A_{run_suffix}"
    node_b = f"NODE_B_{run_suffix}"

    # Setup in PostgreSQL
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Fetch role IDs
            cur.execute("SELECT id, name FROM roles WHERE name IN ('FARM_OWNER', 'TECHNICIAN');")
            role_map = {row[1]: str(row[0]) for row in cur.fetchall()}

            # 2. Insert Users
            cur.execute(
                """
                INSERT INTO users (id, email, full_name, status)
                VALUES
                    (%s, %s, %s, 'ACTIVE'),
                    (%s, %s, %s, 'ACTIVE'),
                    (%s, %s, %s, 'ACTIVE');
                """,
                (
                    owner_a_id, f"owner_a_{run_suffix}@test.vn", "Owner A",
                    owner_b_id, f"owner_b_{run_suffix}@test.vn", "Owner B",
                    tech_id, f"tech_{run_suffix}@test.vn", "Inactive Tech",
                ),
            )

            # 3. Insert User Roles
            cur.execute(
                """
                INSERT INTO user_roles (user_id, role_id)
                VALUES
                    (%s, %s),
                    (%s, %s),
                    (%s, %s);
                """,
                (
                    owner_a_id, role_map["FARM_OWNER"],
                    owner_b_id, role_map["FARM_OWNER"],
                    tech_id, role_map["TECHNICIAN"],
                ),
            )

            # 4. Insert Technician Profile
            cur.execute(
                """
                INSERT INTO technicians (id, full_name, email, status)
                VALUES (%s, %s, %s, 'ACTIVE');
                """,
                (tech_id, "Inactive Tech", f"tech_{run_suffix}@test.vn"),
            )

            # 5. Insert Farms
            cur.execute(
                """
                INSERT INTO farms (id, farm_code, name, owner_id, status)
                VALUES
                    (%s, %s, %s, %s, 'ACTIVE'),
                    (%s, %s, %s, %s, 'ACTIVE');
                """,
                (
                    farm_a_id, farm_a_code, f"Farm Alpha {run_suffix}", owner_a_id,
                    farm_b_id, farm_b_code, f"Farm Beta {run_suffix}", owner_b_id,
                ),
            )

            # 6. Insert Zones with colliding zone_code across Farm A and Farm B
            cur.execute(
                """
                INSERT INTO zones (id, farm_id, zone_code, name)
                VALUES
                    (%s, %s, %s, %s),
                    (%s, %s, %s, %s);
                """,
                (
                    zone_a_id, farm_a_id, colliding_zone_code, "Zone in Farm Alpha",
                    zone_b_id, farm_b_id, colliding_zone_code, "Zone in Farm Beta",
                ),
            )

            # 7. Insert Devices
            cur.execute(
                """
                INSERT INTO devices (id, node_id, farm_id, zone_id, name, is_active)
                VALUES
                    (%s, %s, %s, %s, 'Device Alpha', TRUE),
                    (%s, %s, %s, %s, 'Device Beta', TRUE);
                """,
                (
                    dev_a_id, node_a, farm_a_id, zone_a_id,
                    dev_b_id, node_b, farm_b_id, zone_b_id,
                ),
            )

            # 8. Insert Active Assignment on Farm A, Inactive Assignment on Farm B
            cur.execute(
                """
                INSERT INTO technician_assignments (technician_id, farm_id, is_primary, is_active)
                VALUES
                    (%s, %s, TRUE, TRUE),
                    (%s, %s, TRUE, FALSE);
                """,
                (tech_id, farm_a_id, tech_id, farm_b_id),
            )
            conn.commit()

    # Generate valid JWT tokens
    old_secret = settings.jwt_secret
    if not settings.jwt_secret:
        settings.jwt_secret = "multitenant_idor_e2e_jwt_secret_key_32_bytes_long"

    token_a = create_access_token(subject=owner_a_id, roles=["FARM_OWNER"])
    token_b = create_access_token(subject=owner_b_id, roles=["FARM_OWNER"])
    token_tech = create_access_token(subject=tech_id, roles=["TECHNICIAN"])

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    headers_tech = {"Authorization": f"Bearer {token_tech}"}

    yield {
        "client": client,
        "owner_a_id": owner_a_id,
        "owner_b_id": owner_b_id,
        "tech_id": tech_id,
        "farm_a_id": farm_a_id,
        "farm_b_id": farm_b_id,
        "farm_a_code": farm_a_code,
        "farm_b_code": farm_b_code,
        "zone_a_id": zone_a_id,
        "zone_b_id": zone_b_id,
        "colliding_zone_code": colliding_zone_code,
        "dev_a_id": dev_a_id,
        "dev_b_id": dev_b_id,
        "node_a": node_a,
        "node_b": node_b,
        "headers_a": headers_a,
        "headers_b": headers_b,
        "headers_tech": headers_tech,
    }

    # Teardown / Cleanup
    settings.jwt_secret = old_secret
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM devices WHERE id IN (%s, %s);", (dev_a_id, dev_b_id))
            cur.execute("DELETE FROM zones WHERE id IN (%s, %s);", (zone_a_id, zone_b_id))
            cur.execute("DELETE FROM technician_assignments WHERE technician_id = %s;", (tech_id,))
            cur.execute("DELETE FROM farms WHERE id IN (%s, %s);", (farm_a_id, farm_b_id))
            cur.execute("DELETE FROM technicians WHERE id = %s;", (tech_id,))
            cur.execute("DELETE FROM user_roles WHERE user_id IN (%s, %s, %s);", (owner_a_id, owner_b_id, tech_id))
            cur.execute("DELETE FROM users WHERE id IN (%s, %s, %s);", (owner_a_id, owner_b_id, tech_id))
            conn.commit()


def test_h1_zone_detail_uuid_enforcement_and_idor_prevention(seeded_multitenant_env):
    """
    H-1 Remediation Verification:
    - GET /api/zones/{zone_id} only accepts valid UUID.
    - Non-UUID returns 404 (not 500).
    - Owner A cannot read Owner B's zone (returns 403 Forbidden).
    - Even with identical zone_code in two farms, Owner A gets Zone A, and never accesses Zone B.
    """
    client = seeded_multitenant_env["client"]
    headers_a = seeded_multitenant_env["headers_a"]
    headers_b = seeded_multitenant_env["headers_b"]
    zone_a_id = seeded_multitenant_env["zone_a_id"]
    zone_b_id = seeded_multitenant_env["zone_b_id"]
    colliding_code = seeded_multitenant_env["colliding_zone_code"]

    # 1. Non-UUID path parameter is rejected with 404
    resp_non_uuid = client.get(f"/api/zones/{colliding_code}", headers=headers_a)
    assert resp_non_uuid.status_code == 404
    assert "invalid UUID" in resp_non_uuid.json().get("detail", "")

    resp_slug = client.get("/api/zones/arbitrary-slug-zone-123", headers=headers_a)
    assert resp_slug.status_code == 404

    # 2. Owner A reads own Zone A -> 200 OK
    resp_owner_a_zone_a = client.get(f"/api/zones/{zone_a_id}", headers=headers_a)
    assert resp_owner_a_zone_a.status_code == 200
    data_a = resp_owner_a_zone_a.json()
    assert data_a["zone_id"] == zone_a_id
    assert data_a["farm_id"] == seeded_multitenant_env["farm_a_id"]
    assert data_a["zone_code"] == colliding_code

    # 3. IDOR Attack: Owner A attempts to read Owner B's Zone B -> MUST BE 403 Forbidden!
    resp_owner_a_zone_b = client.get(f"/api/zones/{zone_b_id}", headers=headers_a)
    assert resp_owner_a_zone_b.status_code == 403
    assert "Forbidden" in resp_owner_a_zone_b.json().get("detail", "")

    # 4. Owner B reads own Zone B -> 200 OK
    resp_owner_b_zone_b = client.get(f"/api/zones/{zone_b_id}", headers=headers_b)
    assert resp_owner_b_zone_b.status_code == 200
    data_b = resp_owner_b_zone_b.json()
    assert data_b["zone_id"] == zone_b_id
    assert data_b["farm_id"] == seeded_multitenant_env["farm_b_id"]

    # 5. IDOR Attack: Owner B attempts to read Owner A's Zone A -> 403 Forbidden!
    resp_owner_b_zone_a = client.get(f"/api/zones/{zone_a_id}", headers=headers_b)
    assert resp_owner_b_zone_a.status_code == 403


def test_h2_devices_query_by_farm_code_and_tenant_isolation(seeded_multitenant_env):
    """
    H-2 Remediation Verification:
    - GET /api/devices?farm_id=FARM_CODE returns 200 (not HTTP 500 UUID cast error).
    - Normalized canonical farm UUID queries devices safely.
    - Unauthorized owner querying another owner's farm code returns 403 Forbidden.
    """
    client = seeded_multitenant_env["client"]
    headers_a = seeded_multitenant_env["headers_a"]
    headers_b = seeded_multitenant_env["headers_b"]
    farm_a_code = seeded_multitenant_env["farm_a_code"]
    farm_b_code = seeded_multitenant_env["farm_b_code"]
    farm_a_id = seeded_multitenant_env["farm_a_id"]
    farm_b_id = seeded_multitenant_env["farm_b_id"]
    dev_a_id = seeded_multitenant_env["dev_a_id"]

    # 1. Owner A queries own farm by farm_code -> 200 OK (previously crashed with HTTP 500!)
    resp_code = client.get(f"/api/devices?farm_id={farm_a_code}", headers=headers_a)
    assert resp_code.status_code == 200
    devices = resp_code.json()
    assert isinstance(devices, list)
    assert len(devices) == 1
    assert devices[0]["device_id"] == dev_a_id
    assert devices[0]["farm_id"] == farm_a_id

    # 2. Owner A queries own farm by farm UUID -> 200 OK
    resp_uuid = client.get(f"/api/devices?farm_id={farm_a_id}", headers=headers_a)
    assert resp_uuid.status_code == 200
    assert len(resp_uuid.json()) == 1

    # 3. Owner A queries Owner B's farm by farm_code -> 403 Forbidden
    resp_forbidden_code = client.get(f"/api/devices?farm_id={farm_b_code}", headers=headers_a)
    assert resp_forbidden_code.status_code == 403

    # 4. Owner A queries Owner B's farm by UUID -> 403 Forbidden
    resp_forbidden_uuid = client.get(f"/api/devices?farm_id={farm_b_id}", headers=headers_a)
    assert resp_forbidden_uuid.status_code == 403

    # 5. Non-admin calls GET /api/devices without farm_id -> 403 Forbidden
    resp_no_farm = client.get("/api/devices", headers=headers_a)
    assert resp_no_farm.status_code == 403


def test_inactive_technician_assignment_enforcement(seeded_multitenant_env):
    """
    Verifies that inactive technician assignments (is_active = FALSE) are denied access.
    """
    client = seeded_multitenant_env["client"]
    headers_tech = seeded_multitenant_env["headers_tech"]
    farm_b_id = seeded_multitenant_env["farm_b_id"]
    farm_b_code = seeded_multitenant_env["farm_b_code"]

    # 1. GET /api/farms for technician with inactive assignment must not list Farm B
    resp_farms = client.get("/api/farms", headers=headers_tech)
    assert resp_farms.status_code == 200
    farms = resp_farms.json()
    assert all(f["farm_id"] != farm_b_id for f in farms)

    # 2. Inactive technician requests Farm B detail -> 403 Forbidden
    resp_farm_detail = client.get(f"/api/farms/{farm_b_id}", headers=headers_tech)
    assert resp_farm_detail.status_code == 403

    # 3. Inactive technician requests devices in Farm B -> 403 Forbidden
    resp_tech_devices = client.get(f"/api/devices?farm_id={farm_b_code}", headers=headers_tech)
    assert resp_tech_devices.status_code == 403


def test_m1_m3_device_detail_single_presence_and_status_distinction(seeded_multitenant_env, monkeypatch):
    """
    M-1, M-3 & L-1/L-2 Verification:
    - GET /api/devices/{device_id} resolves presence and returns status ("ONLINE", "OFFLINE", or "UNKNOWN").
    - Schema exposes both `status` and `presence_status`.
    - Parent farm authorization is properly verified.
    - Fully isolated from any live IoT service via monkeypatch.
    """
    client = seeded_multitenant_env["client"]
    headers_a = seeded_multitenant_env["headers_a"]
    headers_b = seeded_multitenant_env["headers_b"]
    dev_a_id = seeded_multitenant_env["dev_a_id"]
    dev_b_id = seeded_multitenant_env["dev_b_id"]

    def failing_http_get(url: str, timeout: float):
        raise ConnectionError("Mocked unreachable IoT service for deterministic E2E test")

    from app.repositories.device_repository import device_repository
    monkeypatch.setattr(device_repository._iot_adapter, "_http_get", failing_http_get)

    # 1. Owner A reads Device A -> 200 OK (isolated IoT -> UNKNOWN)
    resp_dev_a = client.get(f"/api/devices/{dev_a_id}", headers=headers_a)
    assert resp_dev_a.status_code == 200
    data = resp_dev_a.json()
    assert data["device_id"] == dev_a_id
    assert data["status"] == "UNKNOWN"
    assert data["presence_status"] == "UNKNOWN"

    # 2. Owner A attempts to read Device B -> 403 Forbidden
    resp_dev_b_attack = client.get(f"/api/devices/{dev_b_id}", headers=headers_a)
    assert resp_dev_b_attack.status_code == 403


def test_m3_technician_dashboard_and_devices_e2e(seeded_multitenant_env, monkeypatch):
    """
    M-3 & L-2 Verification:
    - Technician dashboard does not count UNKNOWN as OFFLINE when IoT service is unreachable.
    - Technician device list & detail return UNKNOWN status when IoT presence is unavailable.
    - Deterministically isolated from any live IoT service running on port 8002 via monkeypatch.
    - Both unreachable (Scenario A) and online presence (Scenario B) are verified deterministically.
    - Tenant isolation & RBAC are preserved:
      * Technician can access actively assigned Farm A devices.
      * Technician cannot access inactive Farm B devices (403 Forbidden).
      * Other users (Owner A) cannot access Technician's dashboard (403 Forbidden).
    """
    client = seeded_multitenant_env["client"]
    headers_a = seeded_multitenant_env["headers_a"]
    headers_tech = seeded_multitenant_env["headers_tech"]
    tech_id = seeded_multitenant_env["tech_id"]
    farm_a_id = seeded_multitenant_env["farm_a_id"]
    farm_b_id = seeded_multitenant_env["farm_b_id"]
    dev_a_id = seeded_multitenant_env["dev_a_id"]
    node_a = seeded_multitenant_env["node_a"]

    from app.repositories.technician_repository import technician_repository

    # Scenario A: IoT service unreachable -> unknown_device_count > 0, offline == 0
    def failing_http_get(url: str, timeout: float):
        raise ConnectionError("Mocked unreachable IoT service for deterministic E2E test")

    monkeypatch.setattr(technician_repository._iot_adapter, "_http_get", failing_http_get)

    # 1. Technician dashboard when IoT service is down
    resp_dash = client.get(f"/api/technicians/{tech_id}/dashboard", headers=headers_tech)
    assert resp_dash.status_code == 200
    dash_data = resp_dash.json()
    assert dash_data["technician_id"] == tech_id
    assert dash_data["assigned_farm_count"] == 1
    assert dash_data["device_count"] == 1
    assert dash_data["online_device_count"] == 0
    assert dash_data["offline_device_count"] == 0  # Crucial M-3: must NOT misreport as offline
    assert dash_data["unknown_device_count"] == 1

    # 2. Technician accesses assigned Farm A devices
    resp_devices = client.get(f"/api/technicians/{tech_id}/farms/{farm_a_id}/devices", headers=headers_tech)
    assert resp_devices.status_code == 200
    devices = resp_devices.json()
    assert len(devices) == 1
    assert devices[0]["device_id"] == dev_a_id
    assert devices[0]["status"] == "UNKNOWN"
    assert devices[0]["mqtt_status"] == "Unknown"

    # 3. Technician accesses assigned Farm A device detail
    resp_dev_detail = client.get(
        f"/api/technicians/{tech_id}/farms/{farm_a_id}/devices/{dev_a_id}",
        headers=headers_tech,
    )
    assert resp_dev_detail.status_code == 200
    dev_data = resp_dev_detail.json()
    assert dev_data["device_id"] == dev_a_id
    assert dev_data["status"] == "UNKNOWN"
    assert dev_data["mqtt_status"] == "Unknown"

    # Scenario B: IoT service is reachable and reports device ONLINE
    def online_http_get(url: str, timeout: float):
        if url.endswith("/api/iot/devices/presence"):
            return 200, [
                {
                    "deviceId": node_a,
                    "status": "ONLINE",
                    "lastSeen": "2026-11-06T12:00:00Z",
                    "uptime": 1200,
                    "ip": "192.168.1.50",
                    "freeHeap": 190000,
                    "mockMode": False,
                }
            ]
        return 404, None

    monkeypatch.setattr(technician_repository._iot_adapter, "_http_get", online_http_get)
    resp_dash_online = client.get(f"/api/technicians/{tech_id}/dashboard", headers=headers_tech)
    assert resp_dash_online.status_code == 200
    dash_online = resp_dash_online.json()
    assert dash_online["online_device_count"] == 1
    assert dash_online["offline_device_count"] == 0
    assert dash_online["unknown_device_count"] == 0

    # 4. RBAC & Tenant Isolation: Technician accesses unassigned/inactive Farm B devices -> 403 Forbidden
    resp_dev_b = client.get(f"/api/technicians/{tech_id}/farms/{farm_b_id}/devices", headers=headers_tech)
    assert resp_dev_b.status_code == 403

    # 5. RBAC: Non-technician / other user (Owner A) cannot access technician's dashboard -> 403 Forbidden
    resp_owner_attack = client.get(f"/api/technicians/{tech_id}/dashboard", headers=headers_a)
    assert resp_owner_attack.status_code == 403

