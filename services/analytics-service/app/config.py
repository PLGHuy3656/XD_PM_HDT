from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = ""
    management_service_url: str = "http://127.0.0.1:8001"
    analytics_service_token: str = ""
    ai_ingest_token: str = ""
    rabbitmq_url: str = ""
    event_exchange: str = "swiftletcare.events"
    monitor_interval_seconds: int = 30
    service_host: str = "127.0.0.1"
    service_port: int = 8003


settings = Settings()
