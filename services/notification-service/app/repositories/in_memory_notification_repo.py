import threading
from datetime import datetime, timezone
from typing import Optional, List, Dict
from app.domain.enums import NotificationDeliveryStatus
from app.ports.notification_repository import NotificationRepository
from app.schemas.canonical import Notification


class InMemoryNotificationRepository(NotificationRepository):
    """Thread-safe in-memory implementation of NotificationRepository."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._notifications: Dict[str, Notification] = {}

    def save(self, notification: Notification) -> Notification:
        with self._lock:
            notif_copy = notification.model_copy(deep=True)
            self._notifications[notification.notification_id] = notif_copy
            return notif_copy.model_copy(deep=True)

    def get_by_id(self, notification_id: str) -> Optional[Notification]:
        with self._lock:
            notif = self._notifications.get(notification_id)
            if notif is None:
                return None
            return notif.model_copy(deep=True)

    def list_by_user(
        self,
        user_id: str,
        is_read: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Notification]:
        with self._lock:
            filtered = [
                n for n in self._notifications.values() if n.user_id == user_id
            ]

            if is_read is True:
                filtered = [n for n in filtered if n.read_at is not None]
            elif is_read is False:
                filtered = [n for n in filtered if n.read_at is None]

            # Sort descending by createdAt
            filtered.sort(key=lambda n: n.created_at, reverse=True)
            page = filtered[offset : offset + limit]
            return [n.model_copy(deep=True) for n in page]

    def list_by_alert(
        self,
        alert_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Notification]:
        with self._lock:
            filtered = [
                n for n in self._notifications.values() if n.alert_id == alert_id
            ]
            filtered.sort(key=lambda n: n.created_at, reverse=True)
            page = filtered[offset : offset + limit]
            return [n.model_copy(deep=True) for n in page]

    def list_recent(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Notification]:
        with self._lock:
            filtered = list(self._notifications.values())
            filtered.sort(key=lambda n: n.created_at, reverse=True)
            page = filtered[offset : offset + limit]
            return [n.model_copy(deep=True) for n in page]

    def count_by_user(
        self,
        user_id: str,
        is_read: Optional[bool] = None,
    ) -> int:
        with self._lock:
            filtered = [
                n for n in self._notifications.values() if n.user_id == user_id
            ]

            if is_read is True:
                filtered = [n for n in filtered if n.read_at is not None]
            elif is_read is False:
                filtered = [n for n in filtered if n.read_at is None]

            return len(filtered)

    def mark_as_read(
        self,
        notification_id: str,
        user_id: str,
        read_at: Optional[datetime] = None,
    ) -> Optional[Notification]:
        with self._lock:
            notif = self._notifications.get(notification_id)
            if notif is None or notif.user_id != user_id:
                return None

            now = read_at or datetime.now(timezone.utc)
            if notif.read_at is None:
                notif.read_at = now
            return notif.model_copy(deep=True)

    def mark_all_as_read(
        self,
        user_id: str,
        read_at: Optional[datetime] = None,
    ) -> int:
        with self._lock:
            now = read_at or datetime.now(timezone.utc)
            count = 0
            for notif in self._notifications.values():
                if notif.user_id == user_id and notif.read_at is None:
                    notif.read_at = now
                    count += 1
            return count

    def update_delivery_status(
        self,
        notification_id: str,
        status: NotificationDeliveryStatus,
        failure_reason: Optional[str] = None,
    ) -> Optional[Notification]:
        with self._lock:
            notif = self._notifications.get(notification_id)
            if notif is None:
                return None

            notif.delivery_status = status
            if failure_reason is not None:
                notif.failure_reason = failure_reason
            return notif.model_copy(deep=True)
