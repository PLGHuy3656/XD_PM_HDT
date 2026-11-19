from abc import ABC, abstractmethod
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from app.domain.enums import AlertSeverity, AlertEventType


class RecipientInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    roles: List[str] = []


class RecipientResolver(ABC):
    """Abstract port for resolving eligible notification recipients for an alert."""

    @abstractmethod
    def resolve_recipients(
        self,
        farm_id: str,
        zone_id: Optional[str],
        severity: AlertSeverity,
        event_type: AlertEventType,
    ) -> List[RecipientInfo]:
        """Resolve recipients who should receive notification for this alert."""
        pass
