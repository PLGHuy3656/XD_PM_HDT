import threading
from datetime import datetime
from typing import Optional, List, Dict
from app.domain.enums import AlertStatus, AlertSeverity, AlertEventType, AlertSource
from app.ports.alert_repository import AlertRepository
from app.schemas.canonical import Alert, _ensure_utc


class InMemoryAlertRepository(AlertRepository):
    """Thread-safe in-memory implementation of AlertRepository."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._alerts: Dict[str, Alert] = {}

    def save(self, alert: Alert) -> Alert:
        with self._lock:
            # Model copy ensures caller cannot mutate internal state directly
            alert_copy = alert.model_copy(deep=True)
            self._alerts[alert.alert_id] = alert_copy
            return alert_copy.model_copy(deep=True)

    def get_by_id(self, alert_id: str) -> Optional[Alert]:
        with self._lock:
            alert = self._alerts.get(alert_id)
            if alert is None:
                return None
            return alert.model_copy(deep=True)

    def find_active_by_dedup_key(
        self,
        farm_id: str,
        zone_id: Optional[str],
        device_id: Optional[str],
        event_type: AlertEventType,
    ) -> Optional[Alert]:
        with self._lock:
            target_zone = zone_id or ""
            target_device = device_id or ""

            candidates = []
            for alert in self._alerts.values():
                if alert.status not in (AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED):
                    continue
                if alert.farm_id != farm_id:
                    continue
                if (alert.zone_id or "") != target_zone:
                    continue
                alert_dev = alert.device_id or alert.camera_id or ""
                if alert_dev != target_device:
                    continue
                if alert.event_type != event_type:
                    continue
                candidates.append(alert)

            if not candidates:
                return None
            # Return the latest active alert
            candidates.sort(key=lambda a: a.created_at, reverse=True)
            return candidates[0].model_copy(deep=True)

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
        with self._lock:
            filtered = list(self._alerts.values())

            if farm_id is not None:
                filtered = [a for a in filtered if a.farm_id == farm_id]
            if zone_id is not None:
                filtered = [a for a in filtered if a.zone_id == zone_id]
            if status is not None:
                filtered = [a for a in filtered if a.status == status]
            if severity is not None:
                filtered = [a for a in filtered if a.severity == severity]
            if event_type is not None:
                filtered = [a for a in filtered if a.event_type == event_type]
            if source is not None:
                filtered = [a for a in filtered if a.source == source]
            if start_time is not None:
                st = _ensure_utc(start_time)
                filtered = [a for a in filtered if a.created_at >= st]
            if end_time is not None:
                et = _ensure_utc(end_time)
                filtered = [a for a in filtered if a.created_at <= et]

            # Sort descending by createdAt
            filtered.sort(key=lambda a: a.created_at, reverse=True)
            page = filtered[offset : offset + limit]
            return [a.model_copy(deep=True) for a in page]

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
        with self._lock:
            filtered = list(self._alerts.values())

            if farm_id is not None:
                filtered = [a for a in filtered if a.farm_id == farm_id]
            if zone_id is not None:
                filtered = [a for a in filtered if a.zone_id == zone_id]
            if status is not None:
                filtered = [a for a in filtered if a.status == status]
            if severity is not None:
                filtered = [a for a in filtered if a.severity == severity]
            if event_type is not None:
                filtered = [a for a in filtered if a.event_type == event_type]
            if source is not None:
                filtered = [a for a in filtered if a.source == source]
            if start_time is not None:
                st = _ensure_utc(start_time)
                filtered = [a for a in filtered if a.created_at >= st]
            if end_time is not None:
                et = _ensure_utc(end_time)
                filtered = [a for a in filtered if a.created_at <= et]

            return len(filtered)
