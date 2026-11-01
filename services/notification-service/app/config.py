from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = ""
    management_service_url: str = "http://127.0.0.1:8001"
    rabbitmq_url: str = ""
    event_exchange: str = "swiftletcare.events"
    notification_queue: str = "swiftletcare.notifications"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_sender: str = ""
    smtp_starttls: bool = True

    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = ""

    service_host: str = "127.0.0.1"
    service_port: int = 8002


settings = Settings()
