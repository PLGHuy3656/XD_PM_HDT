# 🕊️ HƯỚNG DẪN KẾT NỐI ESP32 VỚI FRONTEND SWIFTLETCARE

Tài liệu này hướng dẫn chi tiết cách kết nối dữ liệu giữa phân hệ **Firmware ESP32 (TV1)** với **Giao diện Web Frontend (TV4)** thông qua **API Gateway & IoT Service**, đảm bảo bất kỳ thành viên nào trong nhóm khi clone code về máy đều có thể chạy được y hệt.

---

## 🏗️ 1. Kiến Trúc Luồng Dữ Liệu 2 Chiều (End-to-End)

```
[ ESP32 Node ] (Mạch thật / Wokwi / chay_esp32_ao.bat)
       │
       │ MQTT (Port 1883)
       │ Topic: swiftlet/telemetry/SWC-DEMO-NODE-001
       ▼
[ Mosquitto Broker ] (:1883)
       │
       ▼
[ IoT Microservice ] (:8002)
       │  (Chuẩn hóa dữ liệu TelemetryPayload, gán Farm ID)
       ▼
[ In-Memory Repository & Cache ]
       ▲
       │ Proxy GET /api/iot/farms/{farm_id}/telemetry/latest
[ API Gateway ] (:8000)
       ▲
       │ HTTP REST Polling (3s/lần)
[ Web Frontend React 19 ] (:3000)
       (Màn hình: /owner/environment & /owner/dashboard)
```

### Luồng điều khiển Rơ-le ngược lại (Web -> ESP32):
1. Người dùng bấm bật/tắt máy phun sương hoặc quạt trên Web.
2. Gateway chuyển lệnh `POST /api/iot/devices/SWC-DEMO-NODE-001/commands/relay` vào `iot-service`.
3. `iot-service` bắn MQTT xuống topic `swiftlet/command/SWC-DEMO-NODE-001`.
4. ESP32 nhận lệnh, đổi trạng thái chân GPIO và gửi lại ACK lên `swiftlet/ack/SWC-DEMO-NODE-001`.

---

## 🚀 2. Các Bước Chạy Thực Tế Trên Máy

### Bước 1: Khởi động hệ thống Docker (1 Click)
Vào thư mục dự án và nhấp đúp file:
👉 **`chay_he_thong.bat`**
*(Hoặc gõ lệnh trong CMD: `docker compose -p swiftletcare-team -f docker-compose.team.yml up -d`)*

Chờ 15 containers khởi động hoàn tất.

### Bước 2: Đăng nhập vào Giao diện Web
1. Mở trình duyệt truy cập: **[http://localhost:3000](http://localhost:3000)**
2. Đăng nhập tài khoản Chủ trại:
   - **Email:** `owner.a.demo@nestmate.dev`
   - **Mật khẩu:** `owner_demo_password_2026`
3. Chọn vào menu **Môi trường & Telemetry** (`/owner/environment`).
   - Khi chưa có ESP32 gửi dữ liệu, hệ thống báo `Chưa có telemetry`.

### Bước 3: Chạy ESP32 gửi dữ liệu (Chọn 1 trong 3 cách bên dưới)

---

## 🔌 3. Ba Cách Chạy ESP32 (Tùy Theo Phần Cứng Của Bạn)

### 👉 Cách A: Dùng Bộ Giả Lập ESP32 Ảo (Khuyên Dùng — Nhanh Nhất, Không Cần Mạch)
Dành cho mọi thành viên khi clone về muốn test ngay:
1. Vào thư mục: `firmware\`
2. Nhấp đúp chuột vào file: **`chay_esp32_ao.bat`**
3. Cửa sổ dòng lệnh sẽ hiện ra:
   - Tự động kết nối tới Mosquitto port 1883 trên máy bạn.
   - Bắn số liệu nhiệt ẩm (28.5°C, 82%), CO2, ánh sáng mỗi 3 giây.
   - Lắng nghe lệnh điều khiển rơ-le từ Web.
4. **Nhìn lại màn hình Web (`/owner/environment`)**:
   - Trạng thái lập tức chuyển sang chấm xanh: **"Dữ liệu trực tiếp" - "Cập nhật Vừa xong"**.
   - Các thẻ Nhiệt độ, Độ ẩm, CO2, Ánh sáng nhảy số trực tiếp theo dữ liệu từ file giả lập!

---

### 👉 Cách B: Chạy Trên Trình Mô Phỏng Wokwi (Trực quan mạch điện)
Dành cho việc quay video báo cáo hoặc demo mạch điện tử ảo:
1. Mở trình duyệt vào: **[https://wokwi.com/projects/new/esp32](https://wokwi.com/projects/new/esp32)**
2. Dán nội dung file `firmware/esp32/sketch.ino` vào tab code `sketch.ino`.
3. Dán nội dung file `firmware/esp32/diagram.json` vào tab `diagram.json`.
4. Bấm **Play (Run)** để chạy. Mạch ESP32 ảo sẽ khởi động và kết nối MQTT.

---

### 👉 Cách C: Nạp Vào Mạch ESP32 Thật Bằng Arduino IDE
Dành cho TV1 hoặc khi mang mạch đi chấm đồ án:
1. Mở file `firmware/esp32/sketch.ino` bằng Arduino IDE.
2. Tìm đến phần cấu hình ở đầu file và chỉnh lại 2 thông số:
   ```cpp
   #define WIFI_SSID_CFG       "Tên_WiFi_Nhà_Bạn"
   #define WIFI_PASSWORD_CFG   "Mật_Khẩu_WiFi"
   #define MQTT_BROKER_HOST    "192.168.1.X"   // Địa chỉ IPv4 của máy tính chạy Docker
   ```
   *(Để xem IP máy tính: Mở CMD gõ `ipconfig`, tìm dòng `IPv4 Address`)*.
3. Cắm cáp USB nối ESP32 với máy tính, chọn Board **ESP32 Dev Module** và bấm **Upload**.
4. Mạch thật sẽ đo cảm biến DHT22 và truyền trực tiếp vào Website qua Wi-Fi nội bộ!

---

## 👥 4. Hướng Dẫn Cho Người Khác Khi Clone Repo Về Máy

Khi các thành viên khác clone repo này về:
1. Cài đặt **Docker Desktop** (bật sẵn Engine).
2. Chạy file `chay_he_thong.bat`.
3. Mở web `http://localhost:3000`.
4. Chạy `firmware\chay_esp32_ao.bat` để bơm dữ liệu cảm biến.
5. Kiểm tra chéo theo bảng tiêu chí trong file `SWIFTLETCARE_Cross_Member_Acceptance_Checklist.md`.
