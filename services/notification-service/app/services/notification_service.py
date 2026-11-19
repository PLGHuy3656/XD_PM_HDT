import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from app.domain.enums import (
    AlertEventType,
    NotificationChannel,
    NotificationDeliveryStatus,
    AlertStatus,
    AlertSeverity,
    AlertSource,
)
from app.ports.alert_repository import AlertRepository
from app.ports.notification_repository import NotificationRepository
from app.ports.user_device_repository import UserDeviceRepository
from app.ports.recipient_resolver import RecipientResolver
from app.ports.fcm_provider import FCMProvider
from app.ports.event_sink import NotificationDomainEventSink
from app.config.alert_rules import AlertRuleConfigProvider
from app.schemas.canonical import Alert, Notification, UserDevice
from app.schemas.events import (
    AIAlertInputEvent,
    IoTTelemetryAlertInputEvent,
    IoTPresenceAlertInputEvent,
    IoTCommandAlertInputEvent,
)
from app.services.alert_lifecycle_service import AlertLifecycleService
from app.services.alert_rule_engine import (
    AlertRuleEngine,
    AlertTrigger,
    AlertAutoResolveAction,
)


class NotificationService:
    """Top-level application facade for Alert domain logic and Notification dispatch."""

    def __init__(
        self,
        alert_repo: AlertRepository,
        notification_repo: NotificationRepository,
        user_device_repo: UserDeviceRepository,
        rule_config_provider: AlertRuleConfigProvider,
        recipient_resolver: RecipientResolver,
        fcm_provider: FCMProvider,
        event_sink: Optional[NotificationDomainEventSink] = None,
    ) -> None:
        self.alert_repo = alert_repo
        self.notification_repo = notification_repo
        self.user_device_repo = user_device_repo
        self.rule_config_provider = rule_config_provider
        self.recipient_resolver = recipient_resolver
        self.fcm_provider = fcm_provider
        self.event_sink = event_sink

        self.lifecycle_service = AlertLifecycleService(alert_repo=self.alert_repo)
        self.rule_engine = AlertRuleEngine(config_provider=self.rule_config_provider)

    def set_event_sink(self, event_sink: Optional[NotificationDomainEventSink]) -> None:
        self.event_sink = event_sink

    def _notify_alert_created(self, alert: Alert) -> None:
        if self.event_sink:
            try:
                self.event_sink.on_alert_created(alert)
            except Exception:
                pass

    def _notify_alert_updated(self, alert: Alert) -> None:
        if self.event_sink:
            try:
                self.event_sink.on_alert_updated(alert)
            except Exception:
                pass

    def _notify_notification_created(self, notification: Notification) -> None:
        if self.event_sink:
            try:
                self.event_sink.on_notification_created(notification)
            except Exception:
                pass

    def _notify_notification_updated(self, notification: Notification) -> None:
        if self.event_sink:
            try:
                self.event_sink.on_notification_updated(notification)
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Domain Event Handlers
    # -------------------------------------------------------------------------

    def handle_ai_event(self, event: AIAlertInputEvent) -> List[Alert]:
        """Ingest AI predator detection events."""
        triggers = self.rule_engine.evaluate_ai_event(event)
        results: List[Alert] = []

        for trigger in triggers:
            alert, is_new = self.lifecycle_service.process_incoming_alert(
                farm_id=trigger.farm_id,
                zone_id=trigger.zone_id,
                device_id=trigger.device_id,
                camera_id=trigger.camera_id,
                event_type=trigger.event_type,
                severity=trigger.severity,
                source=trigger.source,
                title=trigger.title,
                message=trigger.message,
                snapshot_url=trigger.snapshot_url,
                telemetry_snapshot=trigger.telemetry_snapshot,
                occurred_at=trigger.occurred_at,
            )
            if is_new:
                self._notify_alert_created(alert)
                self._dispatch_notifications_for_alert(alert)
            else:
                self._notify_alert_updated(alert)
            results.append(alert)

        return results

    def handle_telemetry_event(
        self,
        event: IoTTelemetryAlertInputEvent,
    ) -> Tuple[List[Alert], List[Alert]]:
        """Ingest IoT telemetry events (with threshold checks and hysteresis auto-recovery)."""
        def active_lookup(et: AlertEventType) -> Optional[Alert]:
            return self.alert_repo.find_active_by_dedup_key(
                farm_id=event.farm_id,
                zone_id=event.zone_id,
                device_id=event.device_id,
                event_type=et,
            )

        triggers, resolves = self.rule_engine.evaluate_telemetry_event(
            event,
            active_alert_lookup=active_lookup,
        )

        resolved_alerts: List[Alert] = []
        for resolve_action in resolves:
            res_alert = self.lifecycle_service.auto_resolve(
                alert=resolve_action.alert_to_resolve,
                resolution_note=resolve_action.resolution_note,
                resolved_at=resolve_action.resolved_at,
            )
            self._notify_alert_updated(res_alert)
            resolved_alerts.append(res_alert)

        triggered_alerts: List[Alert] = []
        for trigger in triggers:
            alert, is_new = self.lifecycle_service.process_incoming_alert(
                farm_id=trigger.farm_id,
                zone_id=trigger.zone_id,
                device_id=trigger.device_id,
                camera_id=trigger.camera_id,
                event_type=trigger.event_type,
                severity=trigger.severity,
                source=trigger.source,
                title=trigger.title,
                message=trigger.message,
                snapshot_url=trigger.snapshot_url,
                telemetry_snapshot=trigger.telemetry_snapshot,
                occurred_at=trigger.occurred_at,
            )
            if is_new:
                self._notify_alert_created(alert)
                self._dispatch_notifications_for_alert(alert)
            else:
                self._notify_alert_updated(alert)
            triggered_alerts.append(alert)

        return triggered_alerts, resolved_alerts

    def handle_presence_event(
        self,
        event: IoTPresenceAlertInputEvent,
    ) -> Tuple[List[Alert], List[Alert]]:
        """Ingest IoT device presence events (OFFLINE triggers, ONLINE auto-resolves)."""
        def active_lookup(et: AlertEventType) -> Optional[Alert]:
            return self.alert_repo.find_active_by_dedup_key(
                farm_id=event.farm_id,
                zone_id=event.zone_id,
                device_id=event.device_id,
                event_type=et,
            )

        triggers, resolves = self.rule_engine.evaluate_presence_event(
            event,
            active_alert_lookup=active_lookup,
        )

        resolved_alerts: List[Alert] = []
        for resolve_action in resolves:
            res_alert = self.lifecycle_service.auto_resolve(
                alert=resolve_action.alert_to_resolve,
                resolution_note=resolve_action.resolution_note,
                resolved_at=resolve_action.resolved_at,
            )
            self._notify_alert_updated(res_alert)
            resolved_alerts.append(res_alert)

        triggered_alerts: List[Alert] = []
        for trigger in triggers:
            alert, is_new = self.lifecycle_service.process_incoming_alert(
                farm_id=trigger.farm_id,
                zone_id=trigger.zone_id,
                device_id=trigger.device_id,
                camera_id=trigger.camera_id,
                event_type=trigger.event_type,
                severity=trigger.severity,
                source=trigger.source,
                title=trigger.title,
                message=trigger.message,
                snapshot_url=trigger.snapshot_url,
                telemetry_snapshot=trigger.telemetry_snapshot,
                occurred_at=trigger.occurred_at,
            )
            if is_new:
                self._notify_alert_created(alert)
                self._dispatch_notifications_for_alert(alert)
            else:
                self._notify_alert_updated(alert)
            triggered_alerts.append(alert)

        return triggered_alerts, resolved_alerts

    def handle_command_event(
        self,
        event: IoTCommandAlertInputEvent,
    ) -> List[Alert]:
        """Ingest IoT command events (only terminal failures trigger alerts; never auto-resolves)."""
        triggers = self.rule_engine.evaluate_command_event(event)
        results: List[Alert] = []

        for trigger in triggers:
            alert, is_new = self.lifecycle_service.process_incoming_alert(
                farm_id=trigger.farm_id,
                zone_id=trigger.zone_id,
                device_id=trigger.device_id,
                camera_id=trigger.camera_id,
                event_type=trigger.event_type,
                severity=trigger.severity,
                source=trigger.source,
                title=trigger.title,
                message=trigger.message,
                snapshot_url=trigger.snapshot_url,
                telemetry_snapshot=trigger.telemetry_snapshot,
                occurred_at=trigger.occurred_at,
            )
            if is_new:
                self._notify_alert_created(alert)
                self._dispatch_notifications_for_alert(alert)
            else:
                self._notify_alert_updated(alert)
            results.append(alert)

        return results

    def handle_condition_transition(
        self,
        event_type: AlertEventType,
        is_recovery: bool,
        farm_id: str,
        zone_id: Optional[str],
        device_id: Optional[str],
        title: str,
        message: str,
        severity: AlertSeverity,
        source: AlertSource = AlertSource.IOT_ENVIRONMENT,
        telemetry_snapshot: Optional[dict] = None,
        resolution_note: Optional[str] = None,
        occurred_at: Optional[datetime] = None,
    ) -> Optional[Alert]:
        """Ingest pre-evaluated condition transition events from messaging consumer (CP7.4)."""
        now = occurred_at or datetime.now(timezone.utc)
        if not is_recovery:
            alert, is_new = self.lifecycle_service.process_incoming_alert(
                farm_id=farm_id,
                zone_id=zone_id,
                device_id=device_id,
                camera_id=None,
                event_type=event_type,
                severity=severity,
                source=source,
                title=title,
                message=message,
                telemetry_snapshot=telemetry_snapshot,
                occurred_at=now,
            )
            if is_new:
                self._notify_alert_created(alert)
                self._dispatch_notifications_for_alert(alert)
            else:
                self._notify_alert_updated(alert)
            return alert
        else:
            active = self.alert_repo.find_active_by_dedup_key(
                farm_id=farm_id,
                zone_id=zone_id,
                device_id=device_id,
                event_type=event_type,
            )
            if active is not None:
                res_alert = self.lifecycle_service.auto_resolve(
                    alert=active,
                    resolution_note=resolution_note or f"Auto-recovered: {title}",
                    resolved_at=now,
                )
                self._notify_alert_updated(res_alert)
                return res_alert
            return None

    # -------------------------------------------------------------------------
    # Notification Dispatching
    # -------------------------------------------------------------------------

    def _dispatch_notifications_for_alert(self, alert: Alert) -> List[Notification]:
        """Resolve eligible recipients and dispatch IN_APP and FCM notifications."""
        recipients = self.recipient_resolver.resolve_recipients(
            farm_id=alert.farm_id,
            zone_id=alert.zone_id,
            severity=alert.severity,
            event_type=alert.event_type,
        )

        now = datetime.now(timezone.utc)
        created_notifications: List[Notification] = []

        payload_data: Dict[str, str] = {
            "farmId": alert.farm_id,
            "alertId": alert.alert_id,
            "eventType": alert.event_type.value,
            "severity": alert.severity.value,
        }
        if alert.zone_id:
            payload_data["zoneId"] = alert.zone_id
        if alert.device_id:
            payload_data["deviceId"] = alert.device_id
        if alert.camera_id:
            payload_data["cameraId"] = alert.camera_id
        if alert.snapshot_url:
            payload_data["snapshotUrl"] = alert.snapshot_url

        for recipient in recipients:
            # 1. IN_APP Notification
            in_app_notif = Notification(
                notification_id=f"ntf_{uuid.uuid4().hex[:12]}",
                user_id=recipient.user_id,
                alert_id=alert.alert_id,
                channel=NotificationChannel.IN_APP,
                title=alert.title,
                body=alert.message,
                delivery_status=NotificationDeliveryStatus.SENT,
                created_at=now,
                read_at=None,
                data=payload_data,
            )
            saved_in_app = self.notification_repo.save(in_app_notif)
            self._notify_notification_created(saved_in_app)
            created_notifications.append(saved_in_app)

            # 2. FCM Push Notification for each enabled device of recipient
            devices = self.user_device_repo.list_by_user(recipient.user_id, is_enabled_only=True)
            for device in devices:
                fcm_notif = Notification(
                    notification_id=f"ntf_{uuid.uuid4().hex[:12]}",
                    user_id=recipient.user_id,
                    alert_id=alert.alert_id,
                    channel=NotificationChannel.FCM,
                    title=alert.title,
                    body=alert.message,
                    delivery_status=NotificationDeliveryStatus.PENDING,
                    created_at=now,
                    read_at=None,
                    data=payload_data,
                )
                saved_fcm = self.notification_repo.save(fcm_notif)

                # Dispatch via FCM provider
                fcm_res = self.fcm_provider.send_single(
                    token=device.fcm_token,
                    title=alert.title,
                    body=alert.message,
                    data=payload_data,
                )

                if fcm_res.success:
                    # Successfully sent to FCM gateway
                    updated_fcm = self.notification_repo.update_delivery_status(
                        notification_id=saved_fcm.notification_id,
                        status=NotificationDeliveryStatus.SENT,
                    )
                    final_fcm = updated_fcm or saved_fcm
                else:
                    # Delivery failed
                    updated_fcm = self.notification_repo.update_delivery_status(
                        notification_id=saved_fcm.notification_id,
                        status=NotificationDeliveryStatus.FAILED,
                        failure_reason=fcm_res.error or "FCM dispatch error",
                    )
                    final_fcm = updated_fcm or saved_fcm

                    # Disable token if unregistered/invalid
                    if device.fcm_token in fcm_res.invalid_tokens:
                        self.user_device_repo.disable_by_token(device.fcm_token)

                self._notify_notification_created(final_fcm)
                created_notifications.append(final_fcm)

        return created_notifications

    # -------------------------------------------------------------------------
    # Alert Lifecycle Operations
    # -------------------------------------------------------------------------

    def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str,
        acknowledged_at: Optional[datetime] = None,
    ) -> Alert:
        alert = self.lifecycle_service.acknowledge(
            alert_id=alert_id,
            acknowledged_by=acknowledged_by,
            acknowledged_at=acknowledged_at,
        )
        self._notify_alert_updated(alert)
        return alert

    def resolve_alert(
        self,
        alert_id: str,
        resolved_by: str,
        resolution_note: Optional[str] = None,
        resolved_at: Optional[datetime] = None,
    ) -> Alert:
        alert = self.lifecycle_service.resolve(
            alert_id=alert_id,
            resolved_by=resolved_by,
            resolution_note=resolution_note,
            resolved_at=resolved_at,
        )
        self._notify_alert_updated(alert)
        return alert

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        return self.alert_repo.get_by_id(alert_id)

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
        return self.alert_repo.list_alerts(
            farm_id=farm_id,
            zone_id=zone_id,
            status=status,
            severity=severity,
            event_type=event_type,
            source=source,
            limit=limit,
            offset=offset,
            start_time=start_time,
            end_time=end_time,
        )

    # -------------------------------------------------------------------------
    # Notification Read State Operations
    # -------------------------------------------------------------------------

    def mark_notification_as_read(
        self,
        notification_id: str,
        user_id: str,
        read_at: Optional[datetime] = None,
    ) -> Optional[Notification]:
        notif = self.notification_repo.mark_as_read(
            notification_id=notification_id,
            user_id=user_id,
            read_at=read_at,
        )
        if notif:
            self._notify_notification_updated(notif)
        return notif

    def mark_all_notifications_as_read(
        self,
        user_id: str,
        read_at: Optional[datetime] = None,
    ) -> int:
        # Fetch unread notifications first so we can dispatch update events
        unread_before = self.notification_repo.list_by_user(user_id=user_id, is_read=False, limit=500)
        count = self.notification_repo.mark_all_as_read(
            user_id=user_id,
            read_at=read_at,
        )
        # Dispatch notification.updated for each updated notification
        for n in unread_before:
            updated = self.notification_repo.get_by_id(n.notification_id)
            if updated:
                self._notify_notification_updated(updated)
        return count

    def list_notifications(
        self,
        user_id: str,
        is_read: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Notification]:
        return self.notification_repo.list_by_user(
            user_id=user_id,
            is_read=is_read,
            limit=limit,
            offset=offset,
        )

    def list_notifications_by_alert(
        self,
        alert_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Notification]:
        return self.notification_repo.list_by_alert(
            alert_id=alert_id,
            limit=limit,
            offset=offset,
        )

    # -------------------------------------------------------------------------
    # User Device Operations
    # -------------------------------------------------------------------------

    def register_device(self, device: UserDevice) -> UserDevice:
        return self.user_device_repo.register_device(device)

    def list_user_devices(
        self,
        user_id: str,
        is_enabled_only: bool = True,
    ) -> List[UserDevice]:
        return self.user_device_repo.list_by_user(
            user_id=user_id,
            is_enabled_only=is_enabled_only,
        )

    def disable_device(self, device_id: str) -> Optional[UserDevice]:
        return self.user_device_repo.disable_device(device_id)
