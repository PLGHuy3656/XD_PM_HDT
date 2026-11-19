import time
import json
import os
import sys
import threading
from datetime import datetime
import paho.mqtt.client as mqtt

# ============================================================================
# SWIFTLETCARE - EDGE SERVICE MONITOR & SUPERVISORY SYSTEM
# Chức năng: 
# 1. Dịch vụ giám sát trung tâm toàn bộ luồng IoT (ESP32, Camera, Loa ru)
# 2. Phân tích vi khí hậu & Thực thi Điều phối Vòng kín (Closed-Loop Automation)
# 3. Kích hoạt còi báo động khi Camera báo Thú săn mồi hoặc Loa bị đứt dây
# 4. Ghi nhật ký sự kiện hệ thống (Audit Log)
# ============================================================================

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
NODE_ID = "swc-h01-f01-node01"

TOPIC_SUB_ALL    = "swiftlet/#"
TOPIC_COMMAND    = f"swiftlet/command/{NODE_ID}"
TOPIC_TELEMETRY  = f"swiftlet/telemetry/{NODE_ID}"
TOPIC_HEARTBEAT  = f"swiftlet/heartbeat/{NODE_ID}"
TOPIC_CAMERA     = f"swiftlet/camera/{NODE_ID}"
TOPIC_ALARM      = f"swiftlet/alarm/{NODE_ID}"
TOPIC_STATUS     = f"swiftlet/status/{NODE_ID}"
TOPIC_ACK        = f"swiftlet/ack/{NODE_ID}"

LOG_FILE = "monitor_events.log"

# Trạng thái toàn cục của các nút thiết bị
system_state = {
    "esp32_status": "CHƯA KẾT NỐI",
    "last_telemetry": None,
    "last_heartbeat": None,
    "temp": 0.0,
    "hum": 0.0,
    "co2": 0,
    "lux": 0.0,
    "relays": {"misting": False, "fan": False, "heater": False, "alarm": False},
    "mode": "UNKNOWN",
    "wifi_rssi": 0,
    "uptime": 0,
    "camera": {"birds_in": 0, "birds_out": 0, "total": 0, "status": "OFFLINE"},
    "audio": {"status": "ONLINE", "healthy": True, "decibel": 68.0},
    "recent_events": [],
    "closed_loop_enabled": True
}

state_lock = threading.Lock()

def log_event(level, source, message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    event_str = f"[{timestamp}] [{level.upper()}] [{source}] {message}"
    with state_lock:
        system_state["recent_events"].append(event_str)
        if len(system_state["recent_events"]) > 8:
            system_state["recent_events"].pop(0)
    
    # Ghi file log
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{level.upper()}] [{source}] {message}\n")
    except:
        pass

def send_mqtt_command(target, state, reason="Service Manual"):
    cmd_id = f"srv-{int(time.time()*1000)%100000}"
    payload = {
        "commandId": cmd_id,
        "action": "SET_RELAY",
        "target": target,
        "state": 1 if state else 0,
        "reason": reason
    }
    mqtt_client.publish(TOPIC_COMMAND, json.dumps(payload))
    log_event("CMD", "SERVICE", f"Bắn lệnh {target} -> {'ON' if state else 'OFF'} ({reason})")

def handle_closed_loop_logic(temp, hum):
    """Quy tắc điều phối tự động vòng kín của Backend Service"""
    if not system_state["closed_loop_enabled"]:
        return

    # Nếu nhiệt độ vượt ngưỡng an toàn (> 32°C) mà Quạt chưa bật -> Service can thiệp bật Quạt
    if temp > 32.0 and not system_state["relays"]["fan"]:
        log_event("WARN", "CLOSED-LOOP", f"Nhiệt độ cao ({temp:.1f}°C > 32°C)! Tự động bật QUẠT LÀM MÁT")
        send_mqtt_command("fan", True, "Auto Cool-down")

    # Nếu độ ẩm quá khô (< 72%) mà Phun sương chưa bật -> Bật Phun sương
    if hum < 72.0 and not system_state["relays"]["misting"]:
        log_event("WARN", "CLOSED-LOOP", f"Độ ẩm thấp ({hum:.1f}% < 72%)! Tự động bật PHUN SƯƠNG BÙ ẨM")
        send_mqtt_command("misting", True, "Auto Humidify")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        log_event("INFO", "MQTT", f"Ket noi Cloud Broker thanh cong ({MQTT_BROKER}:1883)")
        client.subscribe(TOPIC_SUB_ALL)
        log_event("INFO", "MQTT", "Da dang ky (Subscribe) toan bo luong: swiftlet/#")
    else:
        log_event("ERROR", "MQTT", f"Ket noi that bai voi ma loi: {rc}")

def on_message(client, userdata, msg):
    topic = msg.topic
    try:
        data = json.loads(msg.payload.decode('utf-8'))
    except Exception:
        return

    with state_lock:
        if topic == TOPIC_TELEMETRY:
            system_state["esp32_status"] = "ONLINE"
            system_state["last_telemetry"] = time.time()
            m = data.get("metrics", {})
            system_state["temp"] = m.get("temp", 0.0)
            system_state["hum"] = m.get("humidity", 0.0)
            system_state["co2"] = m.get("co2", 0)
            system_state["lux"] = m.get("lux", 0.0)
            
            act = data.get("actuators", {})
            system_state["relays"]["misting"] = act.get("misting", False)
            system_state["relays"]["fan"] = act.get("fan", False)
            system_state["relays"]["heater"] = act.get("heater", False)
            system_state["relays"]["alarm"] = act.get("alarm", False)

            st = data.get("state", {})
            system_state["mode"] = st.get("mode", "AUTO")
            system_state["wifi_rssi"] = st.get("wifiRssi", 0)

            # Phân tích điều phối
            handle_closed_loop_logic(system_state["temp"], system_state["hum"])

        elif topic == TOPIC_HEARTBEAT:
            system_state["esp32_status"] = "ONLINE"
            system_state["last_heartbeat"] = time.time()
            system_state["uptime"] = data.get("uptime", 0)

        elif topic == TOPIC_CAMERA:
            cam = data.get("camera", {})
            system_state["camera"]["birds_in"] = cam.get("birdsIn", 0)
            system_state["camera"]["birds_out"] = cam.get("birdsOut", 0)
            system_state["camera"]["total"] = cam.get("totalInside", 0)
            system_state["camera"]["status"] = "ONLINE"
            log_event("DATA", "CAMERA", f"Vào: {cam.get('birdsIn')} | Ra: {cam.get('birdsOut')} | Tổng đàn: {cam.get('totalInside')}")

        elif topic == TOPIC_ALARM:
            alert_type = data.get("alertType", "GENERAL_ALARM")
            msg_text = data.get("message", "")
            log_event("ALARM", "SECURITY", f"🚨 [{alert_type}] {msg_text}")
            
            # Nếu phát hiện Thú săn mồi từ Camera -> Service lập tức bật Còi báo động trên ESP32!
            if alert_type == "PREDATOR_INTRUSION":
                log_event("ACTION", "SERVICE", "Phat hien Thu San Moi -> Kich hoat COI BAO DONG tren ESP32!")
                send_mqtt_command("alarm", True, "Predator Intercept")

        elif topic == TOPIC_ACK:
            log_event("ACK", "ESP32", f"Lenh [{data.get('commandId')}]: {data.get('status')} - Mode: {data.get('mode')}")

        elif topic == TOPIC_STATUS:
            st = data.get("status", "unknown")
            system_state["esp32_status"] = "ONLINE" if st == "online" else "OFFLINE"
            log_event("STATUS", "ESP32", f"Node Node status: {st.upper()}")

def render_dashboard():
    """Vẽ giao diện bảng điều khiển Monitor trực quan trong Terminal"""
    os.system('cls' if os.name == 'nt' else 'clear')
    with state_lock:
        print("=" * 76)
        print("      SWIFTLETCARE - DỊCH VỤ GIÁM SÁT & ĐIỀU PHỐI TRUNG TÂM (SERVICE MONITOR)      ")
        print("                 Giao thức: MQTT Broker (broker.emqx.io:1883)              ")
        print("=" * 76)

        # Trạng thái Nút IoT
        esp_st = system_state["esp32_status"]
        esp_color = "ONLINE (Kết nối tốt)" if esp_st == "ONLINE" else "OFFLINE / CHỜ TÍN HIỆU"
        cam_st = system_state["camera"]["status"]
        auto_cl = "BẬT (Active)" if system_state["closed_loop_enabled"] else "TẮT (Manual Only)"

        print(f" [NÚT CẢM BIẾN ESP32] : {esp_color:<22} | WiFi RSSI: {system_state['wifi_rssi']} dBm | Uptime: {system_state['uptime']}s")
        print(f" [CAMERA LỖ THU CHIM] : {cam_st:<22} | ĐIỀU PHỐI VÒNG KÍN: {auto_cl}")
        print("-" * 76)

        # Vi khí hậu đo được từ ESP32
        t = system_state["temp"]
        h = system_state["hum"]
        co2 = system_state["co2"]
        lux = system_state["lux"]

        # Cảnh báo vi khí hậu
        t_note = "Bình thường" if 27.0 <= t <= 31.5 else ("CẢNH BÁO NÓNG!" if t > 31.5 else "LẠNH!")
        h_note = "Tối ưu" if 75.0 <= h <= 90.0 else ("ẨM THẤP (KHÔ)!" if h < 75.0 else "QUÁ ẨM!")

        print(f" 🌡️  Nhiệt độ : {t:5.1f} °C   [{t_note:<14}] | 💧 Độ ẩm  : {h:5.1f} %   [{h_note:<14}]")
        print(f" 🌱 Khí CO2  : {co2:5} ppm  [An toàn < 700ppm] | ☀️ Ánh sáng: {lux:5.2f} Lux [Phòng tối < 0.2]")
        print("-" * 76)

        # Trạng thái Rơ-le (Actuators)
        rel = system_state["relays"]
        fmt_m = "[ BẬT ]" if rel["misting"] else "[ TẮT ]"
        fmt_f = "[ BẬT ]" if rel["fan"] else "[ TẮT ]"
        fmt_h = "[ BẬT ]" if rel["heater"] else "[ TẮT ]"
        fmt_a = "[ BẬT ]" if rel["alarm"] else "[ TẮT ]"

        print(f" TRẠNG THÁI RƠ-LE : Phun sương: {fmt_m}  |  Quạt gió: {fmt_f}  |  Sưởi: {fmt_h}  |  Còi: {fmt_a}")
        print(f" CHẾ ĐỘ HOẠT ĐỘNG: {system_state['mode']}")
        print("-" * 76)

        # Thống kê đàn chim
        cam = system_state["camera"]
        print(f" 🕊️  THỐNG KÊ ĐÀN CHIM YẾN (NĐ 13/2020): Vào: {cam['birds_in']}  |  Ra: {cam['birds_out']}  |  Đang ở trong nhà: {cam['total']} con")
        print("=" * 76)

        # Nhật ký sự kiện thời gian thực
        print(" 📜 NHẬT KÝ SỰ KIỆN GIAO TIẾP IOT MỚI NHẤT:")
        if not system_state["recent_events"]:
            print("   (Đang lắng nghe các gói tin MQTT từ mạng lưới IoT...)")
        else:
            for ev in system_state["recent_events"]:
                print(f"   {ev}")
        print("-" * 76)

        # Hướng dẫn tương tác
        print(" PHÍM TƯƠNG TÁC: [1] Bật/Tắt Quạt | [2] Bật/Tắt Sương | [3] Test Còi | [4] Bật/Tắt Auto")
        print("                 [C] Xóa màn hình | [Q] Thoát")
        print("=" * 76)

def monitor_ui_loop():
    while running:
        render_dashboard()
        time.sleep(1.5)

# Khởi tạo MQTT Client
mqtt_client = mqtt.Client(client_id=f"service_monitor_{int(time.time())}")
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
except Exception as e:
    print(f"[ERROR] Không thể kết nối MQTT: {e}")
    sys.exit(1)

running = True
ui_thread = threading.Thread(target=monitor_ui_loop, daemon=True)
ui_thread.start()

# Vòng lặp nhận lệnh bàn phím tương tác
try:
    while running:
        cmd = input().strip().lower()
        if cmd == 'q':
            running = False
            break
        elif cmd == '1':
            new_state = not system_state["relays"]["fan"]
            send_mqtt_command("fan", new_state, "Manual Monitor Trigger")
        elif cmd == '2':
            new_state = not system_state["relays"]["misting"]
            send_mqtt_command("misting", new_state, "Manual Monitor Trigger")
        elif cmd == '3':
            new_state = not system_state["relays"]["alarm"]
            send_mqtt_command("alarm", new_state, "Manual Alarm Test")
        elif cmd == '4':
            system_state["closed_loop_enabled"] = not system_state["closed_loop_enabled"]
            st_text = "BAT" if system_state["closed_loop_enabled"] else "TAT"
            log_event("CONFIG", "SERVICE", f"Dieu phoi tu dong vong kin: {st_text}")
        elif cmd == 'c':
            render_dashboard()
except (KeyboardInterrupt, EOFError):
    running = False

mqtt_client.loop_stop()
mqtt_client.disconnect()
print("\n[INFO] Đã đóng Dịch vụ Giám sát SwiftletCare.")
