
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = ""

    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_client_id: str = "swiftletcare-telemetry-backend"
    management_service_url: str = "http://127.0.0.1:8001"
    rabbitmq_url: str = ""
    event_exchange: str = "swiftletcare.events"


settings = Settings()
