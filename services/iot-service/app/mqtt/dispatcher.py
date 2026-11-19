import logging
from typing import Callable

from app.mqtt.topics import MQTTTopic
from app.services.ack_service import AckService, ack_service
from app.services.heartbeat_service import HeartbeatService, heartbeat_service
from app.services.status_service import StatusService, status_service
from app.services.telemetry_service import TelemetryService, telemetry_service

logger = logging.getLogger("iot_service.mqtt")

HandlerFunc = Callable[[str, bytes], None]


class MessageDispatcher:
    """Routes incoming MQTT messages to domain services or placeholder handlers.

    For CP4.4:
    - telemetry: Dispatches to TelemetryService (CP4.2)
    - heartbeat: Dispatches to HeartbeatService (CP4.3)
    - status: Dispatches to StatusService (CP4.3)
    - ack: Dispatches to AckService (CP4.4)
    """

    def __init__(
        self,
        telemetry_svc: TelemetryService | None = None,
        heartbeat_svc: HeartbeatService | None = None,
        status_svc: StatusService | None = None,
        ack_svc: AckService | None = None,
    ):
        self.telemetry_service = telemetry_svc or telemetry_service
        self.heartbeat_service = heartbeat_svc or heartbeat_service
        self.status_service = status_svc or status_service
        self.ack_service = ack_svc or ack_service

        self._handlers: dict[str, HandlerFunc] = {
            "telemetry": self.handle_telemetry,
            "heartbeat": self.handle_heartbeat,
            "status": self.handle_status,
            "ack": self.handle_ack,
        }

    def register_handler(self, channel: str, handler: HandlerFunc) -> None:
        """Registers or replaces a handler for a specific channel."""
        self._handlers[channel] = handler

    def get_handler(self, channel: str) -> HandlerFunc | None:
        """Returns the currently registered handler for a channel."""
        return self._handlers.get(channel)

    def handle_telemetry(self, device_code: str, payload: bytes) -> None:
        """Processes incoming telemetry through TelemetryService."""
        self.telemetry_service.process_message(device_code, payload)

    def handle_heartbeat(self, device_code: str, payload: bytes) -> None:
        """Processes incoming heartbeat through HeartbeatService."""
        self.heartbeat_service.process_message(device_code, payload)

    def handle_status(self, device_code: str, payload: bytes) -> None:
        """Processes incoming status or LWT message through StatusService."""
        self.status_service.process_message(device_code, payload)

    def handle_ack(self, device_code: str, payload: bytes) -> None:
        """Processes incoming command acknowledgment through AckService."""
        self.ack_service.process_message(device_code, payload)

    def dispatch(self, parsed_topic: MQTTTopic, payload: bytes) -> None:
        """Dispatches a parsed topic to its registered handler."""
        channel = parsed_topic.channel
        device_code = parsed_topic.device_code

        handler = self._handlers.get(channel)
        if handler:
            handler(device_code, payload)
        elif channel == "command":
            logger.warning(
                "Received server-to-device 'command' channel message for device_code='%s'; ignoring inbound command",
                device_code,
            )
        else:
            logger.warning(
                "No handler registered for channel '%s' (device_code='%s')",
                channel,
                device_code,
            )


default_dispatcher = MessageDispatcher()
