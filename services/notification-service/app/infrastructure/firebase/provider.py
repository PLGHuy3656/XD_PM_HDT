"""Production Firebase Cloud Messaging adapter implementing FCMProvider port (CP6.4)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.infrastructure.firebase.client import FirebaseMessagingClient, RealFirebaseMessagingClient
from app.infrastructure.firebase.config import FCMSettings
from app.infrastructure.firebase.errors import (
    NormalizedFCMError,
    normalize_firebase_exception,
    redact_token,
)
from app.ports.fcm_provider import FCMProvider, FCMResponse

log = logging.getLogger("swiftletcare.notification.fcm.provider")


def sanitize_fcm_data(data: Dict[str, Any]) -> Dict[str, str]:
    """Ensure FCM data payload values are strings and exclude local filesystem paths."""
    sanitized: Dict[str, str] = {}
    for k, v in data.items():
        if v is None:
            continue
        v_str = str(v).strip()

        # Sanitize against accidental leakage of local filesystem paths
        lower = v_str.lower()
        if (
            lower.startswith("c:\\")
            or lower.startswith("d:\\")
            or lower.startswith("e:\\")
            or lower.startswith("/home/")
            or lower.startswith("/var/")
            or lower.startswith("file://")
        ):
            log.warning("Excluding local filesystem path from FCM payload key '%s'", k)
            continue

        sanitized[k] = v_str

    return sanitized


class FirebaseFCMProvider(FCMProvider):
    """FCMProvider adapter backed by FirebaseMessagingClient (real or fake).

    Conforms strictly to the transport-neutral FCMProvider port.
    Never leaks Firebase SDK exception types or objects to callers.
    """

    def __init__(
        self,
        client: Optional[FirebaseMessagingClient] = None,
        settings: Optional[FCMSettings] = None,
    ) -> None:
        self.settings = settings or FCMSettings.from_env()
        self.client = client or RealFirebaseMessagingClient(self.settings)

    def send_single(
        self,
        token: str,
        title: str,
        body: str,
        data: Dict[str, str],
    ) -> FCMResponse:
        sanitized_data = sanitize_fcm_data(data)
        safe_token = redact_token(token)

        try:
            msg_id = self.client.send_message(
                token=token,
                title=title,
                body=body,
                data=sanitized_data,
            )
            log.info("FCM dispatched successfully to %s: msgId=%s", safe_token, msg_id)
            return FCMResponse(
                success=True,
                message_id=msg_id,
                error=None,
                invalid_tokens=[],
            )
        except Exception as exc:
            norm: NormalizedFCMError = normalize_firebase_exception(exc)
            log.warning(
                "FCM delivery failed for %s: category=%s, err=%s",
                safe_token,
                norm.category,
                norm.message,
            )
            invalid_list = [token] if norm.is_invalid_token else []
            return FCMResponse(
                success=False,
                message_id=None,
                error=norm.message,
                invalid_tokens=invalid_list,
            )

    def send_multicast(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Dict[str, str],
    ) -> FCMResponse:
        if not tokens:
            return FCMResponse(success=True, message_id=None)

        sanitized_data = sanitize_fcm_data(data)
        try:
            success_ids, failed_tokens, invalid_tokens = self.client.send_multicast(
                tokens=tokens,
                title=title,
                body=body,
                data=sanitized_data,
            )
            all_ok = len(success_ids) == len(tokens)
            return FCMResponse(
                success=all_ok,
                message_id=success_ids[0] if success_ids else None,
                error=None if all_ok else f"{len(failed_tokens)}/{len(tokens)} token deliveries failed",
                invalid_tokens=invalid_tokens,
            )
        except Exception as exc:
            norm = normalize_firebase_exception(exc)
            log.warning("FCM multicast delivery exception: category=%s, err=%s", norm.category, norm.message)
            return FCMResponse(
                success=False,
                message_id=None,
                error=norm.message,
                invalid_tokens=[],
            )


__all__ = [
    "FirebaseFCMProvider",
    "sanitize_fcm_data",
]
