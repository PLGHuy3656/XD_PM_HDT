import logging
from typing import Protocol

import paho.mqtt.client as mqtt

from app.config import settings
from app.mqtt.dispatcher import MessageDispatcher, default_dispatcher
from app.mqtt.topics import TopicParseError, get_subscription_topics, parse_topic

logger = logging.getLogger("iot_service.mqtt")


class CommandPublisher(Protocol):
    """Protocol for sending MQTT commands."""

    def publish(
        self,
        topic: str,
        payload: str | bytes,
        qos: int = 1,
        retain: bool = False,
    ) -> bool:
        ...


class MQTTManager:
    """Manages the Paho MQTT client lifecycle, subscriptions, message routing, and publishing."""

    def __init__(self, dispatcher: MessageDispatcher | None = None):
        self.dispatcher = dispatcher or default_dispatcher
        self.client: mqtt.Client | None = None
        self._is_connected = False
        self._is_running = False

    @property
    def is_connected(self) -> bool:
        """Returns True if currently connected to the MQTT broker."""
        return self._is_connected

    @property
    def is_running(self) -> bool:
        """Returns True if the MQTT client loop is running."""
        return self._is_running

    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        """Callback fired when client connects or fails to connect to broker."""
        is_success = (reason_code == 0) or (
            hasattr(reason_code, "is_failure") and not reason_code.is_failure
        )

        if is_success:
            self._is_connected = True
            logger.info(
                "Connected to MQTT broker at %s:%s (client_id=%s)",
                settings.mqtt_broker_host,
                settings.mqtt_broker_port,
                settings.mqtt_client_id,
            )
            subscriptions = get_subscription_topics()
            for topic in subscriptions:
                client.subscribe(topic, qos=settings.mqtt_qos)
                logger.info(
                    "Subscribed to MQTT topic: %s (QoS %d)",
                    topic,
                    settings.mqtt_qos,
                )
        else:
            self._is_connected = False
            logger.warning(
                "MQTT connection failed with reason_code=%s",
                reason_code,
            )

    def on_disconnect(
        self, client, userdata, disconnect_flags, reason_code, properties=None
    ):
        """Callback fired when disconnected from the broker."""
        self._is_connected = False
        logger.info(
            "Disconnected from MQTT broker (reason_code=%s)",
            reason_code,
        )

    def on_message(self, client, userdata, message):
        """Callback fired when an MQTT message arrives on subscribed topics."""
        topic_str = message.topic
        payload = message.payload

        try:
            parsed = parse_topic(topic_str)
        except (TopicParseError, ValueError) as err:
            logger.warning(
                "Rejected malformed MQTT message on topic '%s': %s",
                topic_str,
                err,
            )
            return
        except Exception as exc:
            logger.warning(
                "Unexpected error parsing MQTT message on topic '%s': %s",
                topic_str,
                exc,
            )
            return

        try:
            self.dispatcher.dispatch(parsed, payload)
        except Exception as exc:
            logger.error(
                "Unhandled error dispatching message for topic '%s': %s",
                topic_str,
                exc,
                exc_info=True,
            )

    def publish(
        self,
        topic: str,
        payload: str | bytes,
        qos: int = 1,
        retain: bool = False,
    ) -> bool:
        """Publishes an MQTT message with QoS and retain flags."""
        if not self.client or not self._is_running:
            logger.warning(
                "Cannot publish to '%s': MQTT client is not running.",
                topic,
            )
            return False

        try:
            msg_info = self.client.publish(
                topic=topic,
                payload=payload,
                qos=qos,
                retain=retain,
            )
            return msg_info.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as exc:
            logger.warning("Failed to publish MQTT message to '%s': %s", topic, exc)
            return False

    def start(self) -> None:
        """Initializes and starts the MQTT client asynchronously."""
        if self._is_running:
            logger.debug("MQTT client is already running.")
            return

        try:
            self.client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=settings.mqtt_client_id,
                protocol=mqtt.MQTTv311,
            )

            if settings.mqtt_username:
                self.client.username_pw_set(
                    settings.mqtt_username,
                    settings.mqtt_password,
                )

            self.client.on_connect = self.on_connect
            self.client.on_disconnect = self.on_disconnect
            self.client.on_message = self.on_message

            logger.info(
                "Initializing asynchronous connection to MQTT broker at %s:%s...",
                settings.mqtt_broker_host,
                settings.mqtt_broker_port,
            )
            self.client.connect_async(
                settings.mqtt_broker_host,
                settings.mqtt_broker_port,
                keepalive=settings.mqtt_keepalive,
            )
            self.client.loop_start()
            self._is_running = True
        except Exception as exc:
            logger.warning(
                "Failed to initialize MQTT client: %s. Service will continue running without live broker.",
                exc,
            )

    def stop(self) -> None:
        """Gracefully disconnects and stops the MQTT client loop."""
        if self.client and self._is_running:
            try:
                logger.info("Stopping MQTT client loop and disconnecting...")
                self.client.loop_stop()
                self.client.disconnect()
            except Exception as exc:
                logger.warning("Error stopping MQTT client: %s", exc)
            finally:
                self._is_connected = False
                self._is_running = False


mqtt_manager = MQTTManager()
