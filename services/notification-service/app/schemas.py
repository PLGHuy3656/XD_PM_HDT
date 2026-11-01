from pydantic import BaseModel, HttpUrl, field_validator


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
