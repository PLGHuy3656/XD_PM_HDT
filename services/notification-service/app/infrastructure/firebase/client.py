"""Firebase messaging client abstraction, real SDK wrapper, and test fake (CP6.4)."""
from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Tuple

from app.infrastructure.firebase.config import FCMSettings
from app.infrastructure.firebase.errors import redact_token

log = logging.getLogger("swiftletcare.notification.fcm.client")


class FirebaseMessagingClient(ABC):
    """Abstract client interface for interacting with Firebase Cloud Messaging."""

    @abstractmethod
    def send_message(
        self,
        token: str,
        title: str,
        body: str,
        data: Dict[str, str],
    ) -> str:
        """Send a single push notification message.

        Returns provider message ID string on success.
        Raises an exception on failure.
        """
        pass

    @abstractmethod
    def send_multicast(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Dict[str, str],
    ) -> Tuple[List[str], List[str], List[str]]:
        """Send multicast push notification message to multiple tokens.

        Returns (successful_message_ids, failed_tokens, invalid_tokens).
        """
        pass


class RealFirebaseMessagingClient(FirebaseMessagingClient):
    """Production wrapper around official firebase_admin SDK."""

    def __init__(self, settings: FCMSettings) -> None:
        self.settings = settings
        self._app: Optional[Any] = None

    def _ensure_initialized(self) -> None:
        """Lazy initialization of firebase_admin app to prevent import-time side-effects."""
        if self._app is not None:
            return

        import firebase_admin
        from firebase_admin import credentials

        # Re-use default app if already initialized
        if firebase_admin._apps:
            self._app = firebase_admin.get_app()
            return

        self.settings.validate_for_runtime()

        cred = None
        if self.settings.credentials_path:
            cred = credentials.Certificate(self.settings.credentials_path)
        else:
            cred = credentials.ApplicationDefault()

        options = {}
        if self.settings.project_id:
            options["projectId"] = self.settings.project_id

        self._app = firebase_admin.initialize_app(cred, options=options)
        log.info("Initialized Firebase Admin SDK app successfully (projectId=%s)", self.settings.project_id)

    def send_message(
        self,
        token: str,
        title: str,
        body: str,
        data: Dict[str, str],
    ) -> str:
        self._ensure_initialized()
        from firebase_admin import messaging

        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data,
            token=token,
        )
        msg_id: str = messaging.send(message, app=self._app)
        log.info("FCM message sent successfully to %s: %s", redact_token(token), msg_id)
        return msg_id

    def send_multicast(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Dict[str, str],
    ) -> Tuple[List[str], List[str], List[str]]:
        self._ensure_initialized()
        from firebase_admin import messaging

        multicast = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=data,
            tokens=tokens,
        )
        response = messaging.send_each_for_multicast(multicast, app=self._app)

        success_ids: List[str] = []
        failed_tokens: List[str] = []
        invalid_tokens: List[str] = []

        for idx, send_response in enumerate(response.responses):
            target_token = tokens[idx]
            if send_response.success:
                success_ids.append(send_response.message_id)
            else:
                err = send_response.exception
                failed_tokens.append(target_token)
                err_str = str(err).lower()
                if "unregistered" in err_str or "invalid" in err_str:
                    invalid_tokens.append(target_token)

        return success_ids, failed_tokens, invalid_tokens


class FakeFirebaseMessagingClient(FirebaseMessagingClient):
    """In-memory fake Firebase client for fast, deterministic unit & E2E testing."""

    def __init__(self) -> None:
        self.sent_messages: List[Dict[str, Any]] = []
        self.invalid_tokens: Set[str] = set()
        self.fail_tokens: Set[str] = set()
        self.simulate_exception: Optional[Exception] = None

    def reset(self) -> None:
        self.sent_messages.clear()
        self.invalid_tokens.clear()
        self.fail_tokens.clear()
        self.simulate_exception = None

    def send_message(
        self,
        token: str,
        title: str,
        body: str,
        data: Dict[str, str],
    ) -> str:
        if self.simulate_exception is not None:
            raise self.simulate_exception

        if token in self.invalid_tokens:
            raise ValueError(f"Requested entity was not found: registration-token-not-registered ({token})")

        if token in self.fail_tokens:
            raise RuntimeError(f"Connection reset by peer during FCM dispatch to {token}")

        msg_id = f"projects/swiftletcare-test/messages/{uuid.uuid4().hex[:16]}"
        self.sent_messages.append({
            "message_id": msg_id,
            "token": token,
            "title": title,
            "body": body,
            "data": dict(data),
        })
        return msg_id

    def send_multicast(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Dict[str, str],
    ) -> Tuple[List[str], List[str], List[str]]:
        if self.simulate_exception is not None:
            raise self.simulate_exception

        success_ids: List[str] = []
        failed_tokens: List[str] = []
        invalid_tokens: List[str] = []

        for token in tokens:
            if token in self.invalid_tokens:
                failed_tokens.append(token)
                invalid_tokens.append(token)
            elif token in self.fail_tokens:
                failed_tokens.append(token)
            else:
                msg_id = f"projects/swiftletcare-test/messages/{uuid.uuid4().hex[:16]}"
                self.sent_messages.append({
                    "message_id": msg_id,
                    "token": token,
                    "title": title,
                    "body": body,
                    "data": dict(data),
                })
                success_ids.append(msg_id)

        return success_ids, failed_tokens, invalid_tokens


__all__ = [
    "FirebaseMessagingClient",
    "RealFirebaseMessagingClient",
    "FakeFirebaseMessagingClient",
]
