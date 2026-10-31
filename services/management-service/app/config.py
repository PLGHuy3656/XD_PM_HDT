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

    # Authentication & JWT Settings
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60


settings = Settings()
