import pytest

from app.services.technician_service import TechnicianService


class FakeTechnicianRepository:
    def get_profile(self, technician_id: str):
        return {
            "technician_id": technician_id,
            "full_name": "Nguyen Van Khang",
            "email": "tech@nestmate.dev",
            "phone": "0903456789",
            "status": "ACTIVE",
        }

    def get_assigned_farms(self, technician_id: str):
        return [
            {
                "farm_id": "farm-binh-an",
                "farm_code": "NM-BA-01",
                "farm_name": "Nhà yến Bình An",
                "address": "Thủ Đức, TP. Hồ Chí Minh",
                "status": "ACTIVE",
                "zone_count": 3,
                "device_count": 6,
            },
            {
                "farm_id": "farm-phu-an",
                "farm_code": "NM-PA-02",
                "farm_name": "Nhà yến Phú An",
                "address": "Dĩ An, Bình Dương",
                "status": "ACTIVE",
                "zone_count": 2,
                "device_count": 4,
            },
        ]

    def get_assigned_farm_detail(
        self,
        technician_id: str,
        farm_id: str,
    ):
        return {
            "farm_id": farm_id,
            "farm_code": "NM-BA-01",
            "farm_name": "Nhà yến Bình An",
            "address": "Thủ Đức, TP. Hồ Chí Minh",
            "status": "ACTIVE",
            "zone_count": 3,
            "device_count": 6,
            "owner_name": "Nguyễn Văn Minh",
            "owner_phone": "0901234567",
        }


@pytest.fixture
def service():
    return TechnicianService(
        repository=FakeTechnicianRepository()
    )


def test_get_profile(service):
    result = service.get_profile("tech-001")

    assert result["technician_id"] == "tech-001"
    assert result["status"] == "ACTIVE"


def test_get_assigned_farms(service):
    result = service.get_assigned_farms("tech-001")

    assert len(result) == 2
    assert result[0]["farm_id"] == "farm-binh-an"
    assert result[1]["farm_id"] == "farm-phu-an"


def test_get_assigned_farm_detail(service):
    result = service.get_assigned_farm_detail(
        "tech-001",
        "farm-binh-an",
    )

    assert result["farm_name"] == "Nhà yến Bình An"
    assert result["zone_count"] == 3


def test_empty_technician_id_is_rejected(service):
    with pytest.raises(
        ValueError,
        match="technician_id is required",
    ):
        service.get_profile("")


def test_empty_farm_id_is_rejected(service):
    with pytest.raises(
        ValueError,
        match="farm_id is required",
    ):
        service.get_assigned_farm_detail(
            "tech-001",
            "",
        )
