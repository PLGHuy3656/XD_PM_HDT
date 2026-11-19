import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple
from app.domain.enums import (
    AlertStatus,
    AlertSeverity,
    AlertSource,
    AlertEventType,
)
from app.ports.alert_repository import AlertRepository
from app.schemas.canonical import Alert


class AlertLifecycleService:
    """Manages Alert state transitions, deduplication, and lifecycle rules."""

    def __init__(self, alert_repo: AlertRepository) -> None:
        self.alert_repo = alert_repo

    def process_incoming_alert(
        self,
        farm_id: str,
        zone_id: Optional[str],
        device_id: Optional[str],
        camera_id: Optional[str],
        event_type: AlertEventType,
        severity: AlertSeverity,
        source: AlertSource,
        title: str,
        message: str,
        snapshot_url: Optional[str] = None,
        telemetry_snapshot: Optional[dict] = None,
        occurred_at: Optional[datetime] = None,
    ) -> Tuple[Alert, bool]:
        """Process an incoming alert event with deduplication.

        Returns (alert, is_new).
        If an active alert (OPEN or ACKNOWLEDGED) already exists for this dedup key,
        it increments occurrenceCount and updates timestamps without creating a new alert.
        """
        now = occurred_at or datetime.now(timezone.utc)
        target_source_id = device_id or camera_id

        existing = self.alert_repo.find_active_by_dedup_key(
            farm_id=farm_id,
            zone_id=zone_id,
            device_id=target_source_id,
            event_type=event_type,
        )

        if existing is not None and existing.status in (AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED):
            # Deduplicate into existing active alert
            existing.occurrence_count += 1
            existing.last_occurred_at = now
            existing.updated_at = datetime.now(timezone.utc)
            if snapshot_url and not existing.snapshot_url:
                existing.snapshot_url = snapshot_url
            if telemetry_snapshot:
                existing.telemetry_snapshot = telemetry_snapshot

            saved = self.alert_repo.save(existing)
            return saved, False

        # Create brand new alert
        new_alert = Alert(
            alert_id=f"alt_{uuid.uuid4().hex[:12]}",
            farm_id=farm_id,
            zone_id=zone_id,
            device_id=device_id,
            camera_id=camera_id,
            event_type=event_type,
            severity=severity,
            status=AlertStatus.OPEN,
            source=source,
            title=title,
            message=message,
            snapshot_url=snapshot_url,
            telemetry_snapshot=telemetry_snapshot,
            created_at=now,
            last_occurred_at=now,
            updated_at=now,
            occurrence_count=1,
        )
        saved = self.alert_repo.save(new_alert)
        return saved, True

    def acknowledge(
        self,
        alert_id: str,
        acknowledged_by: str,
        acknowledged_at: Optional[datetime] = None,
    ) -> Alert:
        """Acknowledge an OPEN alert. Raises ValueError if in invalid state."""
        alert = self.alert_repo.get_by_id(alert_id)
        if alert is None:
            raise KeyError(f"Alert '{alert_id}' not found.")

        if alert.status == AlertStatus.RESOLVED:
            raise ValueError(f"Cannot acknowledge alert '{alert_id}': alert is already RESOLVED.")
        if alert.status == AlertStatus.ACKNOWLEDGED:
            raise ValueError(f"Alert '{alert_id}' is already ACKNOWLEDGED.")

        now = acknowledged_at or datetime.now(timezone.utc)
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = now
        alert.acknowledged_by = acknowledged_by
        alert.updated_at = datetime.now(timezone.utc)
        return self.alert_repo.save(alert)

    def resolve(
        self,
        alert_id: str,
        resolved_by: str,
        resolution_note: Optional[str] = None,
        resolved_at: Optional[datetime] = None,
    ) -> Alert:
        """Resolve an OPEN or ACKNOWLEDGED alert. Raises ValueError if already RESOLVED."""
        alert = self.alert_repo.get_by_id(alert_id)
        if alert is None:
            raise KeyError(f"Alert '{alert_id}' not found.")

        if alert.status == AlertStatus.RESOLVED:
            raise ValueError(f"Cannot resolve alert '{alert_id}': alert is already RESOLVED.")

        now = resolved_at or datetime.now(timezone.utc)
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = now
        alert.resolved_by = resolved_by
        alert.resolution_note = resolution_note or "Resolved by user"
        alert.updated_at = datetime.now(timezone.utc)
        return self.alert_repo.save(alert)

    def auto_resolve(
        self,
        alert: Alert,
        resolution_note: str,
        resolved_at: Optional[datetime] = None,
    ) -> Alert:
        """Auto-resolve an active alert (triggered by system hysteresis or recovery event)."""
        if alert.status == AlertStatus.RESOLVED:
            return alert

        now = resolved_at or datetime.now(timezone.utc)
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = now
        alert.resolved_by = "SYSTEM"
        alert.resolution_note = resolution_note
        alert.updated_at = datetime.now(timezone.utc)
        return self.alert_repo.save(alert)
