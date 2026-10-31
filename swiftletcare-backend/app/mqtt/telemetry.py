import json
import logging

import paho.mqtt.client as mqtt
from pydantic import ValidationError

from app.schemas.telemetry import TelemetryPayload
from app.services.telemetry_service import process_telemetry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telemetry")

TOPIC = "swiftlet/telemetry/+/+"


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        logger.info("Connected to MQTT broker")

        result, _ = client.subscribe(TOPIC, qos=1)
        if result == mqtt.MQTT_ERR_SUCCESS:
            logger.info("Subscribed to %s", TOPIC)
        else:
            logger.error("Failed to subscribe to %s: rc=%s", TOPIC, result)

        ack_topic = "swiftlet/ack/+"
        result, _ = client.subscribe(ack_topic, qos=1)
        if result == mqtt.MQTT_ERR_SUCCESS:
            logger.info("Subscribed to %s", ack_topic)
        else:
            logger.error(
                "Failed to subscribe to %s: rc=%s",
                ack_topic,
                result,
            )
    else:
        logger.error("MQTT connection failed: %s", reason_code)

def on_message(client, userdata, message):
    if message.topic.startswith("swiftlet/ack/"):
        from app.mqtt.ack_handler import process_ack_message

        try:
            process_ack_message(message.topic, message.payload)
        except Exception:
            logger.exception(
                "Failed to process ACK from %s",
                message.topic,
            )
        return

    try:
        parts = message.topic.split("/")

        if len(parts) != 4 or parts[:2] != [
            "swiftlet", "telemetry"
        ]:
            raise ValueError("Invalid telemetry topic")

        house_code = parts[2]
        node_id_from_topic = parts[3]

        payload = TelemetryPayload.model_validate_json(
            message.payload
        )

        if payload.nodeId != node_id_from_topic:
            raise ValueError("nodeId does not match MQTT topic")

        loop = (
            userdata.get("event_loop")
            if isinstance(userdata, dict)
            else None
        )
        process_telemetry(house_code, payload, loop)

    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        logger.warning(
            "Rejected telemetry from %s: %s",
            message.topic,
            exc,
        )

    except Exception:
        logger.exception(
            "Failed to process telemetry from %s",
            message.topic,
        )
