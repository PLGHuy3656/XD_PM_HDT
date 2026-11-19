from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
import pytest

from app.config import settings
from app.core.dependencies import (
    check_technician_permission,
    get_current_user,
    require_admin,
    require_device_access,
    require_farm_access,
    require_roles,
    require_zone_access,
    verify_farm_resource_access,
)
from app.core.security import create_access_token


@pytest.fixture(autouse=True)
def setup_jwt_secret():
    old_secret = settings.jwt_secret
    if not settings.jwt_secret:
        settings.jwt_secret = "test_jwt_secret_key_for_unit_tests_32_bytes_long"
    yield
    settings.jwt_secret = old_secret


def test_get_current_user_missing_credentials():
    with pytest.raises(HTTPException) as exc:
        get_current_user(None)
    assert exc.value.status_code == 401
    assert "Authentication required" in exc.value.detail


def test_get_current_user_invalid_token():
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid.token.here")
    with pytest.raises(HTTPException) as exc:
        get_current_user(creds)
    assert exc.value.status_code == 401


def test_get_current_user_nonexistent_user(monkeypatch):
    token = create_access_token(subject="nonexistent-uuid", roles=["ADMIN"])
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    from app.services.auth_service import auth_service
    monkeypatch.setattr(auth_service, "get_user_by_id", lambda uid: None)

    with pytest.raises(HTTPException) as exc:
        get_current_user(creds)
    assert exc.value.status_code == 401
    assert "User account not found or inactive" in exc.value.detail


def test_get_current_user_valid(monkeypatch):
    token = create_access_token(subject="user-123", roles=["TECHNICIAN"])
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    mock_user = {
        "id": "user-123",
        "email": "tech@nestmate.dev",
        "full_name": "Nguyen Van Technician",
        "roles": ["TECHNICIAN"],
    }
    from app.services.auth_service import auth_service
    monkeypatch.setattr(auth_service, "get_user_by_id", lambda uid: mock_user)

    user = get_current_user(creds)
    assert user["id"] == "user-123"
    assert "TECHNICIAN" in user["roles"]


def test_require_roles_allowed():
    checker = require_roles("ADMIN", "TECHNICIAN")
    user = {"id": "user-1", "roles": ["TECHNICIAN"]}
    assert checker(current_user=user) == user


def test_require_roles_forbidden():
    checker = require_roles("ADMIN")
    user = {"id": "user-1", "roles": ["TECHNICIAN"]}
    with pytest.raises(HTTPException) as exc:
        checker(current_user=user)
    assert exc.value.status_code == 403
    assert "Insufficient role permissions" in exc.value.detail


def test_require_admin():
    admin_checker = require_admin
    admin_user = {"id": "admin-1", "roles": ["ADMIN"]}
    assert admin_checker(current_user=admin_user) == admin_user

    non_admin = {"id": "user-1", "roles": ["TECHNICIAN"]}
    with pytest.raises(HTTPException) as exc:
        admin_checker(current_user=non_admin)
    assert exc.value.status_code == 403


def test_resource_access_admin_allowed():
    admin_user = {"id": "admin-1", "roles": ["ADMIN"]}
    assert verify_farm_resource_access(admin_user, "any-farm-id") is True


def test_resource_access_technician_assigned(monkeypatch):
    from app.repositories.user_repository import user_repository
    monkeypatch.setattr(
        user_repository,
        "is_farm_assigned_to_technician",
        lambda tech_id, farm_id: farm_id == "assigned-farm-01",
    )

    tech_user = {"id": "tech-01", "roles": ["TECHNICIAN"]}

    # Assigned farm -> Allowed
    assert verify_farm_resource_access(tech_user, "assigned-farm-01") is True

    # Unassigned farm -> 403 Forbidden
    with pytest.raises(HTTPException) as exc:
        verify_farm_resource_access(tech_user, "unassigned-farm-99")
    assert exc.value.status_code == 403
    assert "Farm not assigned to technician" in exc.value.detail


def test_owner_accesses_own_farm(monkeypatch):
    from app.repositories.user_repository import user_repository
    monkeypatch.setattr(
        user_repository,
        "is_farm_owned_by_user",
        lambda user_id, farm_id: farm_id == "farm-owned-by-me" and user_id == "owner-me",
    )

    owner_user = {"id": "owner-me", "roles": ["FARM_OWNER"]}
    assert verify_farm_resource_access(owner_user, "farm-owned-by-me") is True


def test_owner_accesses_other_owners_farm_forbidden(monkeypatch):
    from app.repositories.user_repository import user_repository
    monkeypatch.setattr(
        user_repository,
        "is_farm_owned_by_user",
        lambda user_id, farm_id: False,
    )

    owner_user = {"id": "owner-me", "roles": ["FARM_OWNER"]}
    with pytest.raises(HTTPException) as exc:
        verify_farm_resource_access(owner_user, "farm-owned-by-other")
    assert exc.value.status_code == 403
    assert "Farm not owned by user" in exc.value.detail


def test_owner_accesses_farm_with_owner_null_forbidden(monkeypatch):
    from app.repositories.user_repository import user_repository
    # When farm.owner_id is NULL, is_farm_owned_by_user returns False
    monkeypatch.setattr(
        user_repository,
        "is_farm_owned_by_user",
        lambda user_id, farm_id: False,
    )

    owner_user = {"id": "owner-me", "roles": ["FARM_OWNER"]}
    with pytest.raises(HTTPException) as exc:
        verify_farm_resource_access(owner_user, "farm-with-null-owner")
    assert exc.value.status_code == 403
    assert "Farm not owned by user" in exc.value.detail


def test_owner_accesses_zone_in_own_farm(monkeypatch):
    from app.repositories.user_repository import user_repository
    monkeypatch.setattr(
        user_repository,
        "get_farm_id_for_zone",
        lambda zid: "farm-owned" if zid == "zone-owned" else "farm-other",
    )
    monkeypatch.setattr(
        user_repository,
        "is_farm_owned_by_user",
        lambda uid, fid: fid == "farm-owned" and uid == "owner-01",
    )

    owner_user = {"id": "owner-01", "roles": ["FARM_OWNER"]}
    # Zone in own farm -> Allowed
    assert require_zone_access("zone-owned", current_user=owner_user) == "zone-owned"

    # Zone in other owner's farm -> 403 Forbidden
    with pytest.raises(HTTPException) as exc:
        require_zone_access("zone-other", current_user=owner_user)
    assert exc.value.status_code == 403


def test_owner_accesses_device_in_own_farm(monkeypatch):
    from app.repositories.user_repository import user_repository
    monkeypatch.setattr(
        user_repository,
        "get_farm_id_for_device",
        lambda did: "farm-owned" if did == "dev-owned" else "farm-other",
    )
    monkeypatch.setattr(
        user_repository,
        "is_farm_owned_by_user",
        lambda uid, fid: fid == "farm-owned" and uid == "owner-01",
    )

    owner_user = {"id": "owner-01", "roles": ["FARM_OWNER"]}
    # Device in own farm -> Allowed
    assert require_device_access("dev-owned", current_user=owner_user) == "dev-owned"

    # Device in other farm -> 403 Forbidden
    with pytest.raises(HTTPException) as exc:
        require_device_access("dev-other", current_user=owner_user)
    assert exc.value.status_code == 403


def test_nested_zone_access_technician(monkeypatch):
    from app.repositories.user_repository import user_repository
    monkeypatch.setattr(
        user_repository,
        "get_farm_id_for_zone",
        lambda zid: "farm-01" if zid == "zone-01" else None,
    )
    monkeypatch.setattr(
        user_repository,
        "is_farm_assigned_to_technician",
        lambda tid, fid: fid == "farm-01",
    )

    tech_user = {"id": "tech-01", "roles": ["TECHNICIAN"]}

    # Valid zone in assigned farm -> Allowed
    assert require_zone_access("zone-01", current_user=tech_user) == "zone-01"

    # Non-existent zone -> 404 Not Found
    with pytest.raises(HTTPException) as exc:
        require_zone_access("nonexistent-zone", current_user=tech_user)
    assert exc.value.status_code == 404


def test_nested_device_access_technician(monkeypatch):
    from app.repositories.user_repository import user_repository
    monkeypatch.setattr(
        user_repository,
        "get_farm_id_for_device",
        lambda did: "farm-01" if did == "ESP32-001" else None,
    )
    monkeypatch.setattr(
        user_repository,
        "is_farm_assigned_to_technician",
        lambda tid, fid: fid == "farm-01",
    )

    tech_user = {"id": "tech-01", "roles": ["TECHNICIAN"]}

    # Valid device in assigned farm -> Allowed
    assert require_device_access("ESP32-001", current_user=tech_user) == "ESP32-001"

    # Non-existent device -> 404 Not Found
    with pytest.raises(HTTPException) as exc:
        require_device_access("unknown-device", current_user=tech_user)
    assert exc.value.status_code == 404


def test_check_technician_permission(monkeypatch):
    from app.repositories.user_repository import user_repository
    monkeypatch.setattr(
        user_repository,
        "is_farm_assigned_to_technician",
        lambda tid, fid: fid == "farm-01",
    )

    assert check_technician_permission("tech-01", "farm-01", "MONITOR") is True
    assert check_technician_permission("tech-01", "farm-02", "OPERATE") is False
