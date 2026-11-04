import logging
from datetime import datetime, timezone

from app.config import settings
from app.realtime.publisher import RealtimePublisher, ws_manager
from app.repositories.presence_repository import (
    DevicePresenceRepository,
    default_presence_repository,
)
from app.schemas.api import PresenceResponse, RealtimeEvent
from app.schemas.presence import DevicePresence, HeartbeatPayload

logger = logging.getLogger("iot_service.presence")


class DevicePresenceService:
    """Manages runtime presence states, stale device evaluations, and realtime notifications."""

    def __init__(
        self,
        repository: DevicePresenceRepository | None = None,
        stale_timeout_seconds: int | None = None,
        realtime_publisher: RealtimePublisher | None = None,
    ):
        self.repository = repository or default_presence_repository
        self.stale_timeout_seconds = (
            stale_timeout_seconds
            if stale_timeout_seconds is not None
            else settings.device_stale_timeout_seconds
        )
        self.realtime_publisher: RealtimePublisher = (
            realtime_publisher or ws_manager
        )

    def _emit_presence_updated(
        self, presence: DevicePresence, timestamp: datetime
    ) -> None:
        """Publishes a presence.updated event with strict failure isolation."""
        try:
            event = RealtimeEvent(
                type="presence.updated",
                deviceId=presence.device_id,
                timestamp=timestamp,
                data=PresenceResponse.from_domain(presence).model_dump(mode="json"),
            )
            self.realtime_publisher.publish(event)
        except Exception as exc:
            logger.warning(
                "[PRESENCE REALTIME WARNING] Failed to publish presence.updated event for '%s': %s",
                presence.device_id,
                exc,
            )

    def get_presence(self, device_id: str) -> DevicePresence | None:
        """Retrieves current presence state for a device."""
        return self.repository.get(device_id)

    def record_online_status(
        self, device_id: str, timestamp: datetime | None = None
    ) -> DevicePresence:
        """Marks device ONLINE when explicit online status is received."""
        now = timestamp or datetime.now(timezone.utc)
        existing = self.repository.get(device_id)

        if existing:
            updated = existing.model_copy(
                update={
                    "status": "ONLINE",
                    "last_status_at": now,
                    "last_seen": now,
                }
            )
        else:
            updated = DevicePresence(
                device_id=device_id,
                status="ONLINE",
                last_status_at=now,
                last_seen=now,
            )

        self.repository.save(updated)
        logger.info("[PRESENCE] Device '%s' marked ONLINE via status", device_id)
        self._emit_presence_updated(updated, now)
        return updated

    def record_offline_status(
        self, device_id: str, timestamp: datetime | None = None
    ) -> DevicePresence:
        """Marks device OFFLINE when explicit status or MQTT LWT is received."""
        now = timestamp or datetime.now(timezone.utc)
        existing = self.repository.get(device_id)

        if existing:
            updated = existing.model_copy(
                update={
                    "status": "OFFLINE",
                    "last_status_at": now,
                    "last_seen": now,
                }
            )
        else:
            updated = DevicePresence(
                device_id=device_id,
                status="OFFLINE",
                last_status_at=now,
                last_seen=now,
            )

        self.repository.save(updated)
        logger.info("[PRESENCE] Device '%s' marked OFFLINE via status/LWT", device_id)
        self._emit_presence_updated(updated, now)
        return updated

    def record_heartbeat(
        self,
        device_id: str,
        heartbeat: HeartbeatPayload,
        timestamp: datetime | None = None,
    ) -> DevicePresence:
        """Records a valid heartbeat, marking device ONLINE and updating runtime stats."""
        now = timestamp or datetime.now(timezone.utc)
        existing = self.repository.get(device_id)

        updates = {
            "status": "ONLINE",
            "uptime": heartbeat.uptime,
            "ip": heartbeat.ip,
            "free_heap": heartbeat.freeHeap,
            "mock_mode": heartbeat.mockMode,
            "last_heartbeat_at": now,
            "last_seen": now,
        }

        if existing:
            updated = existing.model_copy(update=updates)
        else:
            updated = DevicePresence(
                device_id=device_id,
                **updates,
            )

        self.repository.save(updated)
        logger.info(
            "[PRESENCE] Device '%s' heartbeat recorded (uptime=%ds, ip=%s) -> ONLINE",
            device_id,
            heartbeat.uptime,
            heartbeat.ip,
        )
        self._emit_presence_updated(updated, now)
        return updated

    def evaluate_stale_devices(
        self,
        now: datetime | None = None,
        timeout_seconds: int | None = None,
    ) -> list[DevicePresence]:
        """Evaluates devices currently ONLINE. If the elapsed time since last heartbeat

        exceeds timeout, marks the device as STALE.
        Explicit OFFLINE devices remain strictly OFFLINE.
        """
        current_time = now or datetime.now(timezone.utc)
        timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else self.stale_timeout_seconds
        )

        stale_devices: list[DevicePresence] = []
        for presence in self.repository.list_all():
            # Only ONLINE devices transition to STALE
            if presence.status != "ONLINE":
                continue

            ref_time = presence.last_heartbeat_at or presence.last_seen
            if ref_time and (current_time - ref_time).total_seconds() > timeout:
                stale_presence = presence.model_copy(update={"status": "STALE"})
                self.repository.save(stale_presence)
                stale_devices.append(stale_presence)
                logger.warning(
                    "[PRESENCE] Device '%s' transitioned to STALE (no heartbeat for >%ds)",
                    presence.device_id,
                    timeout,
                )
                self._emit_presence_updated(stale_presence, current_time)

        return stale_devices

    def list_all(self) -> list[DevicePresence]:
        """Returns all tracked device presence records."""
        return self.repository.list_all()


presence_service = DevicePresenceService()
