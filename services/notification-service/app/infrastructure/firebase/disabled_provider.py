"""Disabled FCM provider implementation (CP6.4)."""
from __future__ import annotations

import logging
from typing import Dict, List

from app.ports.fcm_provider import FCMProvider, FCMResponse

log = logging.getLogger("swiftletcare.notification.fcm.disabled")


class DisabledFCMProvider(FCMProvider):
    """FCMProvider implementation when FCM delivery channel is disabled."""

    def send_single(
        self,
        token: str,
        title: str,
        body: str,
        data: Dict[str, str],
    ) -> FCMResponse:
        log.debug("FCM push delivery is disabled; suppressing send to token")
        return FCMResponse(
            success=False,
            error="FCM push notification delivery is disabled",
            invalid_tokens=[],
        )

    def send_multicast(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Dict[str, str],
    ) -> FCMResponse:
        log.debug("FCM multicast push delivery is disabled; suppressing send")
        return FCMResponse(
            success=False,
            error="FCM push notification delivery is disabled",
            invalid_tokens=[],
        )


__all__ = ["DisabledFCMProvider"]
