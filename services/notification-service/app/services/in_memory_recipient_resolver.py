from typing import Optional, List, Dict
from app.domain.enums import AlertSeverity, AlertEventType
from app.ports.recipient_resolver import RecipientResolver, RecipientInfo


class InMemoryRecipientResolver(RecipientResolver):
    """In-memory recipient resolver for testing and local reference runtime."""

    def __init__(self, default_recipients: Optional[List[RecipientInfo]] = None) -> None:
        self._farm_recipients: Dict[str, List[RecipientInfo]] = {}
        self._default_recipients: List[RecipientInfo] = default_recipients or [
            RecipientInfo(
                user_id="user_admin_001",
                email="admin@swiftletcare.com",
                roles=["ADMIN", "FARM_OWNER"],
            )
        ]

    def register_recipient(self, farm_id: str, recipient: RecipientInfo) -> None:
        if farm_id not in self._farm_recipients:
            self._farm_recipients[farm_id] = []
        self._farm_recipients[farm_id].append(recipient)

    def set_default_recipients(self, recipients: List[RecipientInfo]) -> None:
        self._default_recipients = list(recipients)

    def resolve_recipients(
        self,
        farm_id: str,
        zone_id: Optional[str],
        severity: AlertSeverity,
        event_type: AlertEventType,
    ) -> List[RecipientInfo]:
        recipients = self._farm_recipients.get(farm_id)
        if recipients:
            return list(recipients)
        return list(self._default_recipients)
