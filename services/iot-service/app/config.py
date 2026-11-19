from pathlib import Path
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "iot-service"
    service_host: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("service_host", "SERVICE_HOST", "IOT_SERVICE_HOST"),
    )
    service_port: int = Field(
        default=8002,
        validation_alias=AliasChoices("service_port", "SERVICE_PORT", "IOT_SERVICE_PORT"),
    )

    # MQTT Broker Configuration
    mqtt_broker_host: str = "127.0.0.1"
    mqtt_broker_port: int = 1883
    mqtt_client_id: str = "swiftletcare-iot-service"
    mqtt_username: str | None = None
    mqtt_password: str | None = Field(default=None, repr=False)
    mqtt_keepalive: int = 60
    mqtt_qos: int = 1
    mqtt_auto_start: bool = True

    # Device Presence Configuration
    device_stale_timeout_seconds: int = 90

    # Authoritative Management Service Internal Metadata Lookup (INT01)
    management_service_url: str = Field(
        default="",
        validation_alias=AliasChoices("management_service_url", "MANAGEMENT_SERVICE_URL"),
    )
    internal_service_key: str = Field(
        default="",
        repr=False,
        validation_alias=AliasChoices(
            "internal_service_key",
            "INTERNAL_SERVICE_KEY",
            "MANAGEMENT_INTERNAL_SERVICE_KEY",
            "INTERNAL_SERVICE_TOKEN",
        ),
    )
    metadata_cache_ttl_seconds: float = Field(
        default=10.0,
        validation_alias=AliasChoices("metadata_cache_ttl_seconds", "METADATA_CACHE_TTL_SECONDS"),
    )
    metadata_negative_cache_ttl_seconds: float = 5.0


settings = Settings()
