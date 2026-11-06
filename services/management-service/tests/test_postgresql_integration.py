import uuid
import pytest
from app.config import settings
from app.database import get_connection
from app.repositories.farm_repository import farm_repository
from app.repositories.zone_repository import zone_repository
from app.repositories.device_repository import device_repository
from app.repositories.user_repository import user_repository


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


def test_pg_farm_repository_invalid_and_nonexistent_uuid_does_not_throw_500():
    """Verifies that FarmRepository.get_farm_by_id handles non-UUID and non-existent IDs without throwing PostgreSQL 500."""
    # 1. Non-existent UUID
    random_uuid = str(uuid.uuid4())
    result = farm_repository.get_farm_by_id(random_uuid)
    assert result is None

    # 2. Arbitrary non-UUID string (previously caused PostgreSQL InvalidTextRepresentation 500 error)
    non_uuid_str = "invalid-farm-slug-12345"
    result_non_uuid = farm_repository.get_farm_by_id(non_uuid_str)
    assert result_non_uuid is None

    # 3. Empty string
    assert farm_repository.get_farm_by_id("") is None
    assert farm_repository.get_farm_by_id("   ") is None


def test_pg_zone_repository_invalid_and_nonexistent_ids_safe():
    """Verifies that ZoneRepository handles non-UUID farm_id and zone_id without PostgreSQL crash."""
    # 1. Non-UUID farm_id in list_zones_by_farm
    zones = zone_repository.list_zones_by_farm("invalid-farm-code")
    assert isinstance(zones, list)

    # 2. Non-UUID zone_id in get_zone_by_id
    zone = zone_repository.get_zone_by_id("invalid-zone-code")
    assert zone is None


def test_pg_user_repository_farm_exists_safe():
    """Verifies that UserRepository.farm_exists handles non-UUID strings safely."""
    assert user_repository.farm_exists("invalid-farm-id-not-uuid") is False
    assert user_repository.farm_exists(str(uuid.uuid4())) is False
    assert user_repository.farm_exists("") is False


def test_pg_farm_tenant_isolation_live():
    """Verifies tenant isolation queries directly on PostgreSQL."""
    # 1. Anonymous / None fails closed
    assert farm_repository.list_farms(None) == []
    assert farm_repository.list_farms({}) == []
    assert farm_repository.list_farms({"id": "fake", "roles": []}) == []

    # 2. Admin user can query without SQL syntax error
    admin_user = {"id": str(uuid.uuid4()), "roles": ["ADMIN"]}
    admin_farms = farm_repository.list_farms(admin_user)
    assert isinstance(admin_farms, list)

    # 3. Farm owner only queries farms where owner_id matches
    owner_user = {"id": str(uuid.uuid4()), "roles": ["FARM_OWNER"]}
    owner_farms = farm_repository.list_farms(owner_user)
    assert isinstance(owner_farms, list)
    # Since random UUID owns no farms, list must be empty
    assert len(owner_farms) == 0

    # 4. Technician only queries assigned farms
    tech_user = {"id": str(uuid.uuid4()), "roles": ["TECHNICIAN"]}
    tech_farms = farm_repository.list_farms(tech_user)
    assert isinstance(tech_farms, list)
    assert len(tech_farms) == 0


def test_pg_device_repository_safe_lookup():
    """Verifies device_repository lookup handles non-UUID node IDs safely."""
    dev = device_repository.get_device_by_id("ESP32-NONEXISTENT")
    assert dev is None
    dev_uuid = device_repository.get_device_by_id(str(uuid.uuid4()))
    assert dev_uuid is None
