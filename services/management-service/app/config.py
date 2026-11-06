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
    # IoT Service HTTP boundary contract (CP8.0 / CP8.1)
    iot_service_base_url: str = "http://127.0.0.1:8002"
    iot_service_timeout_seconds: float = 2.0
    # Deprecated legacy migration setting (only used by one-off database/migrate_from_legacy.py script)
    legacy_iot_database_url: str = ""
    service_host: str = "127.0.0.1"
    service_port: int = 8001

    # Authentication & JWT Settings
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60


settings = Settings()
