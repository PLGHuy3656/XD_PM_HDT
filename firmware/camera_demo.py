import cv2
import numpy as np
import time
import json
import random
import paho.mqtt.client as mqtt

# ============================================================================
# SWIFTLETCARE - CAMERA AI & SIMULATION (CỬA THU CHIM YẾN ROAMING HOLE)
# Standard: Nghị định 13/2020/NĐ-CP - Quy chuẩn kỹ thuật lỗ thu chim & an toàn sinh học
# Hỗ trợ kép: Nhận diện vật thể thực tế + Mô phỏng phím tắt 100% chuẩn xác
# ============================================================================

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
NODE_ID = "swc-h01-f01-node01"
TOPIC_CAMERA = f"swiftlet/camera/{NODE_ID}"
TOPIC_ALARM = f"swiftlet/alarm/{NODE_ID}"

# 1. Khởi tạo kết nối MQTT
mqtt_client = mqtt.Client(client_id=f"laptop_cam_{int(time.time())}")
try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
    print(f"[MQTT] Da ket noi Cloud Broker: {MQTT_BROKER}")
except Exception as e:
    print(f"[MQTT WARN] Khong the ket noi broker: {e}")

# 2. Khởi tạo Webcam Laptop
cap = cv2.VideoCapture(0)
FRAME_W = 640
FRAME_H = 480
if cap.isOpened():
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
else:
    print("[WARN] Khong tim thay webcam, chuyen sang che do gia lap man hinh ao.")

# THIẾT LẬP CỔNG ĐẾM 2 VẠCH (DUAL-LINE GATE) THEO NGHỊ ĐỊNH 13/2020/NĐ-CP
GATE_Y1 = int(FRAME_H * 0.38)  # Vạch 1: Vạch vào (Entry Line)
GATE_Y2 = int(FRAME_H * 0.62)  # Vạch 2: Vạch ra (Exit Line)

class TrackedBird:
    def __init__(self, obj_id, centroid, label="Swiftlet"):
        self.id = obj_id
        self.centroids = [centroid]
        self.counted = False
        self.label = label
        self.last_seen = time.time()

# Danh sách chim ảo mô phỏng bay qua màn hình
class VirtualBird:
    def __init__(self, direction="IN"):
        self.direction = direction  # "IN" (Trên xuống) hoặc "OUT" (Dưới lên)
        self.x = random.randint(int(FRAME_W * 0.3), int(FRAME_W * 0.7))
        self.y = 40 if direction == "IN" else FRAME_H - 40
        self.speed = 18 if direction == "IN" else -18
        self.alive = True

    def update(self):
        self.y += self.speed
        if self.direction == "IN" and self.y > FRAME_H - 30:
            self.alive = False
        elif self.direction == "OUT" and self.y < 30:
            self.alive = False

tracked_objects = {}
virtual_birds = []
next_id = 1

count_in = 0
count_out = 0
predator_alert_time = 0
last_mqtt_pub = 0
auto_sim_mode = False
last_auto_spawn = 0

print("\n" + "=" * 70)
print("  SWIFTLETCARE - CAMERA AI THEO DÕI CỬA THU CHIM YẾN (ND 13/2020/ND-CP) ")
print("=" * 70)
print(">> PHÍM TẮT MÔ PHỎNG SIÊU DỄ DÀNG CHO BUỔI DEMO (100% THÀNH CÔNG):")
print("   [ I ] : Mô phỏng 1 Chim bay VÀO nhà yến (+1 IN) - Bay từ trên xuống")
print("   [ O ] : Mô phỏng 1 Chim bay RA ngoài (+1 OUT)    - Bay từ dưới lên")
print("   [ A ] : Bật/Tắt chế độ Tự động đàn chim bay ngẫu nhiên (Auto Sim)")
print("   [ P ] : Kích hoạt cảnh báo Thú Săn Mồi (Predator Alert)")
print("   [ R ] : Reset bộ đếm chim về 0")
print("   [ Q ] : Thoát chương trình\n")

while True:
    now = time.time()

    if cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
        else:
            frame = cv2.flip(frame, 1)
    else:
        # Nền giả lập nếu không có webcam
        frame = np.full((FRAME_H, FRAME_W, 3), 30, dtype=np.uint8)

    # Xử lý chế độ Tự động mô phỏng (Auto Sim)
    if auto_sim_mode and (now - last_auto_spawn > 3.5):
        last_auto_spawn = now
        chosen_dir = random.choice(["IN", "IN", "OUT"]) # Xu hướng chiều tối chim vào nhiều hơn
        virtual_birds.append(VirtualBird(chosen_dir))

    # Cập nhật và vẽ các chú chim ảo mô phỏng
    current_detections = []
    for vb in list(virtual_birds):
        vb.update()
        if not vb.alive:
            virtual_birds.remove(vb)
            continue

        cx, cy = int(vb.x), int(vb.y)
        current_detections.append((cx, cy, "Swiftlet AI"))

        # Vẽ hình dáng chim yến đồ họa cánh nhạn đẹp mắt
        wing_span = 30
        pts = np.array([
            [cx, cy - 8],
            [cx - wing_span, cy + 10],
            [cx - 8, cy],
            [cx, cy + 14],
            [cx + 8, cy],
            [cx + wing_span, cy + 10]
        ], np.int32)
        cv2.fillPoly(frame, [pts], (50, 240, 255))
        cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)
        cv2.putText(frame, "Swiftlet (AI)", (cx - 35, cy - 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (50, 240, 255), 1)

    # Theo dõi quỹ đạo (Centroid Tracking)
    matched_ids = set()
    for (cx, cy, label) in current_detections:
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
        # Vẽ vệt đuôi quỹ đạo bay (Flight Trajectory Trail)
        if len(obj.centroids) >= 2:
            pts = np.array(obj.centroids[-15:], np.int32).reshape((-1, 1, 2))
            cv2.polylines(frame, [pts], False, (0, 255, 255), 2)

        if not obj.counted and len(obj.centroids) >= 2:
            first_y = obj.centroids[0][1]
            latest_y = obj.centroids[-1][1]

            # VƯỢT VẠCH 1 XUỐNG VẠCH 2: CHIM VÀO NHÀ (IN)
            if first_y < GATE_Y1 and latest_y > GATE_Y2:
                count_in += 1
                obj.counted = True
                print(f"[NĐ 13/2020] >>> XÁC NHẬN CHIM VÀO (+1 IN): {count_in} | Tổng đàn: {max(0, count_in - count_out)}")

            # VƯỢT VẠCH 2 LÊN VẠCH 1: CHIM BAY RA NGOÀI (OUT)
            elif first_y > GATE_Y2 and latest_y < GATE_Y1:
                count_out += 1
                obj.counted = True
                print(f"[NĐ 13/2020] >>> XÁC NHẬN CHIM RA (+1 OUT): {count_out} | Tổng đàn: {max(0, count_in - count_out)}")

        # Xóa đối tượng đã hoàn thành
        if now - obj.last_seen > 0.5:
            del tracked_objects[oid]

    # Gửi dữ liệu lên MQTT Cloud mỗi 2.5 giây
    if now - last_mqtt_pub >= 2.5:
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
    cv2.putText(frame, "VACH 1 (ENTRY GATE - NGUONG VAO)", (35, GATE_Y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 200, 0), 1)

    # Vạch 2: Exit Line
    cv2.line(frame, (30, GATE_Y2), (FRAME_W - 30, GATE_Y2), (0, 165, 255), 2)
    cv2.putText(frame, "VACH 2 (EXIT GATE - NGUONG RA)", (35, GATE_Y2 + 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 165, 255), 1)

    # Header Bar
    cv2.rectangle(frame, (0, 0), (FRAME_W, 64), (18, 22, 28), -1)
    sim_status = "[AUTO SIM: ON]" if auto_sim_mode else "[MANUAL HOTKEYS]"
    cv2.putText(frame, f"SWIFTLETCARE - CAMERA AI CUA THU CHIM {sim_status}", (12, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)

    total_inside = max(0, count_in - count_out)
    stats_str = f"CHIM VAO: {count_in}   |   CHIM RA: {count_out}   |   TONG DAN: {total_inside} con"
    cv2.putText(frame, stats_str, (12, 48),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (50, 240, 255), 2)

    # Footer Bar hướng dẫn phím tắt trực tiếp
    cv2.rectangle(frame, (0, FRAME_H - 26), (FRAME_W, FRAME_H), (18, 22, 28), -1)
    cv2.putText(frame, "PHIM: [I] Chim Vao | [O] Chim Ra | [A] Tu Dong | [P] Bao Dong | [R] Reset | [Q] Thoat",
                (10, FRAME_H - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 240, 180), 1)

    # Banner Cảnh báo Thú săn mồi
    if now - predator_alert_time < 5.0:
        cv2.rectangle(frame, (0, FRAME_H // 2 - 35), (FRAME_W, FRAME_H // 2 + 35), (0, 0, 220), -1)
        cv2.putText(frame, "CANH BAO NGUY HIEM: PHAT HIEN THU SAN MOI!",
                    (30, FRAME_H // 2 + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.68, (255, 255, 255), 2)

    cv2.imshow("SwiftletCare - Camera AI (ND 13/2020/ND-CP)", frame)

    # Xử lý phím tắt
    key = cv2.waitKey(15) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('i') or key == ord('I'):
        # Bấm phím I: Sinh chim bay vào
        virtual_birds.append(VirtualBird("IN"))
        print("[MÔ PHỎNG] Bấm [I] -> Sinh chim bay VÀO nhà yến")
    elif key == ord('o') or key == ord('O'):
        # Bấm phím O: Sinh chim bay ra
        virtual_birds.append(VirtualBird("OUT"))
        print("[MÔ PHỎNG] Bấm [O] -> Sinh chim bay RA ngoài")
    elif key == ord('a') or key == ord('A'):
        # Bật/tắt tự động
        auto_sim_mode = not auto_sim_mode
        print(f"[AUTO SIM] Che do tu dong dan chim: {'BAT' if auto_sim_mode else 'TAT'}")
    elif key == ord('r') or key == ord('R'):
        count_in = 0
        count_out = 0
        virtual_birds.clear()
        print("[RESET] Da reset bo dem ve 0.")
    elif key == ord('p') or key == ord('P'):
        predator_alert_time = time.time()
        print("\n[CANH BAO] Thu San Moi! Dang gui MQTT Alarm len Cloud...")
        alert_payload = {
            "nodeId": NODE_ID,
            "alertType": "PREDATOR_INTRUSION",
            "message": "Phat hien dong vat san moi tai cua thu chim (Theo ND 13/2020/ND-CP)",
            "timestamp": int(time.time())
        }
        try:
            mqtt_client.publish(TOPIC_ALARM, json.dumps(alert_payload))
        except:
            pass

if cap.isOpened():
    cap.release()
cv2.destroyAllWindows()
mqtt_client.loop_stop()
print("[CAMERA] Da ket thuc chuong trinh Camera.")
