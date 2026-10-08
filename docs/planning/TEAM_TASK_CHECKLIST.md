# SwiftletCare — TEAM TASK CHECKLIST v0.1

> Status: Draft — chờ Team Review
> Scope: Theo SRS và Use Case hiện tại của nhóm
> Team size: 4
> Mục đích:
> - Làm cơ sở họp phân chia công việc
> - Sau khi chốt sẽ chuyển thành Jira Backlog
> - Theo dõi Requirement → Task → Integration → Test
>
> Lưu ý:
> - Đây chưa phải assignment cuối cùng.
> - Ownership chỉ xác định người chịu trách nhiệm chính.
> - Các interface giữa module phải được cả nhóm review.

---

# 0. TEAM OWNERSHIP

| Member | Primary Responsibility |
|---|---|
| TV1 – Leader | Frontend / Mobile / Testing / Documentation / Coordination |
| TV2 | Backend / Cloud Services |
| TV3 | Embedded IoT / Hardware / Firmware |
| TV4 | AI Pipeline / Computer Vision / Audio AI |

---

# A. TV1 — FRONTEND / MOBILE / TESTING

## A1. Frontend Foundation

- [ ] Hoàn thiện cấu trúc React project
- [ ] Cấu hình React Router
- [ ] Xây dựng authentication flow phía client
- [ ] Xây dựng role-based routing
- [ ] Xây dựng shared application layout
- [ ] Xây dựng reusable UI components
- [ ] Chuẩn hóa theme NestMate
- [ ] Responsive Web UI

## A2. Authentication UI

- [ ] Login Page
- [ ] Logout flow
- [ ] Unauthorized / Forbidden Page
- [ ] Điều hướng theo role:
      FARM_OWNER
      TECHNICIAN
      ADMINISTRATOR
- [ ] Mock authentication cho prototype
- [ ] Tích hợp Backend Authentication API khi API sẵn sàng

## A3. Farm Owner UI

- [ ] Farm Owner Dashboard
- [ ] House / Zone Management UI
- [ ] Environment Monitoring Page
- [ ] Current sensor cards
- [ ] Near-real-time environment update
- [ ] Environment History / Charts
- [ ] Environmental Threshold Configuration UI
- [ ] AUTO / MANUAL Control UI
- [ ] Manual Actuator Control UI
- [ ] Device Status Page
- [ ] Swiftlet Entry / Exit Monitoring Page
- [ ] Bird Movement Statistics
- [ ] Live Camera / Image View
- [ ] Predator Event View
- [ ] AI Snapshot / Bounding Box View
- [ ] Audio / Anomaly Status
- [ ] Alert List
- [ ] Alert Detail
- [ ] Alert Handling UI
- [ ] Analytics Dashboard

## A4. Technician UI

- [ ] Technician Dashboard
- [ ] Device List
- [ ] Device Detail
- [ ] Device Online / Offline Status
- [ ] Device Assignment to House / Zone
- [ ] Device Diagnostic UI
- [ ] Technical Alert Page
- [ ] Limited Control UI theo RBAC
- [ ] Device Configuration UI nếu được team chốt

## A5. Administrator UI

- [ ] Administrator Dashboard
- [ ] User Management
- [ ] Role Management
- [ ] Farm / House overview
- [ ] Device overview
- [ ] System Status
- [ ] System Configuration

## A6. Realtime & Notification Integration

- [ ] Tích hợp realtime environment update
- [ ] Tích hợp device status update
- [ ] Tích hợp AI event update
- [ ] Tích hợp alert update
- [ ] Firebase Cloud Messaging
- [ ] Mobile Push Notification

## A7. Testing

- [ ] Viết Frontend test cases
- [ ] Authentication test
- [ ] RBAC UI test
- [ ] Environment monitoring E2E test
- [ ] Control E2E test
- [ ] Device monitoring E2E test
- [ ] AI monitoring E2E test
- [ ] Alert E2E test
- [ ] Cross-module Integration Test
- [ ] Regression Test trước demo

---

# B. TV2 — BACKEND / CLOUD

## B1. Backend Foundation

- [ ] Chốt Backend technology cùng team
- [ ] Setup Backend project
- [ ] Thiết kế Microservices architecture
- [ ] API Gateway
- [ ] Docker environment
- [ ] OpenAPI / Swagger
- [ ] Redis integration
- [ ] Apache NiFi integration plan

## B2. Authentication & Authorization

- [ ] User model
- [ ] Login API
- [ ] Logout API
- [ ] Authentication mechanism
- [ ] RBAC:
      FARM_OWNER
      TECHNICIAN
      ADMINISTRATOR
- [ ] Farm / House scope authorization
- [ ] User management API
- [ ] Role management API

## B3. Farm / House / Zone

- [ ] Farm data model
- [ ] House data model
- [ ] Zone data model
- [ ] Farm API
- [ ] House API
- [ ] Zone API
- [ ] Device ↔ Zone association

## B4. IoT Telemetry

- [ ] MQTT Broker integration
- [ ] Telemetry ingestion service
- [ ] Validate telemetry
- [ ] Store telemetry
- [ ] Current environment API
- [ ] Environmental history API
- [ ] Realtime telemetry service
- [ ] Device heartbeat processing
- [ ] Online / Offline device state

## B5. Environmental Control

- [ ] Store environmental configuration
- [ ] Threshold Configuration API
- [ ] AUTO / MANUAL mode API
- [ ] Manual Control API
- [ ] Publish command Backend → MQTT
- [ ] Receive actuator state from IoT
- [ ] Synchronize control state
- [ ] Enforce authorization on control commands

> Backend quản lý configuration/command/history.
> ESP32 chịu trách nhiệm local automatic control.

## B6. AI Event Backend

- [ ] Define AI Event Contract với TV4
- [ ] Bird Count ingestion
- [ ] Entry / Exit record storage
- [ ] Predator event ingestion
- [ ] AI snapshot metadata handling
- [ ] Audio anomaly event ingestion
- [ ] Bird Count API
- [ ] AI Event API
- [ ] AI Event realtime update

## B7. Alert & Notification

- [ ] Alert data model
- [ ] Environmental alert processing
- [ ] Device alert processing
- [ ] AI predator alert processing
- [ ] Audio anomaly alert processing
- [ ] Alert List API
- [ ] Alert Detail API
- [ ] Alert status update
- [ ] Firebase Cloud Messaging
- [ ] Backend → IoT alarm trigger khi cần

## B8. Analytics

- [ ] Environmental history query
- [ ] Environment trend aggregation
- [ ] Entry / Exit history
- [ ] Bird movement statistics
- [ ] Alert history
- [ ] AI anomaly history

## B9. Backend Quality

- [ ] Input validation
- [ ] Error handling
- [ ] Authentication / Authorization tests
- [ ] API tests
- [ ] OpenAPI documentation
- [ ] Docker deployment verification

---

# C. TV3 — EMBEDDED IoT / HARDWARE

## C1. Hardware Prototype

- [ ] Chốt sensor set với team
- [ ] Chuẩn bị ESP32
- [ ] Kết nối temperature / humidity sensor
- [ ] Kết nối light sensor
- [ ] Kết nối CO2 / air-quality sensor nếu sử dụng
- [ ] Kết nối audio sensor nếu thuộc IoT Node
- [ ] Kết nối relay
- [ ] Kết nối misting actuator
- [ ] Kết nối ventilation fan
- [ ] Kết nối heater nếu prototype sử dụng
- [ ] Kết nối alarm / deterrent actuator

## C2. Sensor Firmware

- [ ] ESP32 firmware project
- [ ] Đọc temperature
- [ ] Đọc humidity
- [ ] Đọc light
- [ ] Đọc air quality / CO2 nếu có
- [ ] Đọc audio level nếu có
- [ ] Sensor validation
- [ ] Sensor fault handling
- [ ] Build telemetry payload

## C3. MQTT Communication

- [ ] Wi-Fi connection
- [ ] MQTT connection
- [ ] Publish telemetry
- [ ] Publish heartbeat
- [ ] Publish device state
- [ ] Subscribe control command
- [ ] Subscribe configuration update
- [ ] Auto reconnect Wi-Fi
- [ ] Auto reconnect MQTT

## C4. Environmental Control

- [ ] AUTO mode
- [ ] MANUAL mode
- [ ] Local threshold configuration
- [ ] Misting control
- [ ] Ventilation control
- [ ] Heating control nếu sử dụng
- [ ] Safety logic
- [ ] Publish actuator state

## C5. Offline Resilience

- [ ] Lưu configuration cần thiết tại Edge
- [ ] Local automatic control khi mất Internet
- [ ] Không phụ thuộc Backend để duy trì môi trường
- [ ] Reconnect khi Internet trở lại
- [ ] Đồng bộ lại trạng thái với Backend

## C6. AI → IoT Reaction

- [ ] Nhận alarm command từ Backend
- [ ] Trigger alarm / deterrent actuator
- [ ] Publish execution state
- [ ] Test Predator → Backend → IoT flow

## C7. Hardware Testing

- [ ] Sensor test
- [ ] Relay test
- [ ] MQTT connectivity test
- [ ] AUTO control test
- [ ] MANUAL control test
- [ ] Offline control test
- [ ] Reconnection test
- [ ] Hardware prototype documentation

---

# D. TV4 — AI PIPELINE

## D1. Dataset

- [ ] Thu thập Swiftlet dataset
- [ ] Thu thập predator dataset
- [ ] Xác định supported predator classes
- [ ] Annotate dataset
- [ ] Train / Validation / Test split
- [ ] Data augmentation

## D2. Swiftlet Detection

- [ ] Setup AI development environment
- [ ] Chọn lightweight YOLO model
- [ ] Train Swiftlet detector
- [ ] Evaluate Precision
- [ ] Evaluate Recall
- [ ] Evaluate mAP
- [ ] Optimize model cho Edge deployment

## D3. Multi-Object Tracking

- [ ] Tích hợp ByteTrack hoặc DeepSORT
- [ ] Maintain Tracking ID
- [ ] Test tracking với nhiều Swiftlet
- [ ] Xử lý object mất / xuất hiện lại

## D4. Entry / Exit Counting

- [ ] Xác định counting region / virtual line
- [ ] Xác định movement direction
- [ ] Entry counting
- [ ] Exit counting
- [ ] Generate timestamp
- [ ] Link result với Camera / Node
- [ ] Compare AI count với manual ground truth

## D5. Predator Detection

- [ ] Predator object detection
- [ ] Confidence threshold
- [ ] Generate anomaly event
- [ ] Bounding Box
- [ ] Evidence snapshot
- [ ] Timestamp
- [ ] Camera / Node ID

## D6. Audio / Anomaly Processing

- [ ] Xác định audio input
- [ ] Xác định loại anomaly hỗ trợ
- [ ] Sound equipment failure detection approach
- [ ] Audio anomaly processing prototype
- [ ] Generate Audio Anomaly Event

## D7. Backend Integration

- [ ] Chốt AI Event Contract với TV2
- [ ] Send Entry / Exit Count
- [ ] Send Predator Event
- [ ] Send Bounding Box
- [ ] Send Snapshot metadata
- [ ] Send Audio Anomaly Event
- [ ] Retry / error handling
- [ ] Test AI → Backend

## D8. AI Evaluation

- [ ] Precision / Recall
- [ ] mAP
- [ ] Counting accuracy
- [ ] Inference latency
- [ ] Edge resource usage
- [ ] Test low-light scenario nếu camera hỗ trợ
- [ ] Final model documentation

---

# E. INTEGRATION CHECKPOINTS

> Đây là phần quan trọng nhất.
> Không được xem module hoàn thành chỉ vì chạy riêng lẻ.

## INT-01 — IoT Telemetry

TV3 + TV2 + TV1

- [ ] ESP32 đọc sensor
- [ ] ESP32 → MQTT
- [ ] Backend nhận telemetry
- [ ] Backend lưu dữ liệu
- [ ] Backend realtime push
- [ ] Frontend hiển thị
- [ ] Verify end-to-end

Flow:

Sensor → ESP32 → MQTT → Backend → DB → Realtime → Frontend

---

## INT-02 — Environmental Control

TV1 + TV2 + TV3

- [ ] User bấm control
- [ ] Frontend → Backend
- [ ] Backend authorization
- [ ] Backend → MQTT
- [ ] ESP32 nhận command
- [ ] Actuator thực thi
- [ ] ESP32 publish state
- [ ] Backend sync state
- [ ] Frontend cập nhật

---

## INT-03 — Offline Resilience

TV2 + TV3 + TV1

- [ ] Ngắt Internet
- [ ] ESP32 phát hiện mất kết nối
- [ ] Local automatic control vẫn hoạt động
- [ ] Frontend thể hiện device offline/stale
- [ ] Internet trở lại
- [ ] ESP32 reconnect
- [ ] Backend đồng bộ trạng thái

---

## INT-04 — Bird Entry / Exit

TV4 + TV2 + TV1

- [ ] Camera → AI
- [ ] Detection
- [ ] Tracking
- [ ] Counting
- [ ] AI → Backend
- [ ] Backend lưu count
- [ ] Realtime → Frontend
- [ ] Dashboard hiển thị Entry / Exit

---

## INT-05 — Predator Alert

TV4 + TV2 + TV1 + TV3

- [ ] AI detect predator
- [ ] AI tạo event + snapshot
- [ ] Backend nhận event
- [ ] Backend tạo alert
- [ ] Frontend nhận realtime alert
- [ ] Mobile Push Notification
- [ ] Backend → MQTT alarm command
- [ ] ESP32 kích hoạt actuator nếu cấu hình
- [ ] Verify toàn bộ trong 3–5 giây

---

## INT-06 — Audio Anomaly

TV4 + TV2 + TV1

- [ ] Audio input
- [ ] AI/anomaly processing
- [ ] Generate event
- [ ] Backend nhận event
- [ ] Alert processing
- [ ] Frontend hiển thị

---

## INT-07 — Authentication & RBAC

TV1 + TV2

- [ ] Farm Owner login
- [ ] Technician login
- [ ] Administrator login
- [ ] Frontend route đúng role
- [ ] Backend authorization đúng role
- [ ] Unauthorized request bị từ chối

---

## INT-08 — Final System Flow

Cả nhóm

- [ ] Login
- [ ] Dashboard
- [ ] Environment realtime
- [ ] AUTO local control
- [ ] MANUAL remote control
- [ ] Device monitoring
- [ ] Entry / Exit monitoring
- [ ] Predator detection
- [ ] Audio anomaly
- [ ] Alert
- [ ] Push notification
- [ ] Analytics
- [ ] Offline demonstration

---

# F. DEFINITION OF DONE

Task chỉ được `[x]` khi:

1. Implementation hoàn thành.
2. Chạy/test được.
3. Code đã push GitHub.
4. Có review nếu ảnh hưởng interface chung.
5. Documentation/API/contract được cập nhật nếu cần.
6. Integration task phải được test với module liên quan.

Không được tick chỉ vì:
- đã tạo file;
- đã viết skeleton;
- mock chạy được nhưng requirement yêu cầu integration thật;
- code chạy trên máy cá nhân nhưng chưa push.

---

# G. OUT OF CURRENT SCOPE

Không đưa vào backlog chính nếu team chưa thay đổi SRS:

- Sales Staff
- Buyer
- Marketplace
- E-commerce
- Payment
- Shipping
- Ticket/SLA system
- Product/Inventory
- Harvest Marketplace
- Google OAuth
- Zalo notification
- OTA firmware
- Sales management