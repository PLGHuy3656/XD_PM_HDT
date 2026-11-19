from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "iot-service"
    service_host: str = "127.0.0.1"
    service_port: int = 8002

    # MQTT Broker Configuration
    mqtt_broker_host: str = "127.0.0.1"
    mqtt_broker_port: int = 1883
    mqtt_client_id: str = "swiftletcare-iot-service"
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_keepalive: int = 60
    mqtt_qos: int = 1
    mqtt_auto_start: bool = True

    # Device Presence Configuration
    device_stale_timeout_seconds: int = 90


settings = Settings()
