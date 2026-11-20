#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SWIFTLETCARE - ESP32 VIRTUAL EDGE NODE SIMULATOR
================================================
Giả lập phần cứng ESP32 thật 100% kết nối vào hệ sinh thái SwiftletCare:
1. Kết nối vào MQTT Broker Mosquitto (port 1883 cục bộ hoặc Cloud EMQX).
2. Tự động gửi Telemetry vi khí hậu (Nhiệt độ, Độ ẩm, CO2, Ánh sáng, Âm thanh loa ru).
3. Lắng nghe và thực thi lệnh điều khiển Rơ-le (Bật/Tắt máy phun sương, quạt, sưởi, còi báo).
4. Phản hồi ACK xác nhận lệnh về cho Web Frontend / Gateway.
5. Gửi bản tin Heartbeat định kỳ kiểm tra sức khỏe thiết bị.

Giúp bất kỳ ai clone project về có thể chạy thử NGAY LẬP TỨC mà không cần mua phần cứng!
"""

import sys
import time
import json
import random
import os
import threading
from datetime import datetime, timezone

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("[ERROR] Thư viện 'paho-mqtt' chưa được cài đặt.")
    print("Vui lòng chạy: pip install paho-mqtt")
    sys.exit(1)

# Cấu hình thiết bị & Broker (qua biến môi trường, không hardcode secrets)
MQTT_BROKER   = os.getenv("MQTT_BROKER_HOST", "127.0.0.1")
MQTT_PORT     = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
DEVICE_ID     = os.getenv("DEVICE_ID", "SWC-DEMO-NODE-001")

TOPIC_TELEMETRY = f"swiftlet/telemetry/{DEVICE_ID}"
TOPIC_HEARTBEAT = f"swiftlet/heartbeat/{DEVICE_ID}"
TOPIC_COMMAND   = f"swiftlet/command/{DEVICE_ID}"
TOPIC_ACK       = f"swiftlet/ack/{DEVICE_ID}"
TOPIC_STATUS    = f"swiftlet/status/{DEVICE_ID}"

# Trạng thái thiết bị giả lập
state = {
    "temperature": 28.5,
    "humidity": 82.0,
    "lux": 0.5,
    "co2": 460.0,
    "audioRms": 0.42,
    "audioHealthy": True,
    "misting": False,
    "fan": False,
    "heater": False,
    "alarm": False,
    "mode": "AUTO",
    "targetTemp": 28.5,
    "targetHum": 80.0,
}

start_time = time.time()

# INT01-R1: idempotency - remember recently executed commandIds and their ACK so a
# redelivered (QoS1 duplicate) command is never executed twice.
RECENT_COMMANDS = {}
RECENT_COMMANDS_MAX = 200

# INT01-R1: opt-in fault injection for deterministic negative-path tests (default: none).
# Format: "misting=FAILED,heater=ERROR,fan=NOACK,alarm=DELAY:20"
#   FAILED / ERROR -> do not actuate, reply ACK with that status
#   NOACK          -> actuate nothing and send no ACK (server must reach TIMEOUT)
#   DELAY:<s>      -> actuate, then ACK SUCCESS after <s> seconds (late-ACK test)
SIM_FAULT_MODE = os.getenv("SIM_FAULT_MODE", "").strip()


def _parse_fault_mode(raw):
    faults = {}
    for item in [p.strip() for p in raw.split(",") if p.strip()]:
        if "=" not in item:
            continue
        target, mode = [x.strip() for x in item.split("=", 1)]
        faults[target] = mode.upper()
    return faults


FAULTS = _parse_fault_mode(SIM_FAULT_MODE)

# INT01-R1: every value produced here is simulated. Declared explicitly so the platform
# never presents it as a physical sensor reading (see IoT TelemetryProvenance).
SIM_PROVENANCE = {
    "source": "SIMULATED",
    "sensors": {
        "temperature": "SIMULATED",
        "humidity": "SIMULATED",
        "co2": "SIMULATED",
        "lux": "SIMULATED",
        "audio": "SIMULATED",
        "networkRssi": "SIMULATED",
    },
}


def _parse_iso_utc(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"\n[OK] ESP32 ({DEVICE_ID}) da ket noi Broker thanh cong: {MQTT_BROKER}:{MQTT_PORT}")
        # Chỉ đăng ký đúng topic lệnh của thiết bị này (không subscribe chéo node khác)
        client.subscribe(TOPIC_COMMAND, qos=1)
        print(f"[SUB] Da lang nghe kenh lenh: {TOPIC_COMMAND}")
        # Thông báo online
        client.publish(TOPIC_STATUS, json.dumps({"status": "online"}), qos=1, retain=True)
    else:
        print(f"[FAIL] Ket noi MQTT that bai! Ma loi: {rc}")


def _publish_ack(client, cmd_id: str, status_val: str, message: str):
    if cmd_id in RECENT_COMMANDS:
        RECENT_COMMANDS[cmd_id] = (status_val, message)
    ack_payload = {
        "commandId": cmd_id,
        "deviceId": DEVICE_ID,
        "status": status_val,
        "mode": state["mode"],
        "message": message,
    }
    client.publish(TOPIC_ACK, json.dumps(ack_payload), qos=1)
    print(f" -> [ACK] Da gui xac nhan {status_val} ve {TOPIC_ACK}")


def on_message(client, userdata, msg):
    global state
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        print(f"\n=======================================================")
        print(f" [LENH NHAN TU WEB/GATEWAY] Topic: {msg.topic}")
        print(f" Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        print(f"=======================================================")

        cmd_id = payload.get("commandId", "00000000-0000-0000-0000-000000000000")
        action = payload.get("action")

        # INT01-R1: duplicate delivery -> re-send the original ACK, never execute twice
        if cmd_id in RECENT_COMMANDS:
            prev = RECENT_COMMANDS[cmd_id]
            print(f" -> [DUPLICATE] commandId {cmd_id} da xu ly; khong thuc thi lai")
            if prev is not None:
                _publish_ack(client, cmd_id, prev[0], prev[1])
            return
        RECENT_COMMANDS[cmd_id] = None
        if len(RECENT_COMMANDS) > RECENT_COMMANDS_MAX:
            RECENT_COMMANDS.pop(next(iter(RECENT_COMMANDS)))

        # INT01-R1: fail-safe expiry - never execute a command past the server deadline
        expires_at = _parse_iso_utc(payload.get("expiresAt")) if payload.get("expiresAt") else None
        if expires_at is not None and datetime.now(timezone.utc) > expires_at:
            print(f" -> [EXPIRED] Lenh {cmd_id} da het han ({payload.get('expiresAt')}); KHONG thuc thi")
            _publish_ack(client, cmd_id, "FAILED", "COMMAND_EXPIRED: deadline passed before execution")
            return

        if action == "SET_RELAY":
            target = payload.get("target")
            relay_state = bool(payload.get("state", 0))
            fault = FAULTS.get(target, "")

            if target in ["misting", "fan", "heater", "alarm"] and fault in ("FAILED", "ERROR"):
                print(f" -> [FAULT INJECTION] {target}: {fault}")
                _publish_ack(client, cmd_id, fault, f"SIM_FAULT_INJECTION: {target} relay {fault}")
            elif target in ["misting", "fan", "heater", "alarm"] and fault == "NOACK":
                print(f" -> [FAULT INJECTION] {target}: NOACK (khong thuc thi, khong gui ACK)")
            elif target in ["misting", "fan", "heater", "alarm"] and fault.startswith("DELAY:"):
                delay_s = float(fault.split(":", 1)[1] or 0)
                state[target] = relay_state
                state["mode"] = "MANUAL"
                print(f" -> [FAULT INJECTION] {target}: ACK SUCCESS tre {delay_s}s")
                threading.Timer(delay_s, _publish_ack, args=(client, cmd_id, "SUCCESS", f"Actuator {target} switched to {relay_state} (late ACK)")).start()
            elif target in ["misting", "fan", "heater", "alarm"]:
                state[target] = relay_state
                state["mode"] = "MANUAL"
                action_str = "BAT" if relay_state else "TAT"
                print(f" -> [THUC THI] Da {action_str} thiet bi: {target.upper()}")
                _publish_ack(
                    client,
                    cmd_id,
                    "SUCCESS",
                    f"Actuator {target} switched to {relay_state}; mode changed to MANUAL",
                )
            else:
                _publish_ack(client, cmd_id, "FAILED", f"Unsupported relay target: {target}")

        elif action == "UPDATE_THRESHOLDS":
            state["targetTemp"] = float(payload.get("targetTemp", 28.5))
            state["targetHum"] = float(payload.get("targetHum", 80.0))
            state["mode"] = "AUTO" if payload.get("isAutoMode", True) else "MANUAL"
            print(f" -> [THUC THI] Cap nhat nguong: TargetTemp={state['targetTemp']}C, TargetHum={state['targetHum']}%")
            _publish_ack(client, cmd_id, "SUCCESS", "Thresholds updated successfully")

        elif action == "PROVISION_DEVICE":
            farm_id = payload.get("farmId")
            zone_id = payload.get("zoneId")
            if not farm_id or not zone_id:
                _publish_ack(client, cmd_id, "FAILED", "Missing farmId or zoneId in PROVISION_DEVICE command")
            else:
                state["farmId"] = farm_id
                state["zoneId"] = zone_id
                _publish_ack(client, cmd_id, "SUCCESS", "Device provisioned in simulator; activation ready")

        else:
            _publish_ack(client, cmd_id, "FAILED", f"Unsupported command action: {action}")

    except Exception as e:
        print(f"[ERROR] Loi xu ly lenh MQTT: {e}")

def main():
    print("==================================================================")
    print("    SWIFTLETCARE - ESP32 VIRTUAL HARDWARE SIMULATOR (TV1)        ")
    print("==================================================================")
    print(f" [i] Thiet bi: {DEVICE_ID} (Nha yen Demo 01 - Tang 1)")
    print(f" [i] Broker:   {MQTT_BROKER}:{MQTT_PORT}")
    print(f" [i] Topic:    {TOPIC_TELEMETRY}")
    print(" Dang ket noi toi Mosquitto Broker...")

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"esp32_sim_{int(time.time())}")
    except AttributeError:
        client = mqtt.Client(client_id=f"esp32_sim_{int(time.time())}")

    client.on_connect = on_connect
    client.on_message = on_message
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD or None)

    # Thiet lap LWT (Last Will and Testament)
    client.will_set(TOPIC_STATUS, json.dumps({"status": "offline"}), qos=1, retain=True)

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        print(f"\n[!] Khong the ket noi broker tai {MQTT_BROKER}:{MQTT_PORT}")
        print(f"    Chi tiet: {e}")
        print("    Hay dam bao Docker stack dang chay (docker compose up -d)")
        return

    client.loop_start()

    last_heartbeat = 0

    try:
        step = 0
        while True:
            step += 1
            now = time.time()

            # Mo phong vi khi hau bien thien tu nhien quanh moc tieu chuan
            # Nhiet do: 28.0 - 29.2 °C
            state["temperature"] = round(28.5 + 0.6 * random.uniform(-1, 1), 2)
            # Do am: 79 - 86 %
            state["humidity"] = round(82.0 + 3.0 * random.uniform(-1, 1), 2)
            # CO2: 430 - 490 ppm
            state["co2"] = float(round(460 + 25 * random.uniform(-1, 1)))
            # Anh sang: 0.2 - 0.7 lux
            state["lux"] = round(0.45 + 0.2 * random.uniform(-1, 1), 2)
            # Am thanh: 0.35 - 0.55
            state["audioRms"] = round(0.42 + 0.08 * random.uniform(-1, 1), 2)

            # Rule tu dong don gian neu o che do AUTO
            if state["mode"] == "AUTO":
                state["misting"] = state["humidity"] < 80.0
                state["fan"] = state["temperature"] > 28.9 or state["co2"] > 500

            telemetry_payload = {
                "deviceId": DEVICE_ID,
                "metrics": {
                    "temperature": state["temperature"],
                    "humidity": state["humidity"],
                    "lux": state["lux"],
                    "co2": state["co2"],
                    "audioRms": state["audioRms"],
                    "audioHealthy": state["audioHealthy"]
                },
                "actuators": {
                    "misting": state["misting"],
                    "fan": state["fan"],
                    "heater": state["heater"],
                    "alarm": state["alarm"]
                },
                "state": {
                    "mode": state["mode"],
                    "networkRssi": -62,  # SIMULATED constant (declared in provenance), not a radio measurement
                    "freeHeap": 221440
                },
                "provenance": SIM_PROVENANCE,
            }

            msg_str = json.dumps(telemetry_payload)
            client.publish(TOPIC_TELEMETRY, msg_str, qos=1)

            relay_info = f"Misting={'ON' if state['misting'] else 'OFF'}, Fan={'ON' if state['fan'] else 'OFF'}"
            print(f"[{datetime.now().strftime('%H:%M:%S')}] TELEMETRY -> {TOPIC_TELEMETRY} | "
                  f"Temp: {state['temperature']}°C | Hum: {state['humidity']}% | CO2: {int(state['co2'])} ppm | Relays: [{relay_info}]")

            # Gui Heartbeat moi 30 giay
            if now - last_heartbeat >= 30:
                last_heartbeat = now
                hb_payload = {
                    "deviceId": DEVICE_ID,
                    "uptime": int(now - start_time),
                    "ip": "192.168.1.105",
                    "freeHeap": 221440,
                    "mockMode": True
                }
                client.publish(TOPIC_HEARTBEAT, json.dumps(hb_payload), qos=1)
                print(f" -> [HEARTBEAT] Da gui Heartbeat cho {DEVICE_ID}")

            time.sleep(3)

    except KeyboardInterrupt:
        print("\n[STOP] Da dung chuong trinh mo phong ESP32.")
    finally:
        client.publish(TOPIC_STATUS, json.dumps({"status": "offline"}), qos=1, retain=True)
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
