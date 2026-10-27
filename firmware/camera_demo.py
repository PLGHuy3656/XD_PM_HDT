import cv2
import numpy as np
import time
import json
import paho.mqtt.client as mqtt

# ============================================================================
# SWIFTLETCARE - LAPTOP CAMERA AI VISION DEMO
# Features: Real-time Webcam Motion Tracking, Virtual Tripwire In/Out Counting,
#           Predator Intrusion Simulation, and MQTT Telemetry Synchronization.
# ============================================================================

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
NODE_ID = "swc-h01-f01-node01"
TOPIC_CAMERA = f"swiftlet/camera/{NODE_ID}"
TOPIC_ALARM = f"swiftlet/alarm/{NODE_ID}"

# 1. Khởi tạo MQTT Client
mqtt_client = mqtt.Client(client_id=f"laptop_cam_{int(time.time())}")
try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
    print(f"[MQTT] Da ket noi toi {MQTT_BROKER} thanh cong!")
except Exception as e:
    print(f"[MQTT WARN] Khong the ket noi broker: {e}")

# 2. Khởi tạo Webcam Laptop
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("[ERROR] Khong the mo Webcam laptop! Hay kiem tra quyen truy cap camera.")
    exit(1)

# Thiết lập độ phân giải
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

# Khởi tạo thuật toán trừ nền (Background Subtraction) để phát hiện chuyển động
fgbg = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=40, detectShadows=False)

# Biến đếm và vạch ranh giới ảo (Virtual Tripwire)
count_in = 0    # Chim bay vào nhà
count_out = 0   # Chim bay ra kiếm ăn
tracked_objects = {}  # {id: [last_y, last_time]}
next_obj_id = 0

last_mqtt_pub = 0
predator_alert_time = 0

print("\n=======================================================")
print("  SWIFTLETCARE - CAMERA AI VISION DEMO DANG CHAY  ")
print("=======================================================")
print(">> Vach vang giua man hinh la RANH GIOI CUA THU CHIM (Roaming Hole)")
print(">> Di chuyen tay/vat the tu TREN XUONG -> Tang dem VAO (IN)")
print(">> Di chuyen tay/vat the tu DUOI LEN   -> Tang dem RA (OUT)")
print(">> Bam phim [P]: Gia lap phat hien Thu San Moi (Predator Alert)")
print(">> Bam phim [R]: Reset so dem ve 0")
print(">> Bam phim [Q]: Thoat chuong trinh\n")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1) # Lật gương cho tự nhiên
    h, w, _ = frame.shape
    line_y = int(h * 0.5) # Vạch ranh giới ảo chia đôi màn hình

    # 1. Phát hiện chuyển động
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (21, 21), 0)
    fgmask = fgbg.apply(blurred)

    # Khử nhiễu mask
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    fgmask = cv2.morphologyEx(fgmask, cv2.MORPH_OPEN, kernel)
    fgmask = cv2.dilate(fgmask, kernel, iterations=2)

    # Tìm đường viền (contours) của các vật thể chuyển động
    contours, _ = cv2.findContours(fgmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    current_centroids = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 1200: # Lọc bỏ nhiễu hạt nhỏ
            x, y, cw, ch = cv2.boundingRect(cnt)
            cx = x + cw // 2
            cy = y + ch // 2
            current_centroids.append((cx, cy))

            # Vẽ bounding box xanh lá quanh vật thể
            cv2.rectangle(frame, (x, y), (x + cw, y + ch), (0, 255, 0), 2)
            cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
            cv2.putText(frame, "Swiftlet / Motion", (x, y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # 2. Thuật toán đếm qua vạch ảo (Virtual Tripwire Logic)
    for (cx, cy) in current_centroids:
        # Tìm xem centroid này có khớp với object cũ nào không
        matched_id = None
        for oid, data in list(tracked_objects.items()):
            prev_y = data['y']
            if abs(cy - prev_y) < 60: # Cùng 1 vật thể đang di chuyển
                matched_id = oid
                break

        if matched_id is not None:
            prev_y = tracked_objects[matched_id]['y']
            # Kiểm tra vượt qua vạch line_y
            if prev_y < line_y and cy >= line_y:
                count_in += 1
                cv2.line(frame, (0, line_y), (w, line_y), (0, 255, 0), 4) # Nháy xanh khi IN
                print(f"[AI COUNT] Chim bay VAO (IN): {count_in} | Tong so trong nha: {count_in - count_out}")
            elif prev_y > line_y and cy <= line_y:
                count_out += 1
                cv2.line(frame, (0, line_y), (w, line_y), (0, 165, 255), 4) # Nháy cam khi OUT
                print(f"[AI COUNT] Chim bay RA (OUT): {count_out} | Tong so trong nha: {count_in - count_out}")

            tracked_objects[matched_id] = {'y': cy, 'time': time.time()}
        else:
            tracked_objects[next_obj_id] = {'y': cy, 'time': time.time()}
            next_obj_id += 1

    # Dọn dẹp các vật thể không còn xuất hiện sau 0.8 giây
    now = time.time()
    tracked_objects = {oid: d for oid, d in tracked_objects.items() if now - d['time'] < 0.8}

    # 3. Gửi Telemetry đếm chim lên Cloud MQTT mỗi 3 giây
    if now - last_mqtt_pub >= 3.0:
        last_mqtt_pub = now
        total_inside = max(0, count_in - count_out)
        payload = {
            "nodeId": NODE_ID,
            "timestamp": int(now),
            "camera": {
                "status": "ONLINE",
                "birdsIn": count_in,
                "birdsOut": count_out,
                "totalInside": total_inside,
                "predatorDetected": (now - predator_alert_time < 5.0)
            }
        }
        try:
            mqtt_client.publish(TOPIC_CAMERA, json.dumps(payload))
        except:
            pass

    # 4. Vẽ giao diện HUD chuyên nghiệp lên màn hình Camera
    # Vạch ranh giới ảo
    cv2.line(frame, (0, line_y), (w, line_y), (0, 255, 255), 2)
    cv2.putText(frame, "--- ROAMING HOLE COUNTING LINE ---", (120, line_y - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

    # Thanh Header thông số
    cv2.rectangle(frame, (0, 0), (w, 55), (20, 20, 20), -1)
    cv2.putText(frame, "SWIFTLETCARE - CAMERA AI VISION NODE", (15, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    total_inside = max(0, count_in - count_out)
    stats_text = f"VAO (IN): {count_in}   |   RA (OUT): {count_out}   |   TRONG NHA: {total_inside}"
    cv2.putText(frame, stats_text, (15, 45),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (50, 220, 255), 2)

    # Hiển thị cảnh báo nếu vừa bấm [P] (Thú săn mồi)
    if now - predator_alert_time < 5.0:
        cv2.rectangle(frame, (0, h - 50), (w, h), (0, 0, 220), -1)
        cv2.putText(frame, "CANH BAO NGUY HIEM: PHAT HIEN THU SAN MOI (PREDATOR)!",
                    (20, h - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    cv2.imshow("SwiftletCare - Laptop Camera AI Demo", frame)

    # 5. Phím bấm điều khiển
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('r'):
        count_in = 0
        count_out = 0
        print("[AI RESET] Da reset bo dem ve 0.")
    elif key == ord('p'):
        predator_alert_time = time.time()
        print("\n[ALERT] PHAT HIEN THU SAN MOI! Dang ban canh bao MQTT...")
        alert_payload = {
            "nodeId": NODE_ID,
            "alertType": "PREDATOR_INTRUSION",
            "message": "Phat hien dong vat san moi tai cua thu chim!",
            "timestamp": int(time.time())
        }
        mqtt_client.publish(TOPIC_ALARM, json.dumps(alert_payload))

cap.release()
cv2.destroyAllWindows()
mqtt_client.loop_stop()
print("[CAMERA] Da dong camera va ngat ket noi.")
