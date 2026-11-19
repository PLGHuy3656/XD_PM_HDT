"""Error normalization and category mapping for Firebase FCM (CP6.4)."""
from __future__ import annotations

from typing import Optional, Tuple
from dataclasses import dataclass


class FCMErrorCategory:
    INVALID_TOKEN = "INVALID_TOKEN"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    UNAVAILABLE = "UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNKNOWN = "UNKNOWN"


# Retryable error categories for future CP7 RabbitMQ dead-letter/retry policy
RETRYABLE_CATEGORIES = {
    FCMErrorCategory.UNAVAILABLE,
    FCMErrorCategory.INTERNAL_ERROR,
}


@dataclass(frozen=True)
class NormalizedFCMError:
    category: str
    message: str
    is_invalid_token: bool = False
    is_retryable: bool = False


def normalize_firebase_exception(exc: Exception) -> NormalizedFCMError:
    """Normalize a Firebase SDK or network exception into a transport-neutral descriptor.

    Ensures no Firebase SDK exception types leak to application/domain services.
    """
    exc_type_name = type(exc).__name__
    exc_str = str(exc)

    # 1. Check for invalid or unregistered registration token
    lower_str = exc_str.lower()
    if (
        "unregistered" in lower_str
        or "invalid-registration-token" in lower_str
        or "registration-token-not-registered" in lower_str
        or "invalid argument" in lower_str
        or "not a valid fcm registration token" in lower_str
        or exc_type_name in ("UnregisteredError", "InvalidArgumentError")
    ):
        return NormalizedFCMError(
            category=FCMErrorCategory.INVALID_TOKEN,
            message=f"Invalid or unregistered FCM token: {exc_str}",
            is_invalid_token=True,
            is_retryable=False,
        )

    # 2. Authentication and credentials errors
    if (
        "unauthenticated" in lower_str
        or "permission-denied" in lower_str
        or "credential" in lower_str
        or exc_type_name in ("UnauthenticatedError", "PermissionDeniedError")
    ):
        return NormalizedFCMError(
            category=FCMErrorCategory.AUTHENTICATION_ERROR,
            message=f"Firebase authentication/permission failure: {exc_str}",
            is_invalid_token=False,
            is_retryable=False,
        )

    # 3. Quota exceeded / rate limit errors
    if (
        "quota" in lower_str
        or "resource-exhausted" in lower_str
        or "rate limit" in lower_str
        or exc_type_name in ("QuotaExceededError", "ResourceExhaustedError")
    ):
        return NormalizedFCMError(
            category=FCMErrorCategory.QUOTA_EXCEEDED,
            message=f"Firebase FCM quota exceeded: {exc_str}",
            is_invalid_token=False,
            is_retryable=False,
        )

    # 4. Unavailable / transient network errors
    if (
        "unavailable" in lower_str
        or "connection reset" in lower_str
        or "timeout" in lower_str
        or exc_type_name in ("UnavailableError", "DeadlineExceededError")
    ):
        return NormalizedFCMError(
            category=FCMErrorCategory.UNAVAILABLE,
            message=f"Firebase service temporarily unavailable: {exc_str}",
            is_invalid_token=False,
            is_retryable=True,
        )

    # 5. Internal server errors
    if (
        "internal" in lower_str
        or exc_type_name in ("InternalError", "ServerError")
    ):
        return NormalizedFCMError(
            category=FCMErrorCategory.INTERNAL_ERROR,
            message=f"Firebase internal error: {exc_str}",
            is_invalid_token=False,
            is_retryable=True,
        )

    # 6. Fallback unknown error
    return NormalizedFCMError(
        category=FCMErrorCategory.UNKNOWN,
        message=f"Unhandled Firebase error ({exc_type_name}): {exc_str}",
        is_invalid_token=False,
        is_retryable=False,
    )


def redact_token(token: Optional[str]) -> str:
    """Safely redact push tokens for logging to prevent credential/PII leakage."""
    if not token:
        return "[EMPTY_TOKEN]"
    token_str = str(token).strip()
    if len(token_str) <= 8:
        return "***"
    return f"{token_str[:4]}...{token_str[-4:]}"


__all__ = [
    "FCMErrorCategory",
    "RETRYABLE_CATEGORIES",
    "NormalizedFCMError",
    "normalize_firebase_exception",
    "redact_token",
]
