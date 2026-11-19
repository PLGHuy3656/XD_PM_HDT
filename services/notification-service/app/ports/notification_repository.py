from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List
from app.domain.enums import NotificationDeliveryStatus
from app.schemas.canonical import Notification


class NotificationRepository(ABC):
    """Abstract interface for Notification persistence."""

    @abstractmethod
    def save(self, notification: Notification) -> Notification:
        """Save or update a notification."""
        pass

    @abstractmethod
    def get_by_id(self, notification_id: str) -> Optional[Notification]:
        """Retrieve a notification by ID."""
        pass

    @abstractmethod
    def list_by_user(
        self,
        user_id: str,
        is_read: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Notification]:
        """List notifications for a specific user, sorted by createdAt descending."""
        pass

    def list_by_alert(
        self,
        alert_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Notification]:
        """List notifications associated with a specific alert, sorted by createdAt descending."""
        raise NotImplementedError

    @abstractmethod
    def count_by_user(
        self,
        user_id: str,
        is_read: Optional[bool] = None,
    ) -> int:
        """Count notifications for a user."""
        pass

    @abstractmethod
    def mark_as_read(
        self,
        notification_id: str,
        user_id: str,
        read_at: Optional[datetime] = None,
    ) -> Optional[Notification]:
        """Mark a notification as read. Returns updated notification if found and user matches."""
        pass

    @abstractmethod
    def mark_all_as_read(
        self,
        user_id: str,
        read_at: Optional[datetime] = None,
    ) -> int:
        """Mark all unread notifications for a user as read. Returns count of modified records."""
        pass

    @abstractmethod
    def update_delivery_status(
        self,
        notification_id: str,
        status: NotificationDeliveryStatus,
        failure_reason: Optional[str] = None,
    ) -> Optional[Notification]:
        """Update notification delivery status."""
        pass
