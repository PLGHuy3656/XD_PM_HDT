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

    def get_assigned_farm_devices(self, technician_id: str, farm_id: str):
        return [
            {
                "device_id": "dev-01",
                "node_id": "NODE-01",
                "name": "Sensor 1",
                "device_type": "SENSOR",
                "farm_id": farm_id,
                "status": "UNKNOWN",
                "mqtt_status": "Unknown",
            }
        ]

    def get_assigned_farm_device_detail(self, technician_id: str, farm_id: str, device_id: str):
        return {
            "device_id": device_id,
            "node_id": "NODE-01",
            "name": "Sensor 1",
            "device_type": "SENSOR",
            "farm_id": farm_id,
            "status": "UNKNOWN",
            "mqtt_status": "Unknown",
        }

    def get_dashboard_summary(self, technician_id: str):
        return {
            "technician_id": technician_id,
            "assigned_farm_count": 2,
            "zone_count": 5,
            "device_count": 10,
            "online_device_count": 0,
            "offline_device_count": 0,
            "unknown_device_count": 10,
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


def test_get_assigned_farm_devices(service):
    result = service.get_assigned_farm_devices("tech-001", "farm-binh-an")
    assert len(result) == 1
    assert result[0]["status"] == "UNKNOWN"
    assert result[0]["mqtt_status"] == "Unknown"


def test_get_assigned_farm_device_detail(service):
    result = service.get_assigned_farm_device_detail("tech-001", "farm-binh-an", "dev-01")
    assert result["device_id"] == "dev-01"
    assert result["status"] == "UNKNOWN"
    assert result["mqtt_status"] == "Unknown"


def test_get_dashboard_summary_includes_unknown_device_count(service):
    result = service.get_dashboard_summary("tech-001")
    assert result["technician_id"] == "tech-001"
    assert result["device_count"] == 10
    assert result["online_device_count"] == 0
    assert result["offline_device_count"] == 0
    assert result["unknown_device_count"] == 10


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
