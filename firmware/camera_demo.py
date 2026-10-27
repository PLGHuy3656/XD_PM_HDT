import cv2
import numpy as np
import time
import json
import paho.mqtt.client as mqtt
from ultralytics import YOLO

# ============================================================================
# SWIFTLETCARE - CAMERA AI VISION (YOLOv8 POWERED DEEP LEARNING)
# Standard: Nghị định 13/2020/NĐ-CP - Quy chuẩn kỹ thuật nhà yến & an toàn sinh học
# Engine: YOLOv8 Deep Learning + Dual-Line Virtual Gate Centroid Tracker
# ============================================================================

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
NODE_ID = "swc-h01-f01-node01"
TOPIC_CAMERA = f"swiftlet/camera/{NODE_ID}"
TOPIC_ALARM = f"swiftlet/alarm/{NODE_ID}"

# 1. Khởi tạo kết nối MQTT
mqtt_client = mqtt.Client(client_id=f"laptop_cam_ai_{int(time.time())}")
try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
    print(f"[MQTT] Da ket noi Cloud Broker: {MQTT_BROKER}")
except Exception as e:
    print(f"[MQTT WARN] Khong the ket noi broker: {e}")

# 2. Khởi tạo mô hình AI YOLOv8
print("[AI] Dang tai mo hinh YOLOv8 Vision Engine...")
model = YOLO("yolov8n.pt")
print("[AI] Mo hinh YOLOv8 da san sang!")

# COCO Class IDs
CLASS_BIRD = 14
CLASS_CAT = 15
CLASS_DOG = 16
PREDATOR_CLASSES = [CLASS_CAT, CLASS_DOG]

# 3. Khởi tạo Webcam Laptop
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("[ERROR] Khong the mo Webcam! Hay kiem tra camera.")
    exit(1)

FRAME_W = 640
FRAME_H = 480
cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)

# THIẾT LẬP CỔNG ĐẾM 2 VẠCH (DUAL-LINE GATE) THEO NGHỊ ĐỊNH 13/2020/NĐ-CP
GATE_Y1 = int(FRAME_H * 0.40)  # Vạch 1: Vạch vào (Entry Line)
GATE_Y2 = int(FRAME_H * 0.60)  # Vạch 2: Vạch ra (Exit Line)

class TrackedBird:
    def __init__(self, obj_id, centroid, label="bird"):
        self.id = obj_id
        self.centroids = [centroid]
        self.counted = False
        self.label = label
        self.last_seen = time.time()

tracked_objects = {}
next_id = 1

count_in = 0
count_out = 0
predator_alert_time = 0
last_mqtt_pub = 0
ai_mode_strict = True  # True: Chỉ đếm chim (Bird); False: Đếm linh hoạt mọi vật mẫu demo

print("\n" + "=" * 70)
print("  SWIFTLETCARE - HE THONG CAMERA AI YOLOv8 THEO DOI CUA THU CHIM YEN  ")
print("  (Dat chuan ky thuat & an toan sinh hoc Nghi dinh 13/2020/ND-CP)     ")
print("=" * 70)
print(">> CONG DEM 2 VACH: Vat the phai di qua 2 vach ao moi duoc xac nhan")
print(">> Tren xuong (Vach 1 -> Vach 2): Chim bay VAO (+1 IN)")
print(">> Duoi len   (Vach 2 -> Vach 1): Chim bay RA  (+1 OUT)")
print(">> [M]: Chuyen che do AI (Strict: Chi chim | Demo: Linh hoat moi vat)")
print(">> [P]: Kich hoat Canh bao Thu San Moi (Predator Alert)")
print(">> [R]: Reset bo dem ve 0")
print(">> [Q]: Thoat chuong trinh\n")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)  # Lật gương tự nhiên
    now = time.time()

    # Nhận diện đối tượng bằng YOLOv8 AI (imgsz=320 để đạt FPS cao 25-30fps trên CPU)
    results = model(frame, imgsz=320, conf=0.25, verbose=False)[0]

    current_detections = []
    detected_predator = False

    for box in results.boxes:
        cls_id = int(box.cls[0].item())
        conf = float(box.conf[0].item())
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        w = x2 - x1
        h = y2 - y1

        # Tự động phát hiện thú săn mồi (mèo, chó, v.v.)
        if cls_id in PREDATOR_CLASSES:
            detected_predator = True
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
            cv2.putText(frame, f"PREDATOR! {conf:.2f}", (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            continue

        # Lọc đối tượng chim (hoặc nhận diện mọi vật mẫu trong chế độ Demo)
        is_bird = (cls_id == CLASS_BIRD)
        is_demo_target = (not ai_mode_strict) and (w * h > 1500) and (cls_id not in [0]) # Loại trừ cả người

        if is_bird or is_demo_target:
            label_text = f"Swiftlet {conf:.2f}" if is_bird else f"Obj {conf:.2f}"
            current_detections.append((cx, cy, (x1, y1, w, h), label_text))
            
            # Vẽ Bounding Box & Centroid của AI
            color = (0, 255, 0) if is_bird else (255, 200, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
            cv2.putText(frame, label_text, (x1, max(20, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

    # Nếu AI tự động thấy mèo/thú săn mồi
    if detected_predator and (now - predator_alert_time > 5.0):
        predator_alert_time = now
        print("[AI ALERT] Phat hien THU SAN MOI xam nhap! Ban MQTT Alarm...")
        try:
            alert_payload = {
                "nodeId": NODE_ID,
                "alertType": "PREDATOR_INTRUSION",
                "message": "AI YOLOv8 phat hien dong vat san moi tai cua thu chim!",
                "timestamp": int(now)
            }
            mqtt_client.publish(TOPIC_ALARM, json.dumps(alert_payload))
        except:
            pass

    # Theo dõi quỹ đạo (Centroid Tracking)
    matched_ids = set()
    for (cx, cy, rect, label) in current_detections:
        best_id = None
        min_dist = 90.0

        for oid, obj in tracked_objects.items():
            if oid in matched_ids:
                continue
            last_cx, last_cy = obj.centroids[-1]
            dist = np.hypot(cx - last_cx, cy - last_cy)
            if dist < min_dist:
                min_dist = dist
                best_id = oid

        if best_id is not None:
            tracked_objects[best_id].centroids.append((cx, cy))
            tracked_objects[best_id].last_seen = now
            matched_ids.add(best_id)
        else:
            new_bird = TrackedBird(next_id, (cx, cy), label)
            tracked_objects[next_id] = new_bird
            matched_ids.add(next_id)
            next_id += 1

    # Kiểm tra vượt Cổng Đếm 2 Vạch (Dual-Line Virtual Gate)
    for oid, obj in list(tracked_objects.items()):
        # Vẽ vệt di chuyển
        if len(obj.centroids) >= 2:
            pts = np.array(obj.centroids[-12:], np.int32).reshape((-1, 1, 2))
            cv2.polylines(frame, [pts], False, (0, 255, 255), 2)

        if not obj.counted and len(obj.centroids) >= 2:
            first_y = obj.centroids[0][1]
            latest_y = obj.centroids[-1][1]

            # VƯỢT VẠCH 1 XUỐNG VẠCH 2: CHIM VÀO NHÀ (IN)
            if first_y < GATE_Y1 and latest_y > GATE_Y2:
                count_in += 1
                obj.counted = True
                print(f"[NĐ 13/2020 AI] >>> XÁC NHẬN CHIM VÀO (+1 IN): {count_in} | Đàn trong nhà: {max(0, count_in - count_out)}")

            # VƯỢT VẠCH 2 LÊN VẠCH 1: CHIM BAY RA NGOÀI (OUT)
            elif first_y > GATE_Y2 and latest_y < GATE_Y1:
                count_out += 1
                obj.counted = True
                print(f"[NĐ 13/2020 AI] >>> XÁC NHẬN CHIM RA (+1 OUT): {count_out} | Đàn trong nhà: {max(0, count_in - count_out)}")

        # Xóa vật thể mất tích quá 0.6s
        if now - obj.last_seen > 0.6:
            del tracked_objects[oid]

    # Gửi dữ liệu lên MQTT Cloud mỗi 3 giây
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
                "aiEngine": "YOLOv8n Nano Vision",
                "complianceStandard": "NĐ 13/2020/NĐ-CP",
                "predatorDetected": (now - predator_alert_time < 5.0)
            }
        }
        try:
            mqtt_client.publish(TOPIC_CAMERA, json.dumps(payload))
        except:
            pass

    # ================= HUD GIAO DIỆN CHUYÊN NGHIỆP =================
    # Vạch 1: Entry Line
    cv2.line(frame, (30, GATE_Y1), (FRAME_W - 30, GATE_Y1), (255, 200, 0), 2)
    cv2.putText(frame, "VACH 1 (ENTRY GATE)", (35, GATE_Y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 200, 0), 1)

    # Vạch 2: Exit Line
    cv2.line(frame, (30, GATE_Y2), (FRAME_W - 30, GATE_Y2), (0, 165, 255), 2)
    cv2.putText(frame, "VACH 2 (EXIT GATE)", (35, GATE_Y2 + 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 165, 255), 1)

    # Header Bar
    cv2.rectangle(frame, (0, 0), (FRAME_W, 62), (18, 22, 28), -1)
    mode_text = "[MODE: BIRD AI (STRICT)]" if ai_mode_strict else "[MODE: DEMO (ALL OBJECTS)]"
    cv2.putText(frame, f"SWIFTLETCARE - CAMERA AI YOLOv8 {mode_text}", (12, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)

    total_inside = max(0, count_in - count_out)
    stats_str = f"CHIM VAO: {count_in}   |   CHIM RA: {count_out}   |   TONG DAN: {total_inside} con"
    cv2.putText(frame, stats_str, (12, 48),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (50, 240, 255), 2)

    # Footer Bar
    cv2.rectangle(frame, (0, FRAME_H - 26), (FRAME_W, FRAME_H), (18, 22, 28), -1)
    cv2.putText(frame, "ND 13/2020/ND-CP | ROAMING HOLE 40x30cm | [M] Mode | [P] Predator | [R] Reset | [Q] Exit",
                (10, FRAME_H - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 180, 180), 1)

    # Banner Cảnh báo Thú săn mồi
    if now - predator_alert_time < 5.0:
        cv2.rectangle(frame, (0, FRAME_H // 2 - 35), (FRAME_W, FRAME_H // 2 + 35), (0, 0, 220), -1)
        cv2.putText(frame, "CANH BAO NGUY HIEM: PHAT HIEN THU SAN MOI!",
                    (30, FRAME_H // 2 + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.68, (255, 255, 255), 2)

    cv2.imshow("SwiftletCare - Camera AI (YOLOv8 + ND 13/2020/ND-CP)", frame)

    # Xử lý phím bấm
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('r'):
        count_in = 0
        count_out = 0
        print("[AI RESET] Da reset so dem dan chim ve 0.")
    elif key == ord('m'):
        ai_mode_strict = not ai_mode_strict
        mode_name = "BIRD AI ONLY (COCO Class 14)" if ai_mode_strict else "DEMO ALL (Linh hoat moi vat)"
        print(f"[AI MODE] Da chuyen sang che do: {mode_name}")
    elif key == ord('p'):
        predator_alert_time = time.time()
        print("\n[CANH BAO] Thu San Moi! Dang gui MQTT Alarm len Cloud...")
        alert_payload = {
            "nodeId": NODE_ID,
            "alertType": "PREDATOR_INTRUSION",
            "message": "Nguoi dung kich hoat canh bao thu san moi tai cua thu chim",
            "timestamp": int(time.time())
        }
        try:
            mqtt_client.publish(TOPIC_ALARM, json.dumps(alert_payload))
        except:
            pass

cap.release()
cv2.destroyAllWindows()
mqtt_client.loop_stop()
print("[CAMERA] Da dong Camera AI va ngat ket noi MQTT.")
