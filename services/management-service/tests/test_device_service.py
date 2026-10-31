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
    device = service.get_device("dev-001")
    assert device is not None
    assert device["device_type"] == "CONTROLLER"


def test_empty_device_id_raises_value_error(service):
    with pytest.raises(ValueError, match="device_id is required"):
        service.get_device("")
