import pytest
from app.services.farm_service import FarmService


class FakeFarmRepository:
    def __init__(self):
        self.list_farms_arguments = None

    def list_farms(self, user_id, is_admin, is_owner, is_technician):
        self.list_farms_arguments = {
            "user_id": user_id,
            "is_admin": is_admin,
            "is_owner": is_owner,
            "is_technician": is_technician,
        }
        return [
            {
                "farm_id": "farm-001",
                "farm_code": "NM-BA-01",
                "farm_name": "Nhà yến Bình An",
                "address": "Thủ Đức, TP. Hồ Chí Minh",
                "status": "ACTIVE",
                "zone_count": 3,
                "device_count": 6,
            }
        ]

    def get_farm_by_id(self, farm_id: str):
        if farm_id == "farm-001":
            return {
                "farm_id": "farm-001",
                "farm_code": "NM-BA-01",
                "farm_name": "Nhà yến Bình An",
                "address": "Thủ Đức, TP. Hồ Chí Minh",
                "status": "ACTIVE",
                "zone_count": 3,
                "device_count": 6,
                "owner_name": "Nguyễn Văn Minh",
                "owner_phone": "0901234567",
                "technician_id": "tech-001",
                "technician_name": "Nguyễn Văn Khang",
                "created_at": "2026-10-23T19:41:50+07:00",
            }
        return None


@pytest.fixture
def service():
    return FarmService(repository=FakeFarmRepository())


def test_list_farms(service):
    farms = service.list_farms(
        {"id": "tech-001", "roles": ["TECHNICIAN"]},
    )
    assert len(farms) == 1
    assert farms[0]["farm_code"] == "NM-BA-01"
    assert service.repository.list_farms_arguments == {
        "user_id": "tech-001",
        "is_admin": False,
        "is_owner": False,
        "is_technician": True,
    }


def test_get_farm_detail(service):
    farm = service.get_farm("farm-001")
    assert farm is not None
    assert farm["farm_name"] == "Nhà yến Bình An"
    assert farm["zone_count"] == 3


def test_empty_farm_id_raises_value_error(service):
    with pytest.raises(ValueError, match="farm_id is required"):
        service.get_farm("")
