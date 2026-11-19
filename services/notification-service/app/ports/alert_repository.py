from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List
from app.domain.enums import AlertStatus, AlertSeverity, AlertEventType, AlertSource
from app.schemas.canonical import Alert


class AlertRepository(ABC):
    """Abstract interface for Alert persistence."""

    @abstractmethod
    def save(self, alert: Alert) -> Alert:
        """Save or update an alert."""
        pass

    @abstractmethod
    def get_by_id(self, alert_id: str) -> Optional[Alert]:
        """Retrieve an alert by its ID."""
        pass

    @abstractmethod
    def find_active_by_dedup_key(
        self,
        farm_id: str,
        zone_id: Optional[str],
        device_id: Optional[str],
        event_type: AlertEventType,
    ) -> Optional[Alert]:
        """Find an active alert (status OPEN or ACKNOWLEDGED) matching the deduplication key."""
        pass

    @abstractmethod
    def list_alerts(
        self,
        farm_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        status: Optional[AlertStatus] = None,
        severity: Optional[AlertSeverity] = None,
        event_type: Optional[AlertEventType] = None,
        source: Optional[AlertSource] = None,
        limit: int = 100,
        offset: int = 0,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Alert]:
        """List alerts filtered by criteria, ordered by createdAt descending."""
        pass

    @abstractmethod
    def count_alerts(
        self,
        farm_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        status: Optional[AlertStatus] = None,
        severity: Optional[AlertSeverity] = None,
        event_type: Optional[AlertEventType] = None,
        source: Optional[AlertSource] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """Count alerts matching filter criteria."""
        pass
