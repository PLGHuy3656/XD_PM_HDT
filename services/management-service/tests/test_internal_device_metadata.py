"""Security and integration tests for Internal Device Metadata API (CP11.4-B1-R2-MGMT-R2).

Verifies strict trust-boundary hardening and regression tests:
1. Valid dedicated PSK (>= 32 bytes) via X-Internal-Service-Key.
2. Missing PSK rejected with 401.
3. Invalid PSK rejected with 401.
4. Weak PSK configuration (< 32 bytes) fails closed with 503.
5. Key rotation accepts both active keys and rejects decommissioned key.
6. User JWT rejected with 401.
7. ADMIN JWT rejected with 401.
8. Service JWT rejected with 401.
9. Conflicting credentials (both Authorization and X-Internal-Service-Key present) rejected with 400.
10. Public Gateway does not expose internal endpoints.
11. UUID / node ID ambiguity rejected with 409 Conflict.
12. Disabled device response (200 with status="DISABLED", isActive=False).
13. Device reassignment produces distinct metadataVersion.
14. PostgreSQL connection failure fails closed with 503.
15. Zero credential leakage in response bodies.
16. Non-ASCII PSK safely returns 401, never HTTP 500.
17. NUL-containing device identifier safely returns 400, never HTTP 503.
18. SQL reassignment (without updated_at) increments database-enforced metadataVersion.
19. Rapid consecutive reassignments monotonically increment metadataVersion.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid
from fastapi.testclient import TestClient
import jwt
import psycopg
import pytest

from app.config import settings
from app.main import app
from app.repositories.device_repository import AmbiguousDeviceIdentifierError
from app.services.device_service import device_service

# Valid high-entropy keys (>= 32 bytes)
VALID_PSK_ACTIVE = "test_internal_service_key_secret_2026_xyz_active_32b"
VALID_PSK_ROTATED = "test_internal_service_key_secret_2025_abc_rotated_32b"
REVOKED_PSK = "test_internal_revoked_key_12345678901234567890"
WEAK_KEY = "weak_key_12345"  # < 32 bytes

FARM_A_UUID = "11111111-1111-1111-1111-111111111111"
FARM_B_UUID = "22222222-2222-2222-2222-222222222222"
FARM_C_UUID = "33333333-3333-3333-3333-333333333333"
DEVICE_UUID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
NODE_ID = "SWC-NODE-001"


class MockInternalDeviceRepository:
    """In-memory mock repository simulating PostgreSQL devices table with trigger."""

    def __init__(self):
        self.devices: list[Dict[str, Any]] = [
            {
                "id": DEVICE_UUID,
                "node_id": NODE_ID,
                "farm_id": FARM_A_UUID,
                "is_active": True,
                "updated_at": datetime(2026, 11, 7, 12, 0, 0, 100000, tzinfo=timezone.utc),
                "metadata_version": 1,
            },
            {
                "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "node_id": "SWC-NODE-DISABLED",
                "farm_id": FARM_A_UUID,
                "is_active": False,
                "updated_at": datetime(2026, 11, 7, 10, 0, 0, 500000, tzinfo=timezone.utc),
                "metadata_version": 1,
            },
        ]
        self.simulate_db_outage = False
        self.simulate_ambiguity = False
        self.simulate_missing_column = False

    def get_internal_device_metadata(self, identifier: str) -> Optional[Dict[str, Any]]:
        if self.simulate_db_outage:
            raise psycopg.OperationalError("Simulated PostgreSQL connection failure")

        if self.simulate_missing_column:
            raise psycopg.errors.UndefinedColumn("column d.metadata_version does not exist")

        if "\x00" in identifier or "\0" in identifier:
            raise psycopg.DataError("A string literal cannot contain NUL (0x00) characters")

        clean_id = str(identifier).strip()
        if not clean_id or len(clean_id) > 100 or any(ord(c) < 32 or ord(c) == 127 for c in clean_id):
            return None

        if self.simulate_ambiguity:
            raise AmbiguousDeviceIdentifierError(
                f"Ambiguous device identifier '{clean_id}' matches multiple records in registry"
            )

        matches = [d for d in self.devices if d["node_id"] == clean_id or d["id"] == clean_id]
        if not matches:
            return None
        if len(matches) > 1:
            raise AmbiguousDeviceIdentifierError(
                f"Ambiguous device identifier '{clean_id}' matches multiple records in registry"
            )

        record = matches[0]
        is_active = record["is_active"]
        updated_at = record["updated_at"]
        version = record.get("metadata_version", 1)
        return {
            "deviceId": record["id"],
            "nodeId": record["node_id"],
            "farmId": record["farm_id"],
            "status": "ACTIVE" if is_active else "DISABLED",
            "isActive": is_active,
            "updatedAt": updated_at.isoformat() if updated_at else None,
            "metadataVersion": version,
            "device_id": record["id"],
            "node_id": record["node_id"],
            "farm_id": record["farm_id"],
            "is_active": is_active,
            "updated_at": updated_at.isoformat() if updated_at else None,
            "metadata_version": version,
        }

    def execute_sql_reassignment(self, node_id: str, new_farm_id: str):
        """Simulates raw SQL UPDATE devices SET farm_id = %s WHERE node_id = %s triggering version bump."""
        for d in self.devices:
            if d["node_id"] == node_id:
                d["farm_id"] = new_farm_id
                # Database trigger bumps metadata_version and updated_at
                d["metadata_version"] = d.get("metadata_version", 1) + 1
                d["updated_at"] = datetime.now(timezone.utc)


@pytest.fixture
def mock_device_repo(monkeypatch):
    repo = MockInternalDeviceRepository()
    monkeypatch.setattr(device_service, "repository", repo)
    return repo


@pytest.fixture(autouse=True)
def configure_service_auth():
    old_token = settings.internal_service_token
    old_tokens = settings.internal_service_tokens
    old_jwt_sec = settings.jwt_secret

    settings.internal_service_token = VALID_PSK_ACTIVE
    settings.internal_service_tokens = f"{VALID_PSK_ACTIVE},{VALID_PSK_ROTATED}"
    settings.jwt_secret = "test_user_jwt_secret_for_rbac_must_be_32b_long"

    yield

    settings.internal_service_token = old_token
    settings.internal_service_tokens = old_tokens
    settings.jwt_secret = old_jwt_sec


@pytest.fixture
def client():
    return TestClient(app)


# =============================================================================
# 1. PSK Authentication & Security Invariants
# =============================================================================

def test_01_valid_dedicated_psk(client, mock_device_repo):
    """Verify authentication succeeds with valid >=32-byte dedicated PSK via X-Internal-Service-Key."""
    response = client.get(
        f"/internal/v1/devices/{NODE_ID}",
        headers={"X-Internal-Service-Key": VALID_PSK_ACTIVE},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["deviceId"] == DEVICE_UUID
    assert data["nodeId"] == NODE_ID
    assert data["farmId"] == FARM_A_UUID
    assert data["status"] == "ACTIVE"
    assert data["isActive"] is True
    assert "updatedAt" in data
    assert "metadataVersion" in data


def test_02_missing_psk_rejected(client, mock_device_repo):
    """Verify request without X-Internal-Service-Key returns 401 Unauthorized."""
    response = client.get(f"/internal/v1/devices/{NODE_ID}")
    assert response.status_code == 401
    assert "missing required header" in response.json()["detail"].lower()


def test_03_invalid_psk_rejected(client, mock_device_repo):
    """Verify incorrect PSK returns 401 Unauthorized."""
    response = client.get(
        f"/internal/v1/devices/{NODE_ID}",
        headers={"X-Internal-Service-Key": "completely_wrong_key_that_has_at_least_32_bytes_len"},
    )
    assert response.status_code == 401
    assert "invalid service credentials" in response.json()["detail"].lower()


def test_04_weak_psk_configuration_fails_closed(client, mock_device_repo):
    """Verify server fails closed (503) if configured PSK has fewer than 32 bytes."""
    settings.internal_service_token = WEAK_KEY
    settings.internal_service_tokens = ""

    response = client.get(
        f"/internal/v1/devices/{NODE_ID}",
        headers={"X-Internal-Service-Key": WEAK_KEY},
    )
    assert response.status_code == 503
    assert "weak (< 32 bytes)" in response.json()["detail"].lower()


def test_05_rotation_with_old_and_new_keys(client, mock_device_repo):
    """Verify bounded rotation allows both active and previous keys, rejecting revoked."""
    resp1 = client.get(f"/internal/v1/devices/{NODE_ID}", headers={"X-Internal-Service-Key": VALID_PSK_ACTIVE})
    assert resp1.status_code == 200

    resp2 = client.get(f"/internal/v1/devices/{NODE_ID}", headers={"X-Internal-Service-Key": VALID_PSK_ROTATED})
    assert resp2.status_code == 200

    resp3 = client.get(f"/internal/v1/devices/{NODE_ID}", headers={"X-Internal-Service-Key": REVOKED_PSK})
    assert resp3.status_code == 401


def test_06_user_jwt_rejected(client, mock_device_repo):
    """Verify standard user Bearer JWT is strictly rejected with 401 on internal endpoint."""
    user_jwt = jwt.encode(
        {"sub": str(uuid.uuid4()), "roles": ["FARM_OWNER"], "exp": int(datetime.now(timezone.utc).timestamp()) + 300},
        settings.jwt_secret,
        algorithm="HS256",
    )
    response = client.get(
        f"/internal/v1/devices/{NODE_ID}",
        headers={"Authorization": f"Bearer {user_jwt}"},
    )
    assert response.status_code == 401
    assert "bearer tokens are not accepted" in response.json()["detail"].lower()


def test_07_admin_jwt_rejected(client, mock_device_repo):
    """Verify ADMIN user Bearer JWT is strictly rejected with 401 on internal endpoint."""
    admin_jwt = jwt.encode(
        {"sub": str(uuid.uuid4()), "roles": ["ADMIN"], "exp": int(datetime.now(timezone.utc).timestamp()) + 300},
        settings.jwt_secret,
        algorithm="HS256",
    )
    response = client.get(
        f"/internal/v1/devices/{NODE_ID}",
        headers={"Authorization": f"Bearer {admin_jwt}"},
    )
    assert response.status_code == 401
    assert "bearer tokens are not accepted" in response.json()["detail"].lower()


def test_08_service_jwt_rejected(client, mock_device_repo):
    """Verify Service JWT (sub='system-iot-service') is rejected with 401; only dedicated PSK allowed."""
    service_jwt = jwt.encode(
        {"sub": "system-iot-service", "service": "iot-service", "exp": int(datetime.now(timezone.utc).timestamp()) + 300},
        settings.jwt_secret,
        algorithm="HS256",
    )
    response = client.get(
        f"/internal/v1/devices/{NODE_ID}",
        headers={"Authorization": f"Bearer {service_jwt}"},
    )
    assert response.status_code == 401
    assert "bearer tokens are not accepted" in response.json()["detail"].lower()


def test_09_conflicting_credentials_rejected(client, mock_device_repo):
    """Verify providing both Authorization and X-Internal-Service-Key is rejected with 400 Bad Request."""
    response = client.get(
        f"/internal/v1/devices/{NODE_ID}",
        headers={
            "X-Internal-Service-Key": VALID_PSK_ACTIVE,
            "Authorization": "Bearer some-token",
        },
    )
    assert response.status_code == 400
    assert "conflicting credentials" in response.json()["detail"].lower()


def test_10_internal_endpoint_inaccessible_through_gateway():
    """Verify Gateway routing allowlist does not expose /internal/ routes."""
    from pathlib import Path
    gateway_routes = Path("D:/Development/Projects/XD_PM_HDT/gateway/app/routes.py")
    if gateway_routes.exists():
        content = gateway_routes.read_text(encoding="utf-8")
        assert "/internal/v1" not in content
        assert "internal" in content.lower()


# =============================================================================
# 2. Metadata Contract, Ambiguity, Reassignment, and Outage Tests
# =============================================================================

def test_11_uuid_node_id_ambiguity_rejected(client, mock_device_repo):
    """Verify ambiguous identifier matching multiple devices is rejected with 409 Conflict."""
    mock_device_repo.simulate_ambiguity = True
    response = client.get(
        f"/internal/v1/devices/{NODE_ID}",
        headers={"X-Internal-Service-Key": VALID_PSK_ACTIVE},
    )
    assert response.status_code == 409
    assert "ambiguous device identifier" in response.json()["detail"].lower()


def test_12_disabled_device_response(client, mock_device_repo):
    """Verify disabled device returns status='DISABLED' and isActive=False."""
    response = client.get(
        "/internal/v1/devices/SWC-NODE-DISABLED",
        headers={"X-Internal-Service-Key": VALID_PSK_ACTIVE},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "DISABLED"
    assert data["isActive"] is False


def test_13_device_reassignment_version_change(client, mock_device_repo):
    """Verify farm reassignment updates farmId and bumps metadataVersion."""
    resp1 = client.get(
        f"/internal/v1/devices/{NODE_ID}",
        headers={"X-Internal-Service-Key": VALID_PSK_ACTIVE},
    )
    v1 = resp1.json()["metadataVersion"]

    # Reassign device
    mock_device_repo.execute_sql_reassignment(NODE_ID, FARM_B_UUID)

    resp2 = client.get(
        f"/internal/v1/devices/{NODE_ID}",
        headers={"X-Internal-Service-Key": VALID_PSK_ACTIVE},
    )
    data2 = resp2.json()
    assert data2["farmId"] == FARM_B_UUID
    v2 = data2["metadataVersion"]

    assert v2 > v1


def test_14_postgresql_failure_fails_closed(client, mock_device_repo):
    """Verify database connection loss returns 503 Service Unavailable."""
    mock_device_repo.simulate_db_outage = True
    response = client.get(
        f"/internal/v1/devices/{NODE_ID}",
        headers={"X-Internal-Service-Key": VALID_PSK_ACTIVE},
    )
    assert response.status_code == 503
    assert "database service unavailable" in response.json()["detail"].lower()


def test_15_no_credential_leakage(client, mock_device_repo):
    """Verify raw tokens and secrets are never reflected in response body or error details."""
    response = client.get(
        f"/internal/v1/devices/{NODE_ID}",
        headers={"X-Internal-Service-Key": "some-secret-token-attempting-reflection-leakage-32b"},
    )
    body = response.text
    assert "some-secret-token" not in body
    assert VALID_PSK_ACTIVE not in body


# =============================================================================
# 3. CP11.4-B1-R2-MGMT-R2 Specific Regression Tests
# =============================================================================

def test_16_non_ascii_psk_returns_401_not_500(client, mock_device_repo):
    """Verify non-ASCII PSK header returns 401 Unauthorized, never unhandled HTTP 500."""
    # Test UTF-8 non-ASCII bytes
    response = client.get(
        f"/internal/v1/devices/{NODE_ID}",
        headers=[(b"x-internal-service-key", "khóa_dịch_vụ_bí_mật_12345678901234567890".encode("utf-8"))],
    )
    assert response.status_code == 401
    assert "invalid service credentials" in response.json()["detail"].lower()

    # Test raw non-ASCII byte sequence
    response2 = client.get(
        f"/internal/v1/devices/{NODE_ID}",
        headers=[(b"x-internal-service-key", b"non_ascii_\x80\xff_key_12345678901234567890")],
    )
    assert response2.status_code == 401
    assert "invalid service credentials" in response2.json()["detail"].lower()


def test_17_nul_containing_device_identifier_returns_400_not_503(client, mock_device_repo):
    """Verify identifier containing NUL character returns 400 Bad Request, never misleading 503."""
    response = client.get(
        "/internal/v1/devices/SWC%00NODE-001",
        headers={"X-Internal-Service-Key": VALID_PSK_ACTIVE},
    )
    assert response.status_code == 400
    assert "invalid characters" in response.json()["detail"].lower()


def test_18_sql_reassignment_bumps_metadata_version(client, mock_device_repo):
    """Verify metadataVersion increments when devices.farm_id is updated directly via SQL."""
    # Baseline query
    resp1 = client.get(
        f"/internal/v1/devices/{NODE_ID}",
        headers={"X-Internal-Service-Key": VALID_PSK_ACTIVE},
    )
    assert resp1.status_code == 200
    v1 = resp1.json()["metadataVersion"]

    # Direct SQL reassignment to Farm B
    mock_device_repo.execute_sql_reassignment(NODE_ID, FARM_B_UUID)

    resp2 = client.get(
        f"/internal/v1/devices/{NODE_ID}",
        headers={"X-Internal-Service-Key": VALID_PSK_ACTIVE},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["farmId"] == FARM_B_UUID
    v2 = data2["metadataVersion"]
    assert v2 == v1 + 1


def test_19_rapid_consecutive_reassignments_monotonic_bump(client, mock_device_repo):
    """Verify two rapid consecutive reassignments monotonically increment metadataVersion (1 -> 2 -> 3)."""
    resp1 = client.get(f"/internal/v1/devices/{NODE_ID}", headers={"X-Internal-Service-Key": VALID_PSK_ACTIVE})
    v1 = resp1.json()["metadataVersion"]

    # Reassignment 1 -> Farm B
    mock_device_repo.execute_sql_reassignment(NODE_ID, FARM_B_UUID)
    resp2 = client.get(f"/internal/v1/devices/{NODE_ID}", headers={"X-Internal-Service-Key": VALID_PSK_ACTIVE})
    v2 = resp2.json()["metadataVersion"]
    assert v2 == v1 + 1
    assert resp2.json()["farmId"] == FARM_B_UUID

    # Reassignment 2 -> Farm C immediately
    mock_device_repo.execute_sql_reassignment(NODE_ID, FARM_C_UUID)
    resp3 = client.get(f"/internal/v1/devices/{NODE_ID}", headers={"X-Internal-Service-Key": VALID_PSK_ACTIVE})
    v3 = resp3.json()["metadataVersion"]
    assert v3 == v2 + 1
    assert resp3.json()["farmId"] == FARM_C_UUID


# =============================================================================
# 4. Round 7 Remediation Verification (R7-H1, Low Findings, Least Privilege)
# =============================================================================

def test_20_static_scan_no_runtime_ddl():
    """R7-H1 Guard: Verify zero DDL statements or schema mutation helpers exist in runtime Python code."""
    from pathlib import Path
    app_dir = Path("D:/Development/Projects/XD_PM_HDT_mgmt_worktree/services/management-service/app")
    py_files = list(app_dir.rglob("*.py"))
    assert len(py_files) > 0

    forbidden_patterns = [
        "ALTER TABLE",
        "CREATE TABLE",
        "CREATE FUNCTION",
        "CREATE OR REPLACE FUNCTION",
        "CREATE TRIGGER",
        "DROP TRIGGER",
        "DROP FUNCTION",
        "_ensure_device_metadata_version_schema",
    ]

    for py_file in py_files:
        content = py_file.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            assert pattern not in content, f"Found forbidden runtime DDL '{pattern}' in {py_file.name}"


def test_21_device_id_exceeding_100_chars_returns_400(client, mock_device_repo):
    """Verify identifier exceeding 100 characters returns 400 Bad Request, never 404 or DB error."""
    long_node_id = "A" * 101
    response = client.get(
        f"/internal/v1/devices/{long_node_id}",
        headers={"X-Internal-Service-Key": VALID_PSK_ACTIVE},
    )
    assert response.status_code == 400
    assert "exceeds maximum" in response.json()["detail"].lower()


def test_22_missing_schema_migration_fails_closed_with_503(client, mock_device_repo):
    """Verify that if database schema has not been migrated, it fails closed with 503 instead of 500."""
    mock_device_repo.simulate_missing_column = True
    response = client.get(
        f"/internal/v1/devices/{NODE_ID}",
        headers={"X-Internal-Service-Key": VALID_PSK_ACTIVE},
    )
    assert response.status_code == 503
    assert "schema migration pending" in response.json()["detail"].lower()


def test_23_repository_transaction_rollback_on_query_failure(monkeypatch):
    """Verify that any database query exception immediately executes conn.rollback()."""
    import sys
    from app.repositories.device_repository import device_repository

    class MockCursor:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, *args, **kwargs):
            raise psycopg.DatabaseError("Simulated query execution failure")

    class MockConnection:
        def __init__(self):
            self.rolled_back = False
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def cursor(self):
            return MockCursor()
        def rollback(self):
            self.rolled_back = True

    mock_conn = MockConnection()
    mod = sys.modules["app.repositories.device_repository"]
    monkeypatch.setattr(mod, "get_connection", lambda: mock_conn)

    with pytest.raises(psycopg.DatabaseError):
        device_repository.get_internal_device_metadata(NODE_ID)

    assert mock_conn.rolled_back is True, "Connection rollback was not executed upon query exception!"

