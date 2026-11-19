import uuid
from typing import List, Dict, Any, Set
from app.ports.fcm_provider import FCMProvider, FCMResponse


class MockFCMProvider(FCMProvider):
    """Mock FCM provider for testing push notifications without external dependencies."""

    def __init__(self) -> None:
        self.sent_messages: List[Dict[str, Any]] = []
        self.fail_all: bool = False
        self.invalid_tokens: Set[str] = set()
        self.fail_tokens: Set[str] = set()

    def reset(self) -> None:
        self.sent_messages.clear()
        self.fail_all = False
        self.invalid_tokens.clear()
        self.fail_tokens.clear()

    def send_single(
        self,
        token: str,
        title: str,
        body: str,
        data: Dict[str, str],
    ) -> FCMResponse:
        if self.fail_all or token in self.fail_tokens:
            return FCMResponse(
                success=False,
                error="FCM dispatch simulated failure",
            )

        if token in self.invalid_tokens:
            return FCMResponse(
                success=False,
                error="Invalid/Unregistered device registration token",
                invalid_tokens=[token],
            )

        msg_id = f"fcm_msg_{uuid.uuid4().hex[:12]}"
        self.sent_messages.append({
            "message_id": msg_id,
            "token": token,
            "title": title,
            "body": body,
            "data": data,
        })
        return FCMResponse(success=True, message_id=msg_id)

    def send_multicast(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Dict[str, str],
    ) -> FCMResponse:
        if not tokens:
            return FCMResponse(success=True, message_id=None)

        if self.fail_all:
            return FCMResponse(
                success=False,
                error="FCM multicast simulated failure",
            )

        invalid: List[str] = [t for t in tokens if t in self.invalid_tokens]
        success_tokens = [
            t for t in tokens if t not in self.invalid_tokens and t not in self.fail_tokens
        ]

        for t in success_tokens:
            msg_id = f"fcm_msg_{uuid.uuid4().hex[:12]}"
            self.sent_messages.append({
                "message_id": msg_id,
                "token": t,
                "title": title,
                "body": body,
                "data": data,
            })

        all_ok = len(success_tokens) == len(tokens)
        return FCMResponse(
            success=all_ok,
            message_id=f"fcm_multi_{uuid.uuid4().hex[:8]}" if success_tokens else None,
            error=None if all_ok else "One or more tokens failed dispatch",
            invalid_tokens=invalid,
        )
