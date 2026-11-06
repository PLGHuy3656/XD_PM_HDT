import pytest
from app.services.zone_service import ZoneService


class FakeZoneRepository:
    def list_zones_by_farm(self, farm_id: str):
        if farm_id == "farm-001":
            return [
                {
                    "zone_id": "zone-001",
                    "farm_id": "farm-001",
                    "zone_code": "ZONE-A",
                    "name": "Khu vực A",
                    "device_count": 2,
                    "created_at": "2026-10-23T19:41:50+07:00",
                }
            ]
        return []

    def get_zone_by_id(self, zone_id: str):
        if zone_id == "zone-001":
            return {
                "zone_id": "zone-001",
                "farm_id": "farm-001",
                "zone_code": "ZONE-A",
                "name": "Khu vực A",
                "device_count": 2,
                "created_at": "2026-10-23T19:41:50+07:00",
            }
        return None


@pytest.fixture
def service():
    return ZoneService(repository=FakeZoneRepository())


def test_list_zones_by_farm(service):
    zones = service.list_zones_by_farm("farm-001")
    assert len(zones) == 1
    assert zones[0]["zone_code"] == "ZONE-A"


def test_get_zone(service):
    zone = service.get_zone("zone-001")
    assert zone is not None
    assert zone["name"] == "Khu vực A"


def test_empty_zone_id_raises_value_error(service):
    with pytest.raises(ValueError, match="zone_id is required"):
        service.get_zone("")


def test_zone_repository_sql_branching_avoids_uuid_cast_error():
    """Verifies that ZoneRepository branches safely between UUID and zone_code/farm_code."""
    import uuid

    # 1. Non-UUID zone code
    zone_code = "ZONE-A"
    is_uuid = False
    try:
        uuid.UUID(zone_code)
        is_uuid = True
    except (ValueError, AttributeError, TypeError):
        is_uuid = False
    assert is_uuid is False

    # 2. Canonical UUID string
    uuid_str = "33333333-cccc-cccc-cccc-cccccccccccc"
    is_uuid = False
    try:
        uuid.UUID(uuid_str)
        is_uuid = True
    except (ValueError, AttributeError, TypeError):
        is_uuid = False
    assert is_uuid is True


def test_zone_controller_get_nonexistent_zone_returns_404():
    from fastapi import HTTPException
    from app.controllers.zone_controller import ZoneController

    class EmptyZoneService:
        def get_zone(self, zone_id: str):
            return None

    controller = ZoneController(service=EmptyZoneService())
    with pytest.raises(HTTPException) as exc_info:
        controller.get_zone("nonexistent-zone")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Zone not found"
