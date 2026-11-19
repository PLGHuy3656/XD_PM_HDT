from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator


class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionRequest(BaseModel):
    endpoint: HttpUrl
    keys: PushSubscriptionKeys

    @field_validator("endpoint")
    @classmethod
    def require_trusted_push_endpoint(cls, endpoint: HttpUrl) -> HttpUrl:
        allowed_domains = (
            "fcm.googleapis.com",
            "push.services.mozilla.com",
            "push.apple.com",
            "notify.windows.com",
        )
        host = endpoint.host.lower().rstrip(".")
        if endpoint.scheme != "https" or not any(
            host == domain or host.endswith(f".{domain}")
            for domain in allowed_domains
        ):
            raise ValueError("Unsupported web push endpoint")
        return endpoint


class FcmTokenRequest(BaseModel):
    token: str = Field(min_length=1, max_length=4096)
    platform: Literal["android", "ios", "web"]


class FcmTokenDeleteRequest(BaseModel):
    token: str = Field(min_length=1, max_length=4096)


class NotificationEvent(BaseModel):
    event_id: UUID
    event_type: str
    recipient_user_ids: list[UUID]
    data: dict[str, Any] = Field(default_factory=dict)
