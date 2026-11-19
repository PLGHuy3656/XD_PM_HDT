from abc import ABC, abstractmethod
from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict, Field


class FCMResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    invalid_tokens: List[str] = Field(default_factory=list)


class FCMProvider(ABC):
    """Abstract port for FCM notification dispatch."""

    @abstractmethod
    def send_single(
        self,
        token: str,
        title: str,
        body: str,
        data: Dict[str, str],
    ) -> FCMResponse:
        """Send a single push notification to one device token."""
        pass

    @abstractmethod
    def send_multicast(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Dict[str, str],
    ) -> FCMResponse:
        """Send multicast push notification to multiple device tokens."""
        pass
