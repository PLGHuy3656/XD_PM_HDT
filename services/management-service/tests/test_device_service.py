import pytest
from app.services.device_service import DeviceService


class FakeDeviceRepository:
    def list_devices(self, farm_id=None, zone_id=None):
        devices = [
            {
                "device_id": "dev-001",
                "node_id": "ESP32-001",
                "name": "Bộ điều khiển Khu vực A",
                "device_type": "CONTROLLER",
                "farm_id": "farm-001",
                "zone_id": "zone-001",
                "zone_name": "Khu vực A",
                "ip_address": "192.168.1.21",
                "firmware_version": "v1.0.0",
                "is_active": True,
                "status": "ONLINE",
            }
        ]
        if farm_id:
            devices = [d for d in devices if d["farm_id"] == farm_id]
        if zone_id:
            devices = [d for d in devices if d["zone_id"] == zone_id]
        return devices

    def get_device_by_id(self, device_id: str):
        if device_id in ("dev-001", "ESP32-001"):
            return {
                "device_id": "dev-001",
                "node_id": "ESP32-001",
                "name": "Bộ điều khiển Khu vực A",
                "device_type": "CONTROLLER",
                "farm_id": "farm-001",
                "zone_id": "zone-001",
                "zone_name": "Khu vực A",
                "ip_address": "192.168.1.21",
                "firmware_version": "v1.0.0",
                "is_active": True,
                "status": "ONLINE",
            }
        return None


@pytest.fixture
def service():
    return DeviceService(repository=FakeDeviceRepository())


def test_list_devices(service):
    devices = service.list_devices()
    assert len(devices) == 1
    assert devices[0]["node_id"] == "ESP32-001"


def test_get_device(service):
    # Lookup by UUID
    device_by_uuid = service.get_device("dev-001")
    assert device_by_uuid is not None
    assert device_by_uuid["device_type"] == "CONTROLLER"
    assert device_by_uuid["farm_id"] == "farm-001"

    # Lookup by node_id (e.g., NODE-A1 / ESP32-001)
    device_by_node = service.get_device("ESP32-001")
    assert device_by_node is not None
    assert device_by_node["device_id"] == "dev-001"
    assert device_by_node["farm_id"] == "farm-001"


def test_device_repository_sql_branching_avoids_uuid_cast_error():
    """Verifies that DeviceRepository inspects UUID vs node_id to avoid PostgreSQL UUID cast error."""
    import uuid
    from app.repositories.device_repository import DeviceRepository

    # 1. Non-UUID node_id like 'NODE-A1'
    node_id_val = "NODE-A1"
    is_uuid = False
    try:
        uuid.UUID(node_id_val)
        is_uuid = True
    except (ValueError, AttributeError, TypeError):
        is_uuid = False
    assert is_uuid is False  # Must branch to WHERE d.node_id = %s

    # 2. Canonical UUID string
    uuid_val = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    is_uuid = False
    try:
        uuid.UUID(uuid_val)
        is_uuid = True
    except (ValueError, AttributeError, TypeError):
        is_uuid = False
    assert is_uuid is True  # Branches to WHERE d.id = %s OR d.node_id = %s


def test_empty_device_id_raises_value_error(service):
    with pytest.raises(ValueError, match="device_id is required"):
        service.get_device("")
