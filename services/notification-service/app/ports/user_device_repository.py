from abc import ABC, abstractmethod
from typing import Optional, List
from app.schemas.canonical import UserDevice


class UserDeviceRepository(ABC):
    """Abstract interface for UserDevice persistence and FCM token management."""

    @abstractmethod
    def register_device(self, device: UserDevice) -> UserDevice:
        """Register or update a user device. Enforces fcmToken uniqueness."""
        pass

    @abstractmethod
    def get_by_id(self, device_id: str) -> Optional[UserDevice]:
        """Retrieve a device by ID."""
        pass

    @abstractmethod
    def get_by_token(self, fcm_token: str) -> Optional[UserDevice]:
        """Retrieve a device by FCM token."""
        pass

    @abstractmethod
    def list_by_user(self, user_id: str, is_enabled_only: bool = True) -> List[UserDevice]:
        """List devices registered to a user."""
        pass

    @abstractmethod
    def disable_device(self, device_id: str) -> Optional[UserDevice]:
        """Disable a device by ID."""
        pass

    @abstractmethod
    def disable_by_token(self, fcm_token: str) -> Optional[UserDevice]:
        """Disable a device by FCM token (e.g. after receiving invalid token error from FCM)."""
        pass

    @abstractmethod
    def delete_device(self, device_id: str) -> bool:
        """Delete a registered device by ID."""
        pass
