# SwiftletCare ESP32 Environmental Controller Node

Firmware cho thiết bị biên (IoT Edge Node) giám sát vi khí hậu và tự động hóa điều khiển môi trường nhà yến thuộc hệ sinh thái **SwiftletCare**.

## 1. Cấu trúc thư mục

```text
firmware/esp32/
├── diagram.json      # Sơ đồ kết nối phần cứng và bố cục linh kiện trên Wokwi
├── libraries.txt     # Danh sách thư viện phụ thuộc (Wokwi / Arduino IDE)
├── sketch.ino        # Mã nguồn C++ chính nạp vào ESP32
└── README.md         # Hướng dẫn chi tiết
```

## 2. Bảng sơ đồ chân (Pin Mapping)

| Thiết bị | Chân ESP32 | Loại tín hiệu | Vai trò trong hệ thống |
|---|---|---|---|
| **DHT22** | `GPIO 15` | Digital Input | Đo nhiệt độ và độ ẩm tương đối của nhà yến |
| **Potentiometer** | `GPIO 34` | Analog (ADC1_CH6) | Giả lập cảm biến âm thanh (MAX4466) kiểm tra loa ru |
| **LED Blue (Relay 1)** | `GPIO 25` | Digital Output | Máy phun sương / Máy tạo ẩm siêu âm |
| **LED Green (Relay 2)** | `GPIO 26` | Digital Output | Quạt thông gió / Quạt hút làm mát |
| **LED Red (Relay 3)** | `GPIO 27` | Digital Output | Đèn sưởi / Máy sưởi |
| **LED Orange (Relay 4)**| `GPIO 33` | Digital Output | Còi / Đèn chớp báo động sự cố hoặc thú săn mồi |

## 3. Giao thức truyền thông MQTT (Canonical Contract V1)

* **Default Demo Broker:** `broker.emqx.io` (Port `1883`, chỉ cho mô phỏng Wokwi)
* **Canonical Device ID:** `SWC-NODE-001`
* **Topic Telemetry:** `swiftlet/telemetry/SWC-NODE-001` (Gửi định kỳ mỗi 5s)
* **Topic Heartbeat:** `swiftlet/heartbeat/SWC-NODE-001` (Gửi định kỳ mỗi 30s)
* **Topic Command:** `swiftlet/command/SWC-NODE-001` (Nhận lệnh từ Backend/App)
* **Topic Ack:** `swiftlet/ack/SWC-NODE-001` (Gửi xác nhận thực thi lệnh)
* **Topic Status (LWT):** `swiftlet/status/SWC-NODE-001` (Cơ chế Last Will and Testament)

## 4. Hướng dẫn chạy trên Wokwi Simulation

1. Truy cập [Wokwi ESP32](https://wokwi.com/projects/new/esp32).
2. Sao chép nội dung `diagram.json`, `libraries.txt` và `sketch.ino` vào các tab tương ứng.
3. Bấm nút **Play (Run)** để khởi chạy mô phỏng.
4. Mở [HiveMQ Web Client](http://www.hivemq.com/demos/websocket-client/) hoặc [EMQX Web Client](https://www.emqx.com/en/mqtt-client-web) để kiểm tra luồng dữ liệu 2 chiều.

## 5. Kiến trúc MQTT, QoS & Giới hạn kỹ thuật

* **Đặc tả QoS của thư viện PubSubClient (Nick O'Leary):**
  * **Subscribe (Command):** Thiết bị đăng ký nhận lệnh với **QoS 1** (`mqttClient.subscribe(TOPIC_COMMAND, 1)`), giúp broker giữ và gửi lại lệnh khi thiết bị tái kết nối trong cùng session.
  * **Publish (Telemetry & ACK):** Thư viện `PubSubClient` giới hạn kiến trúc chỉ hỗ trợ **QoS 0** cho phương thức publish. Do đó, bản tin Telemetry và gói tin ACK phản hồi lệnh được gửi ở QoS 0.
  * **Cơ chế ACK:** Trong điều kiện sóng Wi-Fi hoặc mạng LAN không ổn định, gói tin ACK có thể bị rớt trên đường truyền. Backend / IoT Service cần áp dụng command timeout và polling trạng thái actuator qua Telemetry để xác nhận kép.

## 6. Cảnh báo an ninh mạng & Khuyến nghị Production

> [!WARNING]
> **CẢNH BÁO AN NINH BROKER CÔNG KHAI:**
> * Broker `broker.emqx.io` mặc định **CHỈ DÙNG CHO MỤC ĐÍCH MÔ PHỎNG WOKWI / DEMO**.
> * **TUYỆT ĐỐI KHÔNG** sử dụng broker công khai không xác thực để kết nối hoặc điều khiển thiết bị phần cứng thật trong môi trường trang trại thực tế.
> * Bất kỳ ai trên internet đều có thể nghe lén dữ liệu cảm biến hoặc inject lệnh điều khiển trái phép nếu dùng broker công khai.

* **Yêu cầu triển khai môi trường Production:**
  * Triển khai cụm MQTT Broker nội bộ (Mosquitto / EMQX Enterprise) trong mạng riêng (VLAN / VPN).
  * Kích hoạt xác thực bắt buộc (Username / Password hoặc Client Certificate mTLS).
  * Mã hóa toàn bộ đường truyền bằng **TLS/SSL (Port 8883)**.
  * Cấu hình thông tin kết nối và thông tin xác thực qua build flags (`-DMQTT_BROKER_HOST`, `-DMQTT_USER_CFG`, `-DMQTT_PASSWORD_CFG`) hoặc nạp vào Flash NVS an toàn, tuyệt đối không hardcode credentials trong mã nguồn.

## 7. Trạng thái kiểm chứng (Verification Status)

* **Bộ kiểm thử IoT Service:** `180/180 PASSED` (Python backend, API, WebSocket, MQTT routing, parsing).
* **Firmware Build:** `NOT VERIFIED` (Môi trường local CI/Dev chưa tích hợp toolchain biên dịch chéo `arduino-cli` hoặc `platformio-core`; mã nguồn được thẩm định tĩnh theo mô hình Wokwi simulation).
* **MQTT End-to-End (E2E) trên phần cứng thật:** `NOT VERIFIED` (Chưa chạy thử nghiệm end-to-end với module ESP32 vật lý và mạng LAN thực tế; đang chạy trên giả lập Wokwi và local test harness).

## 8. Minh họa mô phỏng ESP32 trên Wokwi

<img width="686" height="609" alt="image" src="https://github.com/user-attachments/assets/33dde06e-337b-4e2c-8cd4-e179e3819f87" />

Hình ảnh nhật ký khởi động và hoạt động của bộ điều khiển IoT SwiftletCare sử dụng ESP32
<img width="696" height="327" alt="image" src="https://github.com/user-attachments/assets/a2ed1b3e-31a2-46c3-bba9-7d987e2a7eec" />
