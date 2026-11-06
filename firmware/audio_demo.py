import time
import json
import threading
import winsound
import paho.mqtt.client as mqtt

# ============================================================================
# SWIFTLETCARE - LAPTOP AUDIO / SPEAKER MONITORING DEMO
# Features: Simulates Swiftlet Attractant Audio Playback (2.5kHz - 4.5kHz),
#           Speaker Fault Detection, and MQTT Failure Alert Dispatching.
# ============================================================================

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
NODE_ID = "swc-h01-f01-node01"
TOPIC_TELEMETRY = f"swiftlet/telemetry/{NODE_ID}"
TOPIC_ALARM = f"swiftlet/alarm/{NODE_ID}"

# Khởi tạo MQTT Client
mqtt_client = mqtt.Client(client_id=f"laptop_audio_{int(time.time())}")
try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
    print(f"[MQTT] Da ket noi toi {MQTT_BROKER} thanh cong!")
except Exception as e:
    print(f"[MQTT WARN] Khong the ket noi broker: {e}")

# Biến trạng thái
is_playing = True
is_running = True
last_sound_time = time.time()

# Danh sách tần số mô phỏng tiếng chim yến (2500Hz - 4200Hz)
CHIRP_FREQUENCIES = [2800, 3200, 3600, 4000, 3400, 2900]

def audio_playback_worker():
    """Luồng phát âm thanh tiếng chim yến qua loa laptop"""
    global last_sound_time, is_playing, is_running
    idx = 0
    while is_running:
        if is_playing:
            freq = CHIRP_FREQUENCIES[idx % len(CHIRP_FREQUENCIES)]
            idx += 1
            try:
                # Phát tiếng chíp chíp ngắn qua loa laptop
                winsound.Beep(freq, 120)
                last_sound_time = time.time()
            except Exception:
                pass
            time.sleep(0.4)
        else:
            time.sleep(0.5)

# Bắt đầu luồng phát âm thanh ngầm
audio_thread = threading.Thread(target=audio_playback_worker, daemon=True)
audio_thread.start()

print("\n=======================================================")
print("  SWIFTLETCARE - HE THONG LOA RU & GIAM SAT AM THANH   ")
print("=======================================================")
print(">> Loa laptop dang phat am thanh mo phong tieng chim yen (2.8kHz - 4kHz)")
print(">> Bam phim [M] + ENTER: Gia lap SU CO DUT DAY LOA / MAT TIENG")
print(">> Bam phim [R] + ENTER: KHOI PHUC loa hoat dong tro lai")
print(">> Bam phim [Q] + ENTER: Thoat chuong trinh\n")

last_status_pub = 0
alert_sent = False

def monitor_loop():
    global is_playing, is_running, alert_sent, last_status_pub
    while is_running:
        now = time.time()
        time_since_last_sound = now - last_sound_time

        # Kiểm tra xem loa có bị ngắt tiếng quá 2.5 giây không
        if time_since_last_sound > 2.5:
            if not alert_sent:
                alert_sent = True
                print("\n" + "!" * 65)
                print(" [CANH BAO NGUY HIEM] LOA RU NHA YEN DA BI MAT TIENG / CHAY AMPLI!")
                print(" -> Dang gui ban tin bao dong MQTT khan cap toi chu nha yen...")
                print("!" * 65)

                alarm_payload = {
                    "nodeId": NODE_ID,
                    "alertType": "AUDIO_SPEAKER_FAILURE",
                    "message": "Mat tin hieu am thanh loa ru! Nguy co chim bo to!",
                    "timestamp": int(now)
                }
                mqtt_client.publish(TOPIC_ALARM, json.dumps(alarm_payload))

                # Phát còi báo động lỗi
                try:
                    winsound.Beep(1000, 600)
                except:
                    pass
        else:
            if alert_sent:
                alert_sent = False
                print("\n[OK] He thong am thanh da phuc hoi hoat dong binh thuong.")

        # Định kỳ gửi trạng thái loa mỗi 4 giây
        if now - last_status_pub >= 4.0:
            last_status_pub = now
            status_payload = {
                "nodeId": NODE_ID,
                "timestamp": int(now),
                "audio": {
                    "healthy": not alert_sent,
                    "soundDetected": is_playing,
                    "decibelLevel": 68 if is_playing else 25
                }
            }
            mqtt_client.publish(TOPIC_TELEMETRY, json.dumps(status_payload))

        time.sleep(0.5)

# Bắt đầu luồng giám sát ngầm
monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
monitor_thread.start()

# Vòng lặp nhận phím từ người dùng
while True:
    cmd = input("").strip().lower()
    if cmd == 'm':
        is_playing = False
        print("[LENH] >> Da tat tieng loa (Gia lap dut day loa ru / hong ampli).")
    elif cmd == 'r':
        is_playing = True
        last_sound_time = time.time()
        print("[LENH] >> Da bat lai loa ru thanh cong.")
    elif cmd == 'q':
        is_running = False
        break

mqtt_client.loop_stop()
print("[AUDIO] Da dung he thong am thanh.")
