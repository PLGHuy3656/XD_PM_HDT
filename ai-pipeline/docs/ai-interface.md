# SwiftletCare AI ↔ Backend Interface Contract (Canonical V1)

Tài liệu đặc tả hợp đồng giao tiếp giữa Phân hệ Trí tuệ Nhân tạo (**AI Service**) và các dịch vụ trong hệ sinh thái **SwiftletCare** (**Management Service**, **Notification Service**, **Analytics/Persistence Service**, **Frontend**).
Mọi mô hình phát hiện đối tượng, thuật toán tracking có thể được nâng cấp hoặc thay thế mà **không** làm thay đổi hợp đồng này.

---

## 1. Nguyên tắc cốt lõi của Hợp đồng Chuẩn V1 (Canonical V1 Principles)

1. **Chuẩn hóa Thời gian**:
   - 100% trường thời gian sử dụng chuỗi định dạng **ISO-8601 UTC** kết thúc bằng ký tự `Z` (ví dụ: `2026-10-27T15:30:00.000Z`).
   - Tuyệt đối không sử dụng Unix epoch timestamp (`timestamp: 1728135000`) để tránh nhầm lẫn múi giờ và kiểu dữ liệu.
2. **Chuẩn hóa Bounding Box**:
   - Toạ độ hộp giới hạn luôn là pixel thực trên khung hình gốc:
     `{"x1": float, "y1": float, "x2": float, "y2": float}`.
   - Đi kèm thông tin kích thước khung hình trong kết quả detection: `frame: {"width": int, "height": int}`.
3. **Ngữ nghĩa Số đếm Chính trực (`CountUpdate`)**:
   - `entryCount`: Tổng số lượt chim bay vào tích lũy trong cửa sổ đếm hiện tại.
   - `exitCount`: Tổng số lượt chim bay ra tích lũy trong cửa sổ đếm hiện tại.
   - `netChange`: Cân bằng di chuyển ròng trong cửa sổ đếm (`entryCount - exitCount`), **không đại diện cho tổng đàn yến cố định hay số chim đang ngủ trong nhà**.
   - `deltaEntry` / `deltaExit`: Số lượt thay đổi tức thời so với lần gửi trước đó ($\ge 0$).
   - `windowStartedAt`: Thời điểm khởi đầu của cửa sổ đếm hiện tại.
4. **Sự kiện Thiên địch Tức thời (`AIEvent`)**:
   - Loại sự kiện: `eventType: "PREDATOR_DETECTED"` với `class: "rat" | "snake"`.
   - Snapshot luôn là URL chuẩn hoá: `/api/v1/ai/snapshots/<filename>.jpg`.
5. **Ràng buộc Chặt chẽ**:
   - Tất cả schema V1 đều bật `extra="forbid"` nhằm ngăn chặn việc truyền thừa hoặc sai lệch trường dữ liệu.

---

## 2. Kiến trúc Phân luồng Kênh Truyền tải & Quyền Sở hữu Dữ liệu (Traffic Segregation & Data Ownership)

### 2.1 Bảng Phân luồng Kênh Truyền tải theo Đặc thù Tải

| Đối tượng dữ liệu | Tần suất phát sinh | AI REST API V1 | AI WebSocket (`/ws/ai`) | RabbitMQ Exchange (`swiftletcare.ai`) | Dịch vụ tiêu thụ chính |
|---|---|---|---|---|---|
| **`DetectionResult`** | Cao (15–30 FPS) | `GET .../detections/latest` | `detection.updated` (có throttle `detection_max_hz`) | **KHÔNG PUBLISH (NO-OP)** | **Frontend Live View** (vẽ bounding box thời gian thực) |
| **`AIEvent`** (`PREDATOR_DETECTED`) | Khẩn cấp / Tức thời | `GET /api/v1/ai/events` | `ai.event` | **Routing key: `ai.predator.detected`** (Priority 0 - Cao nhất) | **Notification Queue / Notification Service** (cảnh báo & kích hoạt IoT) |
| **`CountUpdate`** | Định kỳ (`report_interval_s`) hoặc khi qua vạch | `GET .../counts/latest`, `/history` | `count.updated` | **Routing key: `ai.count.updated`** (Priority 10, `publish_counts: true`) | **Persistence / Analytics Service** (lưu lịch sử & thống kê đàn) |
| **`CameraRuntimeStatus`** | Khi đổi trạng thái runtime | `GET /api/v1/ai/cameras`, `.../status` | `camera.status` | Mặc định tắt (`publish_status: false`, key `ai.camera.status`) | **Management Service / UI Dashboard** |

### 2.2 Requirement Notes (Ghi chú Kiến trúc Tích hợp)

1. **Luồng Realtime UI (`DetectionResult`)**:
   - Dữ liệu bounding box từng khung hình tuyệt đối **không** đẩy vào RabbitMQ hay HTTP Backend để bảo vệ băng thông mạng và tránh nghẽn hàng đợi (**AI-NFR-006**).
   - Frontend kết nối trực tiếp tới AI WebSocket (`WS /ws/ai?cameraId=CAM-01`) hoặc gọi REST API khi cần hiển thị Live View.
2. **Luồng Cảnh báo Khẩn cấp (`AIEvent` → Notification Queue)**:
   - **Notification Service** chỉ cần bind queue của mình vào exchange `swiftletcare.ai` với routing key duy nhất **`ai.predator.detected`**.
   - Nhờ đó, Notification Queue chỉ nhận đúng các sự kiện phát hiện chuột/rắn thực sự, không bị lẫn các bản tin cập nhật số đếm định kỳ.
3. **Luồng Lưu trữ & Phân tích (`CountUpdate` → Persistence/Analytics)**:
   - Được tách sang routing key **`ai.count.updated`** (có thể bật/tắt độc lập qua `AI_RABBITMQ_PUBLISH_COUNTS=true|false`).
4. **Quyền sở hữu Camera Metadata (`cameraId` ↔ `farmId`, `zoneId`)**:
   - **Management Service** là nguồn chân lý duy nhất (*Single Source of Truth*) quản lý thông tin định danh và ánh xạ nghiệp vụ của camera (`cameraId` thuộc `farmId` nào, `zoneId` nào, tên hiển thị, RTSP URL).
   - **AI Service** chỉ sở hữu **Runtime State** (`status`, `fps`, `processedFrames`, bộ đếm phiên hiện tại, snapshot sự kiện) gắn với khóa `cameraId`. Trường `farmId` và `zoneId` trong các gói tin Canonical V1 mặc định là `null` (trừ khi Management Service chủ động truyền xuống để pass-through).

---

## 3. Giao thức Đẩy Sự kiện: RabbitMQ Producer (`RabbitMQRuntimeSink`) & HTTP Fallback (`HttpBackendSink`)

AI Service xuất dữ liệu qua `CompositeRuntimeSink` tới:
- **Kênh chính (`RabbitMQRuntimeSink`)**: Đẩy message bền vững (`delivery_mode=2`, `content_type="application/json"`) lên Topic Exchange `swiftletcare.ai` qua hàng đợi ưu tiên không chặn luồng (`PriorityQueue(200)`).
- **Kênh dự phòng (`HttpBackendSink`)**: Đẩy HTTP POST (`POST /api/ai/events`, `/api/ai/counts`, `/api/ai/status`) khi bật `AI_BACKEND_ENABLED=true`.

### 3.1 Cảnh báo Thiên địch (Routing key: `ai.predator.detected` | Fallback: `POST /api/ai/events`)
- **Tần suất**: Phát ngay lập tức khi phát hiện thiên địch đủ $N$ khung hình liên tiếp. Độ ưu tiên cao nhất (Priority 0).
- **Payload Schema (`AIEvent`)**:
```json
{
  "eventId": "evt_ai_a1b2c3d4e5f6",
  "eventType": "PREDATOR_DETECTED",
  "cameraId": "CAM-01",
  "farmId": null,
  "zoneId": null,
  "frameId": 328,
  "detectedAt": "2026-10-27T15:30:00.123Z",
  "class": "snake",
  "confidence": 0.925,
  "bbox": {
    "x1": 250.0,
    "y1": 160.0,
    "x2": 340.0,
    "y2": 230.0
  },
  "snapshot": "/api/v1/ai/snapshots/CAM-01_snake_1761510000_200.jpg"
}
```

### 3.2 Cập nhật Số đếm Ra/Vào (Routing key: `ai.count.updated` | Fallback: `POST /api/ai/counts`)
- **Tần suất**: Định kỳ theo `report_interval_s` (mặc định 5s), khi có chim qua vạch, hoặc khi kết thúc cửa sổ đếm.
- **Payload Schema (`CountUpdate`)**:
```json
{
  "cameraId": "CAM-01",
  "farmId": null,
  "zoneId": null,
  "frameId": 350,
  "recordedAt": "2026-10-27T15:30:05.000Z",
  "windowStartedAt": "2026-10-27T15:00:00.000Z",
  "entryCount": 125,
  "exitCount": 98,
  "netChange": 27,
  "deltaEntry": 3,
  "deltaExit": 1
}
```

### 3.3 Trạng thái Hoạt động Camera (Routing key: `ai.camera.status` khi bật | REST/WS)
- **Tần suất**: Khi camera đổi trạng thái (`STARTING`, `ONLINE`, `DEGRADED`, `OFFLINE`, `ERROR`).
- **Payload Schema (`CameraRuntimeStatus`)**:
```json
{
  "cameraId": "CAM-01",
  "farmId": null,
  "zoneId": null,
  "status": "ONLINE",
  "sourceConnected": true,
  "inferenceStatus": "RUNNING",
  "fps": 29.5,
  "width": 1280,
  "height": 720,
  "modelVersion": "best",
  "trackerType": "bytetrack",
  "processedFrames": 1500,
  "lastFrameAt": "2026-10-27T15:30:05.000Z",
  "updatedAt": "2026-10-27T15:30:05.100Z",
  "errorCode": null,
  "errorMessage": null
}
```

---

## 4. Danh mục REST API V1 do AI Service Cung cấp

AI Service cung cấp giao diện REST chuẩn để Management Service và Frontend truy vấn / điều khiển trực tiếp:

| Phương thức | Đường dẫn | Tham số / Body | Kết quả trả về |
|---|---|---|---|
| `GET` | `/health` | Không | `{"service": "ai-service", "status": "ok"}` |
| `GET` | `/api/v1/ai/cameras` | Không | `List[CameraRuntimeStatus]` |
| `GET` | `/api/v1/ai/cameras/{cameraId}/status` | `cameraId` | `CameraRuntimeStatus` (404 nếu chưa đăng ký) |
| `POST` | `/api/v1/ai/cameras/{cameraId}/start` | `cameraId`, Body `CameraStartRequest` (tùy chọn) | `CameraRuntimeStatus` (khởi chạy camera đã có hoặc đăng ký động từ `source`) |
| `POST` | `/api/v1/ai/cameras/{cameraId}/stop` | `cameraId` | `CameraRuntimeStatus` (dừng xử lý luồng) |
| `GET` | `/api/v1/ai/cameras/{cameraId}/detections/latest` | `cameraId` | `DetectionResult` mới nhất |
| `GET` | `/api/v1/ai/cameras/{cameraId}/counts/latest` | `cameraId` | `CountUpdate` mới nhất |
| `GET` | `/api/v1/ai/cameras/{cameraId}/counts` | `cameraId`, `limit=100` | `List[CountUpdate]` bền vững từ PostgreSQL (`ai_db`) |
| `POST` | `/api/v1/ai/cameras/{cameraId}/counts/reset` | `cameraId` | `CountUpdate` sau khi reset về 0 |
| `GET` | `/api/v1/ai/cameras/{cameraId}/counts/history` | `limit=20` | `List[CountUpdate]` (mới nhất trước) |
| `POST` | `/api/v1/ai/analyze` | `cameraId=CAM-01`, `annotate=false`, file ảnh | `DetectionResult` (header `X-Snapshot-Url` nếu `annotate=true`) |
| `GET` | `/api/v1/ai/events` | `cameraId=`, `limit=100` | `List[AIEvent]` |
| `GET` | `/api/v1/ai/events/{eventId}` | `eventId` | `AIEvent` |
| `GET` | `/api/v1/ai/snapshots/{filename}` | `filename` | File ảnh JPEG (được bảo vệ path traversal) |

### Điều khiển Khởi chạy Camera Động từ Management Service (`POST /api/v1/ai/cameras/{cameraId}/start`)
Management Service có thể gọi:
- **Không truyền body**: Khởi chạy camera `cameraId` đã cấu hình sẵn trong `configs/cameras.yaml`.
- **Truyền JSON body tùy chọn (`CameraStartRequest`)**: Khởi chạy hoặc cập nhật nguồn phát động cho bất kỳ `cameraId` nào mà không cần sửa file cấu hình tĩnh:
```json
{
  "source": "rtsp://camera-node-01:8554/entrance",
  "sourceType": "rtsp",
  "countingLine": {
    "start": [0.10, 0.55],
    "end": [0.90, 0.55]
  },
  "insideSide": "positive",
  "fps": 0.0,
  "maxFrames": 0
}
```

---

## 5. Kênh Truyền thông Thời gian thực: WebSocket V1 (`/ws/ai`)

- **Đường dẫn**: `WS /ws/ai` (hoặc lọc theo camera: `WS /ws/ai?cameraId=CAM-01`).
- **Cấu trúc gói tin bao đóng (Envelope)**:
```json
{
  "type": "detection.updated" | "count.updated" | "ai.event" | "camera.status",
  "cameraId": "CAM-01",
  "data": { ...canonical V1 domain object... }
}
```
- **Cơ chế Tiết kiệm Băng thông (AI-NFR-006)**:
  - Tần suất phát gói `detection.updated` có thể được giới hạn thông qua `ws.detection_max_hz` trong cấu hình (ví dụ: tối đa 5 Hz).
  - Các gói dữ liệu mang tính hành động hoặc cảnh báo (`count.updated`, `ai.event`, `camera.status`) luôn được gửi ngay lập tức mà không bị điều tiết.

---

## 6. Bảng Đối chiếu Hợp đồng Cũ (Draft v0.1) vs Hợp đồng Chuẩn V1 (Canonical V1)

| Tiêu chí | Bản phác thảo cũ (Draft v0.1) | Hợp đồng Chuẩn V1 (Canonical V1) | Lý do chuẩn hoá |
|---|---|---|---|
| **Định dạng thời gian** | Số nguyên Unix epoch giây: `timestamp: 1728135000` | Chuỗi ISO-8601 UTC: `"recordedAt": "2026-10-27T15:30:00.000Z"` | Đồng nhất múi giờ quốc tế, dễ đọc và debug |
| **Định dạng Bounding Box** | Mảng số 4 phần tử: `bbox: [x1, y1, x2, y2]` | Đối tượng có tên trường rõ ràng: `bbox: {"x1": 10.0, "y1": 20.0, ...}` | Tránh nhầm lẫn thứ tự `xywh` vs `xyxy` |
| **Kích thước khung hình** | Không đi kèm trong payload | Đi kèm bắt buộc: `frame: {"width": 1280, "height": 720}` | Frontend có đủ dữ liệu để vẽ tỷ lệ hộp nhận diện |
| **Ngữ nghĩa `netChange`** | Không rõ ràng, có nguy cơ hiểu nhầm là số chim trong nhà | Rõ ràng là cân bằng di chuyển trong cửa sổ đếm hiện tại | Ngăn chặn sai lệch báo cáo đàn yến |
| **Kênh đẩy sự kiện** | Chỉ đẩy HTTP / MQTT thô | RabbitMQ Topic Exchange `swiftletcare.ai` tách routing key `ai.predator.detected` và `ai.count.updated` | Tách biệt tải Notification Queue và Persistence/Analytics |
| **Quyền sở hữu Metadata** | Gán cứng `farmId`, `zoneId` tại AI | Management Service sở hữu `cameraId` ↔ `farmId`; AI giữ Runtime State (`farmId: null` mặc định) | Đúng chuẩn Single Source of Truth giữa các Microservices |
| **Khởi chạy camera** | Chỉ đọc file tĩnh `cameras.yaml` | Hỗ trợ thêm dynamic payload qua `POST /api/v1/ai/cameras/{cameraId}/start` | Management Service điều phối camera động dễ dàng |
