from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = ""
    # TODO(MICROSERVICE-BOUNDARY):
    # Temporary fallback connection to legacy database for runtime IoT telemetry/presence state
    # until IoT Service (iot-service) is operational and provides REST / event APIs.
    legacy_iot_database_url: str = ""
    service_host: str = "127.0.0.1"
    service_port: int = 8001


settings = Settings()
