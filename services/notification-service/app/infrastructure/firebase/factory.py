"""Provider factory for constructing FCMProvider instances (CP6.4)."""
from __future__ import annotations

import logging
from typing import Optional

from app.infrastructure.firebase.client import FirebaseMessagingClient
from app.infrastructure.firebase.config import FCMSettings
from app.infrastructure.firebase.disabled_provider import DisabledFCMProvider
from app.infrastructure.firebase.provider import FirebaseFCMProvider
from app.ports.fcm_provider import FCMProvider
from app.services.mock_fcm_provider import MockFCMProvider

log = logging.getLogger("swiftletcare.notification.fcm.factory")


def create_fcm_provider(
    settings: Optional[FCMSettings] = None,
    client: Optional[FirebaseMessagingClient] = None,
) -> FCMProvider:
    """Create an FCMProvider instance based on environment settings and client overrides."""
    resolved_settings = settings or FCMSettings.from_env()

    if not resolved_settings.enabled or resolved_settings.provider == "disabled":
        log.info("FCM provider initialized: DisabledFCMProvider (push delivery suppressed)")
        return DisabledFCMProvider()

    if resolved_settings.provider == "mock":
        log.info("FCM provider initialized: MockFCMProvider (in-memory test provider)")
        return MockFCMProvider()

    if resolved_settings.provider == "firebase":
        log.info("FCM provider initialized: FirebaseFCMProvider")
        return FirebaseFCMProvider(client=client, settings=resolved_settings)

    raise ValueError(f"Unknown FCM provider type '{resolved_settings.provider}'. Expected 'mock', 'firebase', or 'disabled'.")


__all__ = ["create_fcm_provider"]
