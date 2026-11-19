from pathlib import Path
from urllib.parse import quote

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="",
        repr=False,
        validation_alias=AliasChoices("database_url", "DATABASE_URL", "NOTIFICATION_DATABASE_URL"),
    )
    management_service_url: str = Field(
        default="http://127.0.0.1:8001",
        validation_alias=AliasChoices("management_service_url", "MANAGEMENT_SERVICE_URL"),
    )
    internal_service_token: str = Field(
        default="",
        repr=False,
        validation_alias=AliasChoices(
            "internal_service_token",
            "INTERNAL_SERVICE_TOKEN",
            "NOTIFICATION_INTERNAL_SERVICE_TOKEN",
        ),
    )
    rabbitmq_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("rabbitmq_enabled", "RABBITMQ_ENABLED"),
    )
    rabbitmq_url: str = Field(
        default="",
        repr=False,
        validation_alias=AliasChoices("rabbitmq_url", "RABBITMQ_URL"),
    )
    rabbitmq_host: str = Field(
        default="",
        validation_alias=AliasChoices("rabbitmq_host", "RABBITMQ_HOST"),
    )
    rabbitmq_port: int = Field(
        default=5672,
        validation_alias=AliasChoices("rabbitmq_port", "RABBITMQ_PORT"),
    )
    rabbitmq_user: str = Field(
        default="",
        validation_alias=AliasChoices("rabbitmq_user", "RABBITMQ_USER"),
    )
    rabbitmq_password: str = Field(
        default="",
        repr=False,
        validation_alias=AliasChoices("rabbitmq_password", "RABBITMQ_PASSWORD", "RABBITMQ_PASS"),
    )
    rabbitmq_vhost: str = Field(
        default="/",
        validation_alias=AliasChoices("rabbitmq_vhost", "RABBITMQ_VHOST"),
    )
    event_exchange: str = Field(
        default="swiftlet.domain.events",
        validation_alias=AliasChoices("event_exchange", "EVENT_EXCHANGE", "RABBITMQ_EXCHANGE"),
    )
    notification_queue: str = Field(
        default="swiftletcare.notifications",
        validation_alias=AliasChoices("notification_queue", "NOTIFICATION_QUEUE"),
    )

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = Field(default="", repr=False)
    smtp_sender: str = ""
    smtp_starttls: bool = True

    vapid_public_key: str = ""
    vapid_private_key: str = Field(default="", repr=False)
    vapid_subject: str = ""

    firebase_service_account_path: str = ""
    firebase_project_id: str = ""

    service_host: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("service_host", "SERVICE_HOST", "NOTIFICATION_SERVICE_HOST"),
    )
    service_port: int = Field(
        default=8004,
        validation_alias=AliasChoices("service_port", "SERVICE_PORT", "NOTIFICATION_SERVICE_PORT"),
    )

    @model_validator(mode="after")
    def _assemble_rabbitmq_url(self) -> "Settings":
        if not self.rabbitmq_enabled:
            self.rabbitmq_url = ""
            return self
        if not self.rabbitmq_url and self.rabbitmq_host:
            user = quote(self.rabbitmq_user, safe="") if self.rabbitmq_user else ""
            pwd = quote(self.rabbitmq_password, safe="") if self.rabbitmq_password else ""
            auth = f"{user}:{pwd}@" if user or pwd else ""
            vhost = quote(self.rabbitmq_vhost.lstrip("/"), safe="")
            self.rabbitmq_url = f"amqp://{auth}{self.rabbitmq_host}:{self.rabbitmq_port}/{vhost}"
        return self


settings = Settings()
