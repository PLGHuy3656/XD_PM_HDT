# SWIFTLETCARE — CROSS-MEMBER ACCEPTANCE CHECKLIST (CP15)
**Danh Mục Kiểm Thử Chéo Tiếp Nhận Hệ Thống Toàn Diện Giữa Các Thành Viên**

**Phiên bản:** CP15 Portable Release  
**Nhánh nguồn:** `feature/cp14-system-consolidation` (HEAD `58b757f`)  
**Người lập:** Senior Full-Stack & System Integration Engineer (TV4)  
**Phạm vi áp dụng:** TV1 (IoT), TV2 (AI), TV3 (Data & Monitoring), TV4 (Frontend & Gateway)

---

## MỤC LỤC
1. [Hướng Dẫn Áp Dụng Checklist](#1-h%C6%B0%E1%BB%9Bng-d%E1%BA%ABn-%C3%A1p-d%E1%BB%A5ng-checklist)
2. [Checklist Cho TV1 — IoT & Hardware Integration](#2-checklist-cho-tv1--iot--hardware-integration)
3. [Checklist Cho TV2 — AI Vision & Audio Model](#3-checklist-cho-tv2--ai-vision--audio-model)
4. [Checklist Cho TV3 — Data Engineering & Observability](#4-checklist-cho-tv3--data-engineering--observability)
5. [Checklist Cho TV4 — Frontend, Gateway & Platform](#5-checklist-cho-tv4--frontend-gateway--platform)
6. [Biên Bản Xác Nhận Nghiệm Thu (Acceptance Sign-off)](#6-bi%C3%AAn-b%E1%BA%A3n-x%C3%A1c-nh%E1%BA%ADn-nghi%E1%BB%87m-thu-acceptance-sign-off)

---

## 1. HƯỚNG DẪN ÁP DỤNG CHECKLIST

- Mỗi thành viên tải gói `SwiftletCare_Full_System_Team_Test.zip`, giải nén và khởi chạy hệ thống bằng lệnh:
  ```bash
  docker compose -p swiftletcare-team -f docker-compose.team.yml up -d --build
  ```
- Thực hiện lần lượt các ca kiểm thử thuộc quyền phụ trách chuyên môn của mình, đồng thời kiểm thử chéo 2–3 ca của thành viên khác để xác nhận tính tương thích toàn diện trước khi bắt tay vào phát triển phiên bản Mobile App.

---

## 2. CHECKLIST CHO TV1 — IOT & HARDWARE INTEGRATION

| Test ID | Tính Năng / Dịch Vụ | Điều Kiện Tiên Quyết (Preconditions) | Các Bước Thực Hiện (Steps) | Kết Quả Mong Đợi (Expected Outcome) | Đánh Giá (PASS/FAIL) |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **TC-TV1-01** | IoT Service Healthcheck | Docker stack đang chạy bình thường | Gọi `GET http://localhost:8002/health` qua cURL hoặc trình duyệt | Trả về HTTP 200 `{"status":"healthy","service":"iot-service"}` | [ ] PASS<br>[ ] FAIL |
| **TC-TV1-02** | Mosquitto MQTT Broker Connectivity | Container Mosquitto port 1883 mở | Dùng MQTT client (MQTTX) kết nối vào `localhost:1883` không user/pass | Kết nối thành công (Connection Accepted, Return Code 0) | [ ] PASS<br>[ ] FAIL |
| **TC-TV1-03** | Telemetry Ingestion via MQTT | Đã kết nối MQTT Broker | Publish gói tin JSON nhiệt ẩm lên topic `farm/{farm_id}/sensor/{node_id}/telemetry` | Log `iot-service` ghi nhận nhận telemetry thành công, không báo lỗi parse schema | [ ] PASS<br>[ ] FAIL |
| **TC-TV1-04** | Latest Telemetry Cache API | Đã gửi telemetry ở TC-TV1-03 | Gọi `GET http://localhost:8002/api/v1/iot/telemetry/latest?node_id={node_id}` | Trả về HTTP 200 kèm đúng dữ liệu nhiệt ẩm, `audioRms`, `rssi` vừa publish | [ ] PASS<br>[ ] FAIL |
| **TC-TV1-05** | Actuator Command Relay | IoT Service & RabbitMQ đang chạy | Gửi `POST /api/v1/iot/actuators/{device_id}/command` với payload `{"action":"ON"}` | IoT Service chuyển lệnh thành MQTT message trên topic `farm/{id}/actuator/{id}/command` | [ ] PASS<br>[ ] FAIL |
| **TC-TV1-06** | Telemetry Schema Tolerance | Schema telemetry v1 | Gửi telemetry thiếu trường không bắt buộc (ví dụ `battery` null) | IoT Service xử lý bình thường, gán giá trị mặc định, không ném ngoại lệ 500 | [ ] PASS<br>[ ] FAIL |

---

## 3. CHECKLIST CHO TV2 — AI VISION & AUDIO MODEL

| Test ID | Tính Năng / Dịch Vụ | Điều Kiện Tiên Quyết (Preconditions) | Các Bước Thực Hiện (Steps) | Kết Quả Mong Đợi (Expected Outcome) | Đánh Giá (PASS/FAIL) |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **TC-TV2-01** | AI Service Healthcheck | AI container đang chạy | Gọi `GET http://localhost:8003/health` | Trả về HTTP 200 `{"status":"healthy","service":"ai-service"}` | [ ] PASS<br>[ ] FAIL |
| **TC-TV2-02** | Isolated Safety Test Suite | Container AI chạy bình thường | Thực thi lệnh: `docker compose -p swiftletcare-team -f docker-compose.team.yml exec ai-service pytest tests/test_isolated_runner.py -v` | Vượt qua **14/14 safety tests PASS**, không có cảnh báo ghi đè CSDL chính | [ ] PASS<br>[ ] FAIL |
| **TC-TV2-03** | Camera Registry Query | CSDL `ai_db` đã khởi tạo | Gọi qua Gateway `GET http://localhost:8000/api/v1/ai/cameras` kèm Admin JWT token | Trả về HTTP 200 kèm danh sách camera đã đăng ký của các nhà yến demo | [ ] PASS<br>[ ] FAIL |
| **TC-TV2-04** | Bird Count Query API | Dữ liệu camera demo có sẵn | Gọi `GET http://localhost:8000/api/v1/ai/counts/latest?camera_id=CAM-01` | Trả về HTTP 200 kèm `entry_count`, `exit_count`, `net_inside` và `confidence_avg` | [ ] PASS<br>[ ] FAIL |
| **TC-TV2-05** | Fallback Khi Không Có RTSP | Không có luồng camera thật | Mở trang `/owner/swiftlets` trên Frontend | Giao diện hiển thị trạng thái `Chưa có luồng phát` thân thiện, không báo lỗi crash JS | [ ] PASS<br>[ ] FAIL |
| **TC-TV2-06** | Acoustic Telemetry Handling | IoT gửi trường `audioRms` | Kiểm tra API hoặc DB có lưu trữ chỉ số âm học | Trường `audioRms` và `audioHealthy` được lưu trữ toàn vẹn (sẵn sàng cho OQ-04) | [ ] PASS<br>[ ] FAIL |

---

## 4. CHECKLIST CHO TV3 — DATA ENGINEERING & OBSERVABILITY

| Test ID | Tính Năng / Dịch Vụ | Điều Kiện Tiên Quyết (Preconditions) | Các Bước Thực Hiện (Steps) | Kết Quả Mong Đợi (Expected Outcome) | Đánh Giá (PASS/FAIL) |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **TC-TV3-01** | Notification Service Health | Container Notification chạy | Gọi `GET http://localhost:8004/health` | Trả về HTTP 200 `{"status":"healthy","service":"notification-service"}` | [ ] PASS<br>[ ] FAIL |
| **TC-TV3-02** | Analytics Service Health | Container Analytics chạy | Gọi `GET http://localhost:8005/health` | Trả về HTTP 200 `{"status":"healthy","service":"analytics-service"}` | [ ] PASS<br>[ ] FAIL |
| **TC-TV3-03** | RabbitMQ Management Console | Container RabbitMQ mở cổng 15672 | Truy cập `http://localhost:15672` bằng user `swiftlet` / `swiftlet123` | Đăng nhập thành công vào bảng điều khiển quản trị RabbitMQ Overview | [ ] PASS<br>[ ] FAIL |
| **TC-TV3-04** | In-App Alert Query API | CSDL `notification_db` sẵn sàng | Gọi `GET http://localhost:8000/api/v1/notifications` với Owner JWT token | Trả về HTTP 200 kèm danh sách cảnh báo (ngưỡng nhiệt độ, cảm biến) | [ ] PASS<br>[ ] FAIL |
| **TC-TV3-05** | Environmental Daily Rollup | Có dữ liệu telemetry trong DB | Gọi `GET http://localhost:8000/api/v1/analytics/environmental/summary?farm_id=...&period=daily` | Trả về HTTP 200 kèm các giá trị min/max/avg nhiệt độ, độ ẩm | [ ] PASS<br>[ ] FAIL |
| **TC-TV3-06** | Grafana Dashboard & Prometheus | Cụm monitoring đang chạy | Truy cập `http://localhost:3001` (Grafana) và `http://localhost:9090` (Prometheus) | Grafana mở bình thường, Prometheus hiển thị các target microservice trạng thái UP | [ ] PASS<br>[ ] FAIL |
| **TC-TV3-07** | pgAdmin 4 Docker DB Connect | pgAdmin cài trên máy cá nhân | Kết nối vào `localhost:5433` user `postgres` / `postgres_demo_2026` | Kết nối thành công, thấy đủ 4 CSDL: `management_db`, `ai_db`, `notification_db`, `analytics_db` | [ ] PASS<br>[ ] FAIL |

---

## 5. CHECKLIST CHO TV4 — FRONTEND, GATEWAY & PLATFORM

| Test ID | Tính Năng / Dịch Vụ | Điều Kiện Tiên Quyết (Preconditions) | Các Bước Thực Hiện (Steps) | Kết Quả Mong Đợi (Expected Outcome) | Đánh Giá (PASS/FAIL) |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **TC-TV4-01** | Frontend Web App Delivery | Container Frontend đang chạy | Truy cập `http://localhost:3000/` trên trình duyệt | Giao diện React 19 tải thành công trong vòng < 2 giây, không có lỗi console trắng trang | [ ] PASS<br>[ ] FAIL |
| **TC-TV4-02** | API Gateway Routing & Reverse Proxy| Gateway mở cổng 8000 | Truy cập `http://localhost:8000/health` và `http://localhost:8000/docs` | Swagger UI hiển thị đầy đủ tài liệu API của tất cả microservices | [ ] PASS<br>[ ] FAIL |
| **TC-TV4-03** | Admin Full Authentication Flow | Frontend & Management chạy | Đăng nhập bằng `admin.demo@nestmate.dev` / `admin_demo_password_2026` | Đăng nhập thành công, chuyển hướng vào `/admin/dashboard`, hiển thị tên Quản trị viên | [ ] PASS<br>[ ] FAIL |
| **TC-TV4-04** | Live Users Management (FR-UAM-05)| Đang ở quyền Admin | Vào trang `/admin/users`, nhấn **Thêm người dùng**, nhập thông tin hợp lệ và Lưu | Người dùng mới được thêm ngay lập tức vào bảng và lưu thành công vào CSDL | [ ] PASS<br>[ ] FAIL |
| **TC-TV4-05** | Server-Side Logout (FR-UAM-02) | Đang đăng nhập bất kỳ role nào | Nhấn nút **Đăng xuất** ở thanh điều hướng | Hệ thống gọi `POST /api/auth/logout`, thu hồi token trên Redis và đưa về `/login` | [ ] PASS<br>[ ] FAIL |
| **TC-TV4-06** | Farm Owner Complete Journey | Tài khoản Chủ trại A | Đăng nhập `owner.a.demo@nestmate.dev` -> Xem Dashboard -> Xem Telemetry -> Xem Cảnh báo | Tất cả các trang hiển thị dữ liệu mượt mà, không gặp lỗi TypeError Javascript | [ ] PASS<br>[ ] FAIL |
| **TC-TV4-07** | Technician Node Diagnostics | Tài khoản Kỹ thuật viên A | Đăng nhập `tech.a.demo@nestmate.dev` -> Vào `/technician/diagnostics` | Hiển thị bảng danh sách node, chỉ số RSSI và pin, xử lý fallback an toàn nếu node offline | [ ] PASS<br>[ ] FAIL |
| **TC-TV4-08** | Unauthorized Access Block | Không đăng nhập (Guest) | Cố tình truy cập trực tiếp URL `http://localhost:3000/admin/users` | Hệ thống chặn lại và tự động chuyển hướng về `/login` | [ ] PASS<br>[ ] FAIL |

---

## 6. BIÊN BẢN XÁC NHẬN NGHIỆM THU (ACCEPTANCE SIGN-OFF)

Sau khi cả 4 thành viên hoàn thành chạy thử trên máy cá nhân và xác nhận PASS toàn bộ các ca kiểm thử:

- **Đại diện TV1 (IoT & Hardware):** ____________________  | Ngày: ____/____/2026 | Ý kiến: ________________________
- **Đại diện TV2 (AI & Vision):** ____________________  | Ngày: ____/____/2026 | Ý kiến: ________________________
- **Đại diện TV3 (Data & Monitoring):** ____________________  | Ngày: ____/____/2026 | Ý kiến: ________________________
- **Đại diện TV4 (Frontend & Platform):** ____________________  | Ngày: ____/____/2026 | Ý kiến: ________________________

> **Kết luận chung:** Toàn bộ hệ thống đạt tiêu chuẩn **READY FOR MOBILE DEVELOPMENT**. Bắt đầu chuyển giao API contracts cho đội ngũ phát triển Mobile Application.
