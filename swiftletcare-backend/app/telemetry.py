import asyncio
import json
import logging
from datetime import datetime, timezone


import paho.mqtt.client as mqtt
from pydantic import ValidationError
from psycopg.types.json import Jsonb

from app.config import settings
from app.database import get_connection
from app.schemas import TelemetryPayload
from app.realtime import realtime_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telemetry")

TOPIC = "swiftlet/telemetry/+/+"


def save_telemetry(
    house_code: str,
    payload: TelemetryPayload,
) -> None:
    recorded_at = datetime.fromtimestamp(
        payload.timestamp,
        tz=timezone.utc,
    )

    # Không cho phép timestamp lệch quá xa về tương lai.
    now = datetime.now(timezone.utc)
    if (recorded_at - now).total_seconds() > 300:
        raise ValueError("Telemetry timestamp is too far in the future")

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Xác minh node có đăng ký và thuộc đúng nhà yến.
            cur.execute(
                """
                SELECT d.id, z.zone_code
                FROM public.devices d
                JOIN public.houses h ON h.id = d.house_id
                JOIN public.zones z ON z.id = d.zone_id
                WHERE d.node_id = %s
                  AND h.house_code = %s
                  AND d.is_active = TRUE
                  AND z.house_id = h.id
                """,
                (payload.nodeId, house_code),
            )

            device = cur.fetchone()

            if device is None:
                raise ValueError(
                    "Unknown, inactive, or mismatched device"
                )

            device_id = device[0]
            metrics = payload.metrics.model_dump(by_alias=True)
            actuators = payload.actuators.model_dump()
            state = payload.state.model_dump()

            # Lưu lịch sử telemetry.
            cur.execute(
                """
                INSERT INTO public.telemetry (
                    device_id, recorded_at,
                    temperature, humidity, lux, co2,
                    audio_rms, audio_healthy,
                    actuators, device_state, raw_payload
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s
                )
                """,
                (
                    device_id,
                    recorded_at,
                    metrics["temperature"],
                    metrics["humidity"],
                    metrics["lux"],
                    metrics["co2"],
                    metrics["audioRms"],
                    metrics["audioHealthy"],
                    Jsonb(actuators),
                    Jsonb(state),
                    Jsonb(payload.model_dump(by_alias=True)),
                ),
            )

            # Cập nhật trạng thái mới nhất của thiết bị.
            cur.execute(
                """
                INSERT INTO public.device_latest_state (
                    device_id, recorded_at,
                    temperature, humidity, lux, co2,
                    audio_rms, audio_healthy,
                    actuators, device_state
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s
                )
                ON CONFLICT (device_id) DO UPDATE SET
                    recorded_at = EXCLUDED.recorded_at,
                    received_at = now(),
                    temperature = EXCLUDED.temperature,
                    humidity = EXCLUDED.humidity,
                    lux = EXCLUDED.lux,
                    co2 = EXCLUDED.co2,
                    audio_rms = EXCLUDED.audio_rms,
                    audio_healthy = EXCLUDED.audio_healthy,
                    actuators = EXCLUDED.actuators,
                    device_state = EXCLUDED.device_state
                WHERE EXCLUDED.recorded_at
                      >= device_latest_state.recorded_at
                """,
                (
                    device_id,
                    recorded_at,
                    metrics["temperature"],
                    metrics["humidity"],
                    metrics["lux"],
                    metrics["co2"],
                    metrics["audioRms"],
                    metrics["audioHealthy"],
                    Jsonb(actuators),
                    Jsonb(state),
                ),
            )

    logger.info(
        "Saved telemetry: node=%s house=%s",
        payload.nodeId,
        house_code,
    )


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        logger.info("Connected to MQTT broker")
        client.subscribe(TOPIC, qos=1)
        logger.info("Subscribed to %s", TOPIC)
    else:
        logger.error("MQTT connection failed: %s", reason_code)



def on_message(client, userdata, message):
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

        # Chỉ phát realtime sau khi lưu thành công.
        save_telemetry(house_code, payload)

        loop = (
            userdata.get("event_loop")
            if isinstance(userdata, dict)
            else None
        )

        if loop is None or not loop.is_running():
            logger.warning(
                "Telemetry saved, but realtime event loop is unavailable"
            )
            return

        realtime_data = {
            "type": "telemetry",
            "houseCode": house_code,
            "nodeId": payload.nodeId,
            "timestamp": payload.timestamp,
            "metrics": payload.metrics.model_dump(by_alias=True),
            "actuators": payload.actuators.model_dump(),
            "state": payload.state.model_dump(),
        }

        future = asyncio.run_coroutine_threadsafe(
            realtime_manager.broadcast(realtime_data),
            loop,
        )

        def log_broadcast_result(result):
            try:
                result.result()
            except Exception:
                logger.exception("Failed to broadcast telemetry")

        future.add_done_callback(log_broadcast_result)

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

def start_mqtt(event_loop):
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=settings.mqtt_client_id,
        protocol=mqtt.MQTTv311,
        userdata={"event_loop": event_loop},
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
