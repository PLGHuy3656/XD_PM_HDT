import asyncio
import logging

import paho.mqtt.client as mqtt

from app.config import settings
from app.services.telemetry_service import (
    TelemetryService,
    telemetry_service,
)

logger = logging.getLogger("mqtt")

TELEMETRY_TOPIC = "swiftlet/telemetry/+/+"


def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        logger.info("Connected to MQTT broker")
        client.subscribe(TELEMETRY_TOPIC, qos=1)
        logger.info("Subscribed to %s", TELEMETRY_TOPIC)
    else:
        logger.error("MQTT connection failed: %s", reason_code)


def on_message(client, userdata, message):
    service = (
        userdata.get("telemetry_service")
        if isinstance(userdata, dict)
        else None
    )
    event_loop = (
        userdata.get("event_loop")
        if isinstance(userdata, dict)
        else None
    )

    if service is None:
        service = telemetry_service

    service.process_message(
        topic=message.topic,
        payload_bytes=message.payload,
        event_loop=event_loop,
    )


def start_mqtt(
    event_loop: asyncio.AbstractEventLoop | None = None,
    service: TelemetryService | None = None,
) -> mqtt.Client | None:
    """
    Initializes and starts the MQTT client asynchronously.
    Catches errors gracefully so FastAPI startup never crashes
    if MQTT broker is unavailable.
    """
    try:
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.mqtt_client_id,
            protocol=mqtt.MQTTv311,
            userdata={
                "event_loop": event_loop,
                "telemetry_service": service or telemetry_service,
            },
        )

        if settings.mqtt_username:
            client.username_pw_set(
                settings.mqtt_username,
                settings.mqtt_password,
            )

        client.on_connect = on_connect
        client.on_message = on_message

        client.connect_async(
            settings.mqtt_host,
            settings.mqtt_port,
            keepalive=60,
        )
        client.loop_start()
        return client

    except Exception as exc:
        logger.warning(
            "MQTT client initialization or connection failed: %s",
            exc,
        )
        return None


def stop_mqtt(client: mqtt.Client | None) -> None:
    """Gracefully disconnects and stops the MQTT loop."""
    if client is None:
        return

    try:
        client.disconnect()
        client.loop_stop()
        logger.info("MQTT client disconnected and loop stopped")
    except Exception as exc:
        logger.warning("Error stopping MQTT client: %s", exc)
