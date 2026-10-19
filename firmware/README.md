# SwiftletCare Firmware Subsystem

Phân hệ Firmware & IoT đóng vai trò là tầng giao tiếp vật lý của hệ sinh thái **SwiftletCare**, chịu trách nhiệm thu thập dữ liệu vi khí hậu, điều khiển cơ cấu chấp hành và duy trì vận hành tự động cục bộ (Offline Resiliency) trong nhà yến.

## Cấu trúc thư mục

```text
firmware/
├── esp32/            # Firmware node điều khiển môi trường và vi khí hậu (ESP32)
│   ├── diagram.json
│   ├── libraries.txt
│   ├── sketch.ino
│   └── README.md
└── README.md
```

## Các module phần cứng chính

1. **`esp32/`** — Environmental Controller Node:
   - Vi điều khiển: ESP32-WROOM-32.
   - Đo đạc: Nhiệt độ, độ ẩm (DHT22 / SHT31), âm thanh loa ru (ADC).
   - Điều khiển: 4 kênh rơ-le cách ly (Máy tạo ẩm, quạt thông gió, máy sưởi, còi báo động).
   - Truyền thông: MQTT qua Wi-Fi (JSON Payload hai chiều, LWT, Command Ack).
   - Thuật toán: Closed-loop Hysteresis tự động duy trì $27 - 31^\circ\text{C}$ và $75 - 90\%\text{ RH}$.
