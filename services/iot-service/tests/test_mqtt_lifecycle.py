import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mqtt.client import MQTTManager


def test_mqtt_manager_start_and_stop_without_broker():
    """Verifies that starting and stopping the MQTT manager does not crash

    even if the MQTT broker is not reachable locally.
    """
    manager = MQTTManager()
    manager.start()
    assert manager.is_running is True

    manager.stop()
    assert manager.is_running is False


def test_fastapi_lifespan_and_health_with_test_client():
    """Verifies that FastAPI starts up with lifespan and GET /health returns 200

    independently from MQTT broker availability.
    """
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data == {
            "status": "ok",
            "service": "iot-service",
        }
        # Explicit check: no MQTT credentials leaked in health check
        assert "username" not in data
        assert "password" not in data
        assert "mqtt_broker_host" not in data
