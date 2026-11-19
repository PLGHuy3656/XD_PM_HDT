# SwiftletCare — INT01 Integration Runbook (Management V1 + IoT + MQTT + Simulator + Gateway + Frontend)

## 1. Kiến trúc & Cách ly môi trường
INT01 chạy hoàn toàn độc lập với **Standalone Management V1** (`1xxxx`) và **Docker Demo** (`3000`/`8000`):
- **Docker Project:** `swiftletcare-int01`
- **Network:** `swiftletcare-int01-net`
- **Volumes:** `swiftletcare_int01_pg_data`, `swiftletcare_int01_redis_data`
- **Host Ports (`127.0.0.1` only):**
  - Frontend Web UI: `http://127.0.0.1:23000`
  - API Gateway: `http://127.0.0.1:28000`
  - Management Service: `http://127.0.0.1:28001`
  - IoT Service: `http://127.0.0.1:28002`
  - PostgreSQL: `127.0.0.1:25432`
  - Redis: `127.0.0.1:26379`
  - Mosquitto MQTT: `127.0.0.1:21883`

## 2. Khởi tạo cấu hình
```powershell
Copy-Item .env.int01.example .env.int01
# Điền mật khẩu và INTERNAL_SERVICE_TOKEN (>= 32 ký tự ASCII) trong .env.int01
# KHÔNG commit file .env.int01 vào Git.
```

## 3. Lệnh vận hành (Chỉ tác động tài nguyên INT01)
```powershell
# Kiểm tra cấu hình Compose
docker compose -p swiftletcare-int01 -f docker-compose.int01.yml --env-file .env.int01 config

# Khởi động INT01 (7 services lõi)
docker compose -p swiftletcare-int01 -f docker-compose.int01.yml --env-file .env.int01 up -d --build

# Khởi động thêm ESP32 Simulator (tuỳ chọn)
docker compose -p swiftletcare-int01 -f docker-compose.int01.yml --env-file .env.int01 --profile simulator up -d esp32-simulator

# Xem trạng thái / logs
docker compose -p swiftletcare-int01 -f docker-compose.int01.yml --env-file .env.int01 ps
docker compose -p swiftletcare-int01 -f docker-compose.int01.yml --env-file .env.int01 logs -f

# Dừng INT01 nhưng GIỮ dữ liệu PostgreSQL/Redis
docker compose -p swiftletcare-int01 -f docker-compose.int01.yml --env-file .env.int01 stop

# Reset sạch CHỈ dữ liệu INT01 (chỉ dùng khi được phê duyệt)
docker compose -p swiftletcare-int01 -f docker-compose.int01.yml --env-file .env.int01 --profile simulator down -v
```

## 4. Kịch bản Demo 4 Luồng (DEMO A–D)
- **DEMO A (Admin):** Đăng nhập `http://127.0.0.1:23000` -> Tạo & phê duyệt Farm -> Đăng ký thiết bị với `node_id` trùng `INT01_SIMULATOR_DEVICE_ID` -> Gán Zone.
- **DEMO B (Farm Owner):** Đăng nhập -> Chọn Farm -> Xem telemetry real-time (polling 3s có xác thực JWT) -> Chuyển chế độ `MANUAL` (nhận ACK) -> Bật/tắt rơ-le phun sương -> Xem trạng thái `PENDING -> SUCCESS`.
- **DEMO C (Technician):** Đăng nhập -> Kiểm tra chỉ xem/điều khiển được thiết bị thuộc Farm được phân công -> Thử truy cập Farm khác bị chặn `403`.
- **DEMO D (IoT Failure):** Dừng container `esp32-simulator` -> Quan sát LWT chuyển `OFFLINE` -> Gửi lệnh khi offline nhận `TIMEOUT` -> Khởi động lại simulator -> Quay lại `ONLINE`.

## 5. Giới hạn đã ghi nhận tại INT01
- **Telemetry Persistence:** IoT Service dùng `InMemoryTelemetryRepository` (dữ liệu telemetry mất khi restart `iot-service`; dữ liệu lịch sử bền vững thuộc phạm vi `INT04` Analytics).
- **WebSocket:** `/ws/iot` nội bộ chưa có farm-scoped auth nên không mở trực tiếp ra browser; Frontend dùng authenticated farm-scoped REST polling qua Gateway.
- **ESP32 Hardware:** Chưa nghiệm thu mạch ESP32/cảm biến vật lý; sử dụng `firmware/esp32_simulator.py` qua Mosquitto thật.
