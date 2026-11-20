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

    # INT01-R1: Inbound service-to-service authentication for /api/iot/* and /ws/iot.
    # The same INT01 internal service key (INTERNAL_SERVICE_TOKEN) is presented by the
    # API Gateway and Management Service in the X-Internal-Service-Key header.
    # Fail-closed: when required and no key is configured, every protected route returns 503.
    internal_api_auth_required: bool = Field(
        default=True,
        validation_alias=AliasChoices("internal_api_auth_required", "IOT_INTERNAL_API_AUTH_REQUIRED"),
    )

    # INT01-R1: Server-authoritative command ACK deadline and runtime TIMEOUT sweeper.
    command_ack_timeout_seconds: int = Field(
        default=15,
        ge=3,
        le=300,
        validation_alias=AliasChoices("command_ack_timeout_seconds", "COMMAND_ACK_TIMEOUT_SECONDS"),
    )
    command_timeout_sweep_interval_seconds: float = Field(
        default=1.0,
        gt=0,
        le=30,
        validation_alias=AliasChoices(
            "command_timeout_sweep_interval_seconds", "COMMAND_TIMEOUT_SWEEP_INTERVAL_SECONDS"
        ),
    )
    command_timeout_sweeper_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("command_timeout_sweeper_enabled", "COMMAND_TIMEOUT_SWEEPER_ENABLED"),
    )


settings = Settings()
