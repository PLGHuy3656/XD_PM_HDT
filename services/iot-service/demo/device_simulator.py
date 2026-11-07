"""Canonical V1 ESP32 Device Simulator for SwiftletCare IoT Service E2E Demo.

Simulates device: SWC-NODE-001
- Configures MQTT LWT: swiftlet/status/SWC-NODE-001 -> {"status":"offline"} (retained=True)
- On connect:
  - Publishes retained {"status":"online"} to swiftlet/status/SWC-NODE-001
  - Subscribes to swiftlet/command/SWC-NODE-001 (QoS 1)
- Periodically publishes canonical V1 heartbeat and telemetry
- Processes SET_RELAY and UPDATE_THRESHOLDS commands and replies with canonical V1 ACKs

Usage:
    python services/iot-service/demo/device_simulator.py --host 127.0.0.1 --port 1883
"""

import argparse
import json
import logging
import random
import time
from typing import Any

import paho.mqtt.client as mqtt

from app.mqtt.topics import build_topic

logger = logging.getLogger("demo.simulator")

ALLOWED_RELAYS = ("misting", "fan", "heater", "alarm")


class ESP32DeviceSimulator:
    """Simulates a canonical V1 ESP32 edge controller node."""

    def __init__(
        self,
        device_id: str = "SWC-NODE-001",
        broker_host: str = "127.0.0.1",
        broker_port: int = 1883,
        ip_address: str = "192.168.1.100",
    ):
        self.device_id = device_id
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.ip_address = ip_address
        self.boot_monotonic = time.monotonic()

        # Simulated runtime state
        self.mode: str = "AUTO"
        self.target_temp: float = 29.0
        self.target_hum: float = 80.0
        self.actuators: dict[str, bool] = {
            "misting": False,
            "fan": False,
            "heater": False,
            "alarm": False,
        }
        self.temperature: float = 29.2
        self.humidity: float = 80.5
        self.lux: float = 15.0
        self.co2: float = 620.0
        self.audio_rms: float = 0.31
        self.audio_healthy: bool = True
        self.network_rssi: int = -51
        self.free_heap: int = 183420

        # Canonical V1 topics
        self.topic_telemetry = build_topic("telemetry", self.device_id)
        self.topic_heartbeat = build_topic("heartbeat", self.device_id)
        self.topic_status = build_topic("status", self.device_id)
        self.topic_command = build_topic("command", self.device_id)
        self.topic_ack = build_topic("ack", self.device_id)

        self.client: mqtt.Client | None = None
        self.is_connected: bool = False
        self.received_commands: list[dict[str, Any]] = []

    @property
    def uptime_seconds(self) -> int:
        return max(0, int(time.monotonic() - self.boot_monotonic))

    def build_telemetry_payload(self, vary: bool = False) -> dict[str, Any]:
        if vary:
            self.temperature = round(
                min(33.0, max(25.0, self.temperature + random.uniform(-0.2, 0.2))),
                2,
            )
            self.humidity = round(
                min(92.0, max(65.0, self.humidity + random.uniform(-0.4, 0.4))),
                2,
            )
            self.co2 = round(
                min(900.0, max(420.0, self.co2 + random.uniform(-5.0, 5.0))),
                1,
            )

        return {
            "deviceId": self.device_id,
            "metrics": {
                "temperature": self.temperature,
                "humidity": self.humidity,
                "lux": self.lux,
                "co2": self.co2,
                "audioRms": self.audio_rms,
                "audioHealthy": self.audio_healthy,
            },
            "actuators": dict(self.actuators),
            "state": {
                "mode": self.mode,
                "networkRssi": self.network_rssi,
                "freeHeap": self.free_heap,
            },
        }

    def build_heartbeat_payload(self) -> dict[str, Any]:
        return {
            "deviceId": self.device_id,
            "uptime": self.uptime_seconds,
            "ip": self.ip_address,
            "freeHeap": self.free_heap,
            "mockMode": True,
        }

    def publish_online_status(self) -> None:
        if not self.client:
            return
        payload = json.dumps({"status": "online"})
        self.client.publish(self.topic_status, payload, qos=1, retain=True)
        logger.info("[SIMULATOR] Published retained ONLINE status -> %s", self.topic_status)

    def publish_offline_status(self) -> None:
        if not self.client:
            return
        payload = json.dumps({"status": "offline"})
        self.client.publish(self.topic_status, payload, qos=1, retain=True)
        logger.info("[SIMULATOR] Published retained OFFLINE status -> %s", self.topic_status)

    def publish_heartbeat(self) -> dict[str, Any]:
        payload_dict = self.build_heartbeat_payload()
        if self.client:
            self.client.publish(
                self.topic_heartbeat, json.dumps(payload_dict), qos=1, retain=False
            )
            logger.info(
                "[SIMULATOR] Published HEARTBEAT (uptime=%ds) -> %s",
                payload_dict["uptime"],
                self.topic_heartbeat,
            )
        return payload_dict

    def publish_telemetry(self, vary: bool = False) -> dict[str, Any]:
        payload_dict = self.build_telemetry_payload(vary=vary)
        if self.client:
            self.client.publish(
                self.topic_telemetry, json.dumps(payload_dict), qos=1, retain=False
            )
            logger.info(
                "[SIMULATOR] Published TELEMETRY (temp=%.2fC, hum=%.2f%%, fan=%s, mode=%s) -> %s",
                payload_dict["metrics"]["temperature"],
                payload_dict["metrics"]["humidity"],
                payload_dict["actuators"]["fan"],
                payload_dict["state"]["mode"],
                self.topic_telemetry,
            )
        return payload_dict

    def _publish_ack(
        self, command_id: str, status: str, message: str
    ) -> dict[str, Any]:
        ack_dict = {
            "commandId": command_id,
            "deviceId": self.device_id,
            "status": status,
            "mode": self.mode,
            "message": message,
        }
        if self.client:
            self.client.publish(
                self.topic_ack, json.dumps(ack_dict), qos=1, retain=False
            )
            logger.info(
                "[SIMULATOR] Published ACK (commandId=%s, status=%s, mode=%s) -> %s",
                command_id,
                status,
                self.mode,
                self.topic_ack,
            )
        return ack_dict

    def handle_command_payload(self, raw_payload: bytes | str) -> dict[str, Any] | None:
        """Processes an incoming command JSON payload and emits a canonical V1 ACK."""
        try:
            text = (
                raw_payload.decode("utf-8")
                if isinstance(raw_payload, (bytes, bytearray))
                else raw_payload
            )
            cmd = json.loads(text)
        except Exception as exc:
            logger.warning("[SIMULATOR] Malformed command JSON: %s", exc)
            return None

        if not isinstance(cmd, dict):
            return None

        self.received_commands.append(cmd)
        command_id = cmd.get("commandId")
        action = cmd.get("action")
        logger.info("[SIMULATOR] Received command on %s: %s", self.topic_command, cmd)

        if not isinstance(command_id, str) or not command_id:
            logger.warning("[SIMULATOR] Command missing commandId; cannot send ACK")
            return None

        if action == "SET_RELAY":
            target = cmd.get("target")
            state = cmd.get("state")
            if target not in ALLOWED_RELAYS or state not in (0, 1) or isinstance(state, bool):
                return self._publish_ack(
                    command_id=command_id,
                    status="FAILED",
                    message=f"Invalid SET_RELAY target='{target}' or state='{state}'",
                )

            self.actuators[target] = bool(state)
            self.mode = "MANUAL"
            state_label = "ON" if state == 1 else "OFF"
            return self._publish_ack(
                command_id=command_id,
                status="SUCCESS",
                message=f"Actuator '{target}' set to {state_label}; mode switched to MANUAL",
            )

        elif action == "UPDATE_THRESHOLDS":
            target_temp = cmd.get("targetTemp")
            target_hum = cmd.get("targetHum")
            is_auto_mode = cmd.get("isAutoMode")

            if (
                not isinstance(target_temp, (int, float))
                or isinstance(target_temp, bool)
                or not isinstance(target_hum, (int, float))
                or isinstance(target_hum, bool)
                or not isinstance(is_auto_mode, bool)
                or not (0.0 <= float(target_hum) <= 100.0)
            ):
                return self._publish_ack(
                    command_id=command_id,
                    status="FAILED",
                    message="Invalid UPDATE_THRESHOLDS parameters",
                )

            self.target_temp = float(target_temp)
            self.target_hum = float(target_hum)
            self.mode = "AUTO" if is_auto_mode else "MANUAL"
            return self._publish_ack(
                command_id=command_id,
                status="SUCCESS",
                message=(
                    f"Thresholds updated (targetTemp={self.target_temp}C, "
                    f"targetHum={self.target_hum}%); mode={self.mode}"
                ),
            )

        elif action == "PROVISION_DEVICE":
            farm_id = cmd.get("farmId")
            zone_id = cmd.get("zoneId")
            serial_number = cmd.get("serialNumber")
            if not farm_id or not zone_id:
                return self._publish_ack(
                    command_id=command_id,
                    status="FAILED",
                    message="Missing farmId or zoneId in PROVISION_DEVICE command",
                )

            self.farm_id = farm_id
            self.zone_id = zone_id
            self.serial_number = serial_number or "SN-001"
            return self._publish_ack(
                command_id=command_id,
                status="SUCCESS",
                message=f"Node provisioned to {farm_id}/{zone_id}; activation ready",
            )

        else:
            return self._publish_ack(
                command_id=command_id,
                status="ERROR",
                message=f"Unsupported command action: '{action}'",
            )

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        is_ok = (reason_code == 0) or (
            hasattr(reason_code, "is_failure") and not reason_code.is_failure
        )
        if is_ok:
            self.is_connected = True
            logger.info(
                "[SIMULATOR] Connected to MQTT broker at %s:%d as '%s'",
                self.broker_host,
                self.broker_port,
                self.device_id,
            )
            client.subscribe(self.topic_command, qos=1)
            logger.info("[SIMULATOR] Subscribed to %s (QoS 1)", self.topic_command)
            self.publish_online_status()
        else:
            logger.error("[SIMULATOR] MQTT connect failed: %s", reason_code)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None):
        self.is_connected = False
        logger.info("[SIMULATOR] Disconnected from MQTT broker (rc=%s)", reason_code)

    def _on_message(self, client, userdata, message):
        if message.topic == self.topic_command:
            self.handle_command_payload(message.payload)

    def start(self) -> None:
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"sim-{self.device_id}",
            protocol=mqtt.MQTTv311,
        )
        # Configure MQTT LWT offline status (retained=True, QoS=1)
        self.client.will_set(
            topic=self.topic_status,
            payload=json.dumps({"status": "offline"}),
            qos=1,
            retain=True,
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        self.client.connect(self.broker_host, self.broker_port, keepalive=30)
        self.client.loop_start()

    def stop(self, publish_offline: bool = True) -> None:
        if self.client:
            if publish_offline and self.is_connected:
                self.publish_offline_status()
                time.sleep(0.1)
            self.client.loop_stop()
            self.client.disconnect()
            self.is_connected = False


def main() -> None:
    parser = argparse.ArgumentParser(description="SwiftletCare Canonical ESP32 Device Simulator")
    parser.add_argument("--device-id", default="SWC-NODE-001", help="Device code (default: SWC-NODE-001)")
    parser.add_argument("--host", default="127.0.0.1", help="MQTT broker host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port (default: 1883)")
    parser.add_argument("--telemetry-interval", type=float, default=5.0, help="Telemetry interval in seconds")
    parser.add_argument("--heartbeat-interval", type=float, default=15.0, help="Heartbeat interval in seconds")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    sim = ESP32DeviceSimulator(
        device_id=args.device_id,
        broker_host=args.host,
        broker_port=args.port,
    )
    sim.start()

    # Wait briefly for connection handshake
    for _ in range(20):
        if sim.is_connected:
            break
        time.sleep(0.1)

    last_telemetry = 0.0
    last_heartbeat = 0.0

    try:
        while True:
            now = time.monotonic()
            if now - last_heartbeat >= args.heartbeat_interval:
                sim.publish_heartbeat()
                last_heartbeat = now
            if now - last_telemetry >= args.telemetry_interval:
                sim.publish_telemetry(vary=True)
                last_telemetry = now
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[SIMULATOR] Stopping device simulator...")
    finally:
        sim.stop(publish_offline=True)


if __name__ == "__main__":
    main()
