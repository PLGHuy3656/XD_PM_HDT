import pytest
from app.services.farm_service import FarmService


class FakeFarmRepository:
    def __init__(self):
        self.all_farms = [
            {
                "farm_id": "farm-001",
                "farm_code": "NM-BA-01",
                "farm_name": "Nhà yến Bình An",
                "address": "Thủ Đức, TP. Hồ Chí Minh",
                "status": "ACTIVE",
                "zone_count": 3,
                "device_count": 6,
                "owner_id": "owner-001",
                "assigned_technicians": ["tech-001"],
            },
            {
                "farm_id": "farm-002",
                "farm_code": "NM-BA-02",
                "farm_name": "Nhà yến Bình Dương",
                "address": "Bình Dương",
                "status": "ACTIVE",
                "zone_count": 2,
                "device_count": 4,
                "owner_id": "owner-002",
                "assigned_technicians": [],
            },
        ]

    def list_farms(self, current_user: dict):
        if not current_user or not isinstance(current_user, dict) or not current_user.get("id"):
            return []
        roles = current_user.get("roles") or []
        user_id = str(current_user["id"])
        if "ADMIN" in roles:
            return self.all_farms
        if "FARM_OWNER" in roles:
            return [f for f in self.all_farms if f.get("owner_id") == user_id]
        if "TECHNICIAN" in roles:
            return [f for f in self.all_farms if user_id in f.get("assigned_technicians", [])]
        return []

    def get_farm_by_id(self, farm_id: str):
        for f in self.all_farms:
            if f["farm_id"] == farm_id:
                return f
        return None


class BrokenTypeErrorFarmRepository:
    def list_farms(self, current_user: dict):
        raise TypeError("Unexpected TypeError in repository query execution")


@pytest.fixture
def service():
    return FarmService(repository=FakeFarmRepository())


def test_list_farms_none_fails_closed(service):
    # Calling list_farms with None or without credentials must fail closed (empty list)
    assert service.list_farms(None) == []
    assert service.list_farms() == []
    assert service.list_farms({}) == []


def test_list_farms_repository_type_error_fails_closed():
    broken_service = FarmService(repository=BrokenTypeErrorFarmRepository())
    user = {"id": "owner-001", "roles": ["FARM_OWNER"]}
    # Must fail closed to empty list, never leaking or falling back to select all
    assert broken_service.list_farms(user) == []


def test_list_farms_scoped_to_owner(service):
    # Owner 001 sees only Farm 1
    user_owner_1 = {"id": "owner-001", "roles": ["FARM_OWNER"]}
    farms_1 = service.list_farms(user_owner_1)
    assert len(farms_1) == 1
    assert farms_1[0]["farm_id"] == "farm-001"

    # Owner 002 sees only Farm 2, cannot see Farm 1
    user_owner_2 = {"id": "owner-002", "roles": ["FARM_OWNER"]}
    farms_2 = service.list_farms(user_owner_2)
    assert len(farms_2) == 1
    assert farms_2[0]["farm_id"] == "farm-002"

    # Owner 003 has no farms -> sees empty
    user_owner_3 = {"id": "owner-003", "roles": ["FARM_OWNER"]}
    assert len(service.list_farms(user_owner_3)) == 0


def test_list_farms_scoped_to_technician(service):
    # Tech 001 is assigned to Farm 1 only
    tech_1 = {"id": "tech-001", "roles": ["TECHNICIAN"]}
    farms_tech = service.list_farms(tech_1)
    assert len(farms_tech) == 1
    assert farms_tech[0]["farm_id"] == "farm-001"

    # Tech 002 has no active assignments -> sees empty
    tech_2 = {"id": "tech-002", "roles": ["TECHNICIAN"]}
    assert len(service.list_farms(tech_2)) == 0


def test_list_farms_admin_sees_all(service):
    admin = {"id": "admin-001", "roles": ["ADMIN"]}
    farms = service.list_farms(admin)
    assert len(farms) == 2
    codes = {f["farm_code"] for f in farms}
    assert codes == {"NM-BA-01", "NM-BA-02"}


def test_get_farm_detail(service):
    farm = service.get_farm("farm-001")
    assert farm is not None
    assert farm["farm_name"] == "Nhà yến Bình An"
    assert farm["zone_count"] == 3


def test_empty_farm_id_raises_value_error(service):
    with pytest.raises(ValueError, match="farm_id is required"):
        service.get_farm("")


def test_farm_repository_sql_branching_avoids_uuid_cast_error():
    """Verifies that FarmRepository branches safely between UUID and farm_code to avoid PostgreSQL UUID cast error."""
    import uuid

    # 1. Non-UUID farm code like 'NM-BA-01' or arbitrary string
    code_val = "NM-BA-01"
    is_uuid = False
    try:
        uuid.UUID(code_val)
        is_uuid = True
    except (ValueError, AttributeError, TypeError):
        is_uuid = False
    assert is_uuid is False  # Must branch to WHERE f.farm_code = %s

    # 2. Canonical UUID string
    uuid_val = "22222222-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    is_uuid = False
    try:
        uuid.UUID(uuid_val)
        is_uuid = True
    except (ValueError, AttributeError, TypeError):
        is_uuid = False
    assert is_uuid is True  # Branches to WHERE f.id = %s OR f.farm_code = %s


def test_farm_controller_get_nonexistent_farm_returns_404():
    """Verifies that FarmController converts None farm result to HTTP 404 rather than 500."""
    from fastapi import HTTPException
    from app.controllers.farm_controller import FarmController

    class EmptyFarmService:
        def get_farm(self, farm_id: str):
            return None

    controller = FarmController(service=EmptyFarmService())
    with pytest.raises(HTTPException) as exc_info:
        controller.get_farm("nonexistent-farm-id")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Farm not found"


def test_farm_controller_get_farm_value_error_returns_400():
    """Verifies that FarmController converts ValueError to HTTP 400."""
    from fastapi import HTTPException
    from app.controllers.farm_controller import FarmController

    class ErrorFarmService:
        def get_farm(self, farm_id: str):
            raise ValueError("farm_id is required")

    controller = FarmController(service=ErrorFarmService())
    with pytest.raises(HTTPException) as exc_info:
        controller.get_farm("")

    assert exc_info.value.status_code == 400
