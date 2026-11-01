import asyncio

import paho.mqtt.client as mqtt

from app.config.settings import settings
from app.mqtt.telemetry import on_connect, on_message


def start_mqtt(
    event_loop: asyncio.AbstractEventLoop,
    event_publisher=None,
) -> mqtt.Client:
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=settings.mqtt_client_id,
        protocol=mqtt.MQTTv311,
        userdata={
            "event_loop": event_loop,
            "event_publisher": event_publisher,
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