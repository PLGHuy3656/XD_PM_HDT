"""Firebase infrastructure module for Notification Service."""

from app.infrastructure.firebase.config import FCMSettings, FCMProviderType
from app.infrastructure.firebase.errors import (
    FCMErrorCategory,
    NormalizedFCMError,
    normalize_firebase_exception,
    redact_token,
)
from app.infrastructure.firebase.client import (
    FirebaseMessagingClient,
    RealFirebaseMessagingClient,
    FakeFirebaseMessagingClient,
)
from app.infrastructure.firebase.disabled_provider import DisabledFCMProvider
from app.infrastructure.firebase.provider import FirebaseFCMProvider, sanitize_fcm_data
from app.infrastructure.firebase.factory import create_fcm_provider

__all__ = [
    "FCMSettings",
    "FCMProviderType",
    "FCMErrorCategory",
    "NormalizedFCMError",
    "normalize_firebase_exception",
    "redact_token",
    "FirebaseMessagingClient",
    "RealFirebaseMessagingClient",
    "FakeFirebaseMessagingClient",
    "DisabledFCMProvider",
    "FirebaseFCMProvider",
    "sanitize_fcm_data",
    "create_fcm_provider",
]
