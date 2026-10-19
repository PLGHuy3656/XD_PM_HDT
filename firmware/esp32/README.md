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

## 3. Giao thức truyền thông MQTT

* **Broker:** `broker.emqx.io` (Port `1883`)
* **Device ID:** `swc-node-01`
* **Topic Telemetry:** `swiftlet/telemetry/swc-node-01` (Gửi định kỳ mỗi 5s)
* **Topic Command:** `swiftlet/command/swc-node-01` (Nhận lệnh từ Backend/App)
* **Topic Ack:** `swiftlet/ack/swc-node-01` (Gửi xác nhận thực thi lệnh)
* **Topic Status (LWT):** `swiftlet/status/swc-node-01` (Cơ chế Last Will and Testament)

## 4. Hướng dẫn chạy trên Wokwi

1. Truy cập [Wokwi ESP32](https://wokwi.com/projects/new/esp32).
2. Sao chép nội dung `diagram.json`, `libraries.txt` và `sketch.ino` vào các tab tương ứng.
3. Bấm nút **Play (Run)** để khởi chạy mô phỏng.
4. Mở [HiveMQ Web Client](http://www.hivemq.com/demos/websocket-client/) hoặc [EMQX Web Client](https://www.emqx.com/en/mqtt-client-web) để kiểm tra luồng dữ liệu 2 chiều.

## 5. Mô phỏng ESP32 trên Wokwi cho hệ thống SwiftletCare

<img width="686" height="609" alt="image" src="https://github.com/user-attachments/assets/33dde06e-337b-4e2c-8cd4-e179e3819f87" />
