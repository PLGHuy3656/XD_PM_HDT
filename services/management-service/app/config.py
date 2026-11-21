from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

MIN_PSK_BYTES = 32


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

    # Authentication & JWT Settings (Public User RBAC Only)
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # Dedicated Service-to-Service PSK Authentication (CP11.4-B1-R2-MGMT-R1)
    # Primary internal service token (minimum 32 bytes)
    internal_service_token: str = ""
    # Comma-separated list of active service tokens to support bounded key rotation (minimum 32 bytes each)
    internal_service_tokens: str = ""


    # INT03-R1: business domain events (Management -> RabbitMQ -> Notification)
    rabbitmq_url: str = ""
    rabbitmq_host: str = ""
    rabbitmq_port: int = 5672
    rabbitmq_user: str = ""
    rabbitmq_password: str = ""
    rabbitmq_vhost: str = "/"
    event_exchange: str = "swiftlet.domain.events"
    events_enabled: bool = True
    event_dispatch_interval_seconds: float = 2.0
    event_max_attempts: int = 10
    auto_apply_additive_migrations: bool = True

    @property
    def effective_rabbitmq_url(self) -> str:
        """RABBITMQ_URL if given, else assembled from parts with URL-quoted credentials."""
        if self.rabbitmq_url:
            return self.rabbitmq_url
        if not self.rabbitmq_host:
            return ""
        from urllib.parse import quote

        return (
            f"amqp://{quote(self.rabbitmq_user, safe='')}:{quote(self.rabbitmq_password, safe='')}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}/{quote(self.rabbitmq_vhost, safe='')}"
        )

    def _get_raw_service_tokens(self) -> list[str]:
        raw: list[str] = []
        if self.internal_service_token and self.internal_service_token.strip():
            raw.append(self.internal_service_token.strip())
        if self.internal_service_tokens and self.internal_service_tokens.strip():
            for t in self.internal_service_tokens.split(","):
                clean = t.strip()
                if clean:
                    raw.append(clean)
        return raw

    @property
    def has_weak_service_token(self) -> bool:
        """Returns True if any configured service token has fewer than 32 bytes."""
        raw = self._get_raw_service_tokens()
        if not raw:
            return False
        return any(len(t.encode("utf-8")) < MIN_PSK_BYTES for t in raw)

    @property
    def valid_service_tokens(self) -> set[str]:
        """Resolves all valid high-entropy pre-shared service tokens (>= 32 bytes) for constant-time comparison."""
        tokens: set[str] = set()
        for t in self._get_raw_service_tokens():
            if len(t.encode("utf-8")) >= MIN_PSK_BYTES:
                tokens.add(t)
        return tokens

    @property
    def is_service_auth_configured(self) -> bool:
        """Checks if valid, high-entropy service authentication is configured without weak keys."""
        raw = self._get_raw_service_tokens()
        if not raw:
            return False
        if self.has_weak_service_token:
            return False
        return bool(self.valid_service_tokens)


settings = Settings()
