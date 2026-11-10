"""Configuration settings for SwiftletCare API Gateway (CP11 Phase 1 & Phase 2)."""
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Gateway Server
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8000
    gateway_debug: bool = False
    service_name: str = "api-gateway"
    version: str = "0.2.0"
    environment: str = "test"

    # Upstream Services
    management_service_url: str = "http://127.0.0.1:8001"
    iot_service_url: str = "http://127.0.0.1:8002"
    ai_service_url: str = "http://127.0.0.1:8003"
    notification_service_url: str = "http://127.0.0.1:8004"
    analytics_service_url: str = "http://127.0.0.1:8005"
    analytics_service_deployed: bool = False

    # Timeouts (seconds)
    default_timeout_seconds: float = 5.0
    management_timeout_seconds: float = 5.0
    iot_timeout_seconds: float = 5.0
    ai_timeout_seconds: float = 10.0
    notification_timeout_seconds: float = 5.0
    analytics_timeout_seconds: float = 15.0

    # HTTP Client Pool
    http_max_connections: int = 100
    http_max_keepalive_connections: int = 20
    http_keepalive_expiry_seconds: float = 30.0

    # JWT Authentication & RBAC (CP11.3)
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_require_active_check: bool = True
    user_cache_ttl_seconds: int = 0  # 0 = direct inspection every time, fail-closed

    # CORS
    allowed_origins: str = "*"

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Gateway configuration error: JWT_SECRET must not be empty or blank.")
        if len(v.strip()) < 16:
            raise ValueError("Gateway configuration error: JWT_SECRET must be at least 16 characters long.")
        return v


settings = GatewaySettings()
