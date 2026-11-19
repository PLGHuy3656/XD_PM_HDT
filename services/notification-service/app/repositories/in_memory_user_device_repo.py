import threading
from datetime import datetime, timezone
from typing import Optional, List, Dict
from app.ports.user_device_repository import UserDeviceRepository
from app.schemas.canonical import UserDevice


class InMemoryUserDeviceRepository(UserDeviceRepository):
    """Thread-safe in-memory implementation of UserDeviceRepository."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._devices: Dict[str, UserDevice] = {}

    def register_device(self, device: UserDevice) -> UserDevice:
        with self._lock:
            # Enforce fcmToken uniqueness across devices
            now = datetime.now(timezone.utc)
            dev_copy = device.model_copy(deep=True)

            to_remove = []
            for did, d in self._devices.items():
                if d.fcm_token == dev_copy.fcm_token and did != dev_copy.device_id:
                    to_remove.append(did)

            for did in to_remove:
                del self._devices[did]

            dev_copy.updated_at = now
            self._devices[dev_copy.device_id] = dev_copy
            return dev_copy.model_copy(deep=True)

    def get_by_id(self, device_id: str) -> Optional[UserDevice]:
        with self._lock:
            dev = self._devices.get(device_id)
            if dev is None:
                return None
            return dev.model_copy(deep=True)

    def get_by_token(self, fcm_token: str) -> Optional[UserDevice]:
        with self._lock:
            for dev in self._devices.values():
                if dev.fcm_token == fcm_token:
                    return dev.model_copy(deep=True)
            return None

    def list_by_user(
        self,
        user_id: str,
        is_enabled_only: bool = True,
    ) -> List[UserDevice]:
        with self._lock:
            result = [
                d for d in self._devices.values() if d.user_id == user_id
            ]
            if is_enabled_only:
                result = [d for d in result if d.is_enabled]
            return [d.model_copy(deep=True) for d in result]

    def disable_device(self, device_id: str) -> Optional[UserDevice]:
        with self._lock:
            dev = self._devices.get(device_id)
            if dev is None:
                return None
            dev.is_enabled = False
            dev.updated_at = datetime.now(timezone.utc)
            return dev.model_copy(deep=True)

    def disable_by_token(self, fcm_token: str) -> Optional[UserDevice]:
        with self._lock:
            for dev in self._devices.values():
                if dev.fcm_token == fcm_token:
                    dev.is_enabled = False
                    dev.updated_at = datetime.now(timezone.utc)
                    return dev.model_copy(deep=True)
            return None

    def delete_device(self, device_id: str) -> bool:
        with self._lock:
            if device_id in self._devices:
                del self._devices[device_id]
                return True
            return False
