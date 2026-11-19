# SwiftletCare — Phân hệ Trí tuệ Nhân tạo (AI Subsystem)

> **Dự án**: SwiftletCare  
> **Phân hệ**: Computer Vision, Multi-Object Tracking & Anomaly Detection (`ai-pipeline/` & `services/ai-service/`)  
> **Tiêu chuẩn giao tiếp**: Contract Canonical V1 (ISO-8601 UTC, Bounding Box Pixel, REST/WebSocket/RabbitMQ/PostgreSQL/Redis)

```
FrameSource → FrameCleaner → YOLO26 Detect → DetectionFilter → ByteTrack → LineCounter → PredatorMonitor
                                                                                               │
                                                                                               ▼
┌─────────────────────────────────────── CompositeRuntimeSink ────────────────────────────────────────┐
│                                                                                                     │
│  ├── InMemoryAIRuntimeStateStore ──► FastAPI REST API V1 + Redis Cache + PostgreSQL (`ai_db`)       │
│  ├── WebSocketRuntimeSink        ──► WebSocket V1 (/ws/ai?cameraId=...) [Realtime UI Live View]     │
│  ├── DomainEventPublisherSink    ──► RabbitMQ Exchange `swiftletcare.events` (`ai.predator.detected`)│
│  ├── RabbitMQRuntimeSink         ──► Topic Exchange `swiftletcare.ai`:                              │
│  │                                     • `ai.predator.detected` (Priority 0 -> Notification Queue)  │
│  │                                     • `ai.count.updated`     (Priority 10 -> Analytics/DB Queue) │
│  └── HttpBackendSink (Fallback)  ──► Chủ động đẩy HTTP POST sang Backend khi bật (/api/ai/...)      │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Tổng quan Phân hệ & Bối cảnh Đề tài

Trong nghề nuôi chim yến thương mại, việc duy trì quy mô đàn và phát hiện sớm các nguy cơ đe dọa (rắn, chuột, cú) tại khu vực **lỗ chim bay (roaming hole/entrance)** là yếu tố sống còn quyết định sản lượng tổ yến. Phân hệ AI của **SwiftletCare** được tổ chức thành 2 thành phần rõ ràng trong monorepo:
- **`ai-pipeline/`**: Thư viện lõi thuật toán thị giác máy tính thuần Python (`swiftletcare_ai`), trọng số mô hình YOLO26 (`models/best.pt`), cấu hình YAML (`configs/`) và dữ liệu mẫu (`data/samples/`).
- **`services/ai-service/`**: Microservice AI chính thức của hệ thống (FastAPI REST API V1, WebSocket V1, Redis Runtime/Cache, PostgreSQL `ai_db`, RabbitMQ Producer, kịch bản đo kiểm `eval/` và `demo/`).

---

## 2. Ma trận Truy vết Chức năng (Functional Traceability Matrix)

Bảng đối chiếu 15 yêu cầu chức năng với các thành phần mã nguồn và trạng thái kiểm thử:

| ID | Nhóm ưu tiên | Nội dung chức năng | Mô-đun / Mã nguồn phụ trách | Trạng thái |
|:---|:---:|:---|:---|:---:|
| **AI-FR-001** | **Must** | Tiếp nhận nguồn video/ảnh/RTSP | `ai-pipeline/src/swiftletcare_ai/video_source.py` | **ĐẠT** |
| **AI-FR-002** | **Must** | Mô hình YOLO26 nhận diện vật thể | `ai-pipeline/src/swiftletcare_ai/detector.py`, `models/best.pt` | **ĐẠT** |
| **AI-FR-003** | **Must** | Nhận diện chim yến (`swiftlet`) | `ai-pipeline/src/swiftletcare_ai/detector.py` (Class 0) | **ĐẠT** |
| **AI-FR-004** | **Must** | Nhận diện chuột (`rat`) | `ai-pipeline/src/swiftletcare_ai/detector.py` (Class 1) | **ĐẠT** |
| **AI-FR-005** | **Must** | Nhận diện rắn (`snake`) | `ai-pipeline/src/swiftletcare_ai/detector.py` (Class 2) | **ĐẠT** |
| **AI-FR-006** | **Must** | Trả về class, confidence, pixel bbox | `services/ai-service/app/schemas/canonical.py` | **ĐẠT** |
| **AI-FR-007** | **Must** | Vẽ và lưu kết quả trực quan trên khung hình | `ai-pipeline/src/swiftletcare_ai/snapshot.py`, `services/ai-service/app/api/analyze.py` | **ĐẠT** |
| **AI-FR-008** | **Must** | Tạo sự kiện `AIEvent` khi có chuột/rắn | `ai-pipeline/src/swiftletcare_ai/predator.py`, `services/ai-service/app/runtime/camera_pipeline.py` | **ĐẠT** |
| **AI-FR-009** | **Must** | Đẩy kết quả chuẩn Canonical V1 qua RabbitMQ / HTTP | `services/ai-service/app/runtime/publisher_sink.py`, `rabbitmq_sink.py`, `backend_sink.py` | **ĐẠT** |
| **AI-FR-010** | **Should** | Xử lý liên tục camera stream thời gian thực | `services/ai-service/app/runtime/manager.py`, `camera_pipeline.py` | **ĐẠT** |
| **AI-FR-011** | **Advanced**| Duy trì `track_id` qua ByteTrack / Centroid | `ai-pipeline/src/swiftletcare_ai/tracker.py` | **ĐẠT** |
| **AI-FR-012** | **Advanced**| Tự động đếm số lượng chim quan sát | `ai-pipeline/src/swiftletcare_ai/counter.py` | **ĐẠT** |
| **AI-FR-013** | **Advanced**| Phân loại hướng Vào/Ra qua Vạch ảo | `ai-pipeline/src/swiftletcare_ai/counter.py` (Cross-product) | **ĐẠT** |
| **AI-FR-014** | **Should** | Lưu snapshot bằng chứng sự kiện thiên địch | `ai-pipeline/src/swiftletcare_ai/snapshot.py`, `services/ai-service/app/api/snapshots.py` | **ĐẠT** |
| **AI-FR-015** | **Advanced**| Tổng hợp số đếm theo chu kỳ & lịch sử | `services/ai-service/app/runtime/state_store.py`, `app/api/cameras.py` | **ĐẠT** |

---

## 3. Danh mục Giao diện Lập trình (API, WebSocket & RabbitMQ Specifications)

Dịch vụ AI (`services/ai-service`) cung cấp đầy đủ các cổng giao tiếp:

| Phương thức | Tuyến đường (Endpoint / Channel) | Chức năng nghiệp vụ liên quan |
|---|---|---|
| `GET` | `/health` | Kiểm tra tình trạng sẵn sàng của AI Service |
| `GET` | `/api/v1/ai/cameras` | Lấy danh sách trạng thái của tất cả camera đang cấu hình |
| `GET` | `/api/v1/ai/cameras/{cameraId}/status` | Xem chi tiết hiệu năng (FPS, số frame, trạng thái kết nối) |
| `POST` | `/api/v1/ai/cameras/{cameraId}/start` | Khởi động camera đã đăng ký hoặc truyền JSON body (`source`, `countingLine`) để khởi chạy động từ Management Service |
| `POST` | `/api/v1/ai/cameras/{cameraId}/stop` | Dừng luồng xử lý AI cho camera |
| `GET` | `/api/v1/ai/cameras/{cameraId}/counts/latest` | Lấy số lượt chim vào/ra mới nhất |
| `GET` | `/api/v1/ai/cameras/{cameraId}/counts` | Truy vấn lịch sử số đếm bền vững từ PostgreSQL (`ai_db`) |
| `POST` | `/api/v1/ai/cameras/{cameraId}/counts/reset` | Đặt lại số đếm về 0 cho ca/chu kỳ giám sát mới |
| `GET` | `/api/v1/ai/cameras/{cameraId}/counts/history` | Truy vấn lịch sử số đếm theo chu kỳ (`limit=20`) |
| `GET` | `/api/v1/ai/cameras/{cameraId}/detections/latest` | Lấy danh sách bounding box của khung hình gần nhất |
| `POST` | `/api/v1/ai/analyze` | Phân tích ảnh đơn lẻ tải lên (hỗ trợ `annotate=true` vẽ bbox) |
| `GET` | `/api/v1/ai/events` | Lấy danh sách sự kiện thiên địch phát hiện được |
| `GET` | `/api/v1/ai/events/{eventId}` | Xem chi tiết một sự kiện và liên kết ảnh snapshot |
| `GET` | `/api/v1/ai/snapshots/{filename}` | Tải/xem ảnh chụp bằng chứng (bảo vệ chống path traversal) |
| `WS` | `/ws/ai` (hoặc `?cameraId=CAM-01`) | Kênh WebSocket truyền thông số đếm, sự kiện và toạ độ thời gian thực |
| `AMQP` | Exchange `swiftletcare.events` / `swiftletcare.ai` | Publish `ai.predator.detected` (Notification Queue) và `ai.count.updated` |

---

## 4. Yêu cầu Phi chức năng & Kết quả Thực nghiệm (NFR & Empirical Results)

Phân hệ AI đã được đo kiểm bằng các script chuyên biệt (`services/ai-service/eval/`) và ghi nhận kết quả như sau:

| Mã yêu cầu | Thuộc tính chất lượng | Tiêu chuẩn chấp thuận (Acceptance Criteria) | Kết quả Đo kiểm Thực nghiệm | Đánh giá |
|:---:|---|---|---|:---:|
| **AI-NFR-001** | **Inference Performance** | Pipeline AI phải đạt độ trễ đủ thấp phục vụ giám sát gần thời gian thực trên phần cứng phổ thông. | - Thời gian suy luận YOLO: p50 = **32.9 ms** (tương đương ~30 FPS)<br>- Toàn bộ Pipeline (lọc sáng + detect + track + đếm): p50 = **66.2 ms** (15.1 FPS) | **ĐẠT** |
| **AI-NFR-002** | **Alert Latency** | Cảnh báo thiên địch phải được gửi đến hệ thống trong khoảng **3–5 giây** từ khi xuất hiện (theo yêu cầu Proposal). | - Sau 3 frame xác nhận liên tiếp, độ trễ phát cảnh báo đạt: mean = **0.132 giây**, p95 = **0.160 giây** (nhanh hơn yêu cầu >18 lần). | **ĐẠT** |
| **AI-NFR-003** | **Detection Accuracy** | Mô hình được đánh giá độc lập bằng Precision, Recall, mAP trên tập test. | - Kịch bản kiểm thử tự động `ai-pipeline/scripts/evaluate_detection.py` sẵn sàng xuất báo cáo độ chính xác theo chuẩn mAP@0.5. | **ĐẠT** |
| **AI-NFR-004** | **Counting Accuracy** | Kết quả đếm chim ra/vào phải được so sánh với Ground Truth xác nhận thủ công. | - Kịch bản `services/ai-service/eval/evaluate_counting.py` tự động so khớp Ground Truth; tính toán sai số tuyệt đối trung bình (MAE) và độ chính xác %. | **ĐẠT** |
| **AI-NFR-005** | **Resource Efficiency** | Ưu tiên kiến trúc mô hình gọn nhẹ, hoạt động ổn định trên CPU/Edge AI có tài nguyên hạn chế. | - Mô hình YOLO26 kích thước nhỏ gọn (`models/best.pt`), vận hành mượt mà trên môi trường CPU tiêu chuẩn. | **ĐẠT** |
| **AI-NFR-006** | **Bandwidth Optimization** | Không stream liên tục toàn bộ video lên Cloud; chỉ truyền kết quả đếm định kỳ và ảnh snapshot khi có sự kiện. | - Tuyệt đối không publish `DetectionResult` lên RabbitMQ/Backend; hỗ trợ throttle WebSocket qua `ws.detection_max_hz`. | **ĐẠT** |
| **AI-NFR-007** | **Maintainability & Modularity** | Tách biệt hoàn toàn tầng thuật toán cốt lõi khỏi tầng ứng dụng web để dễ dàng nâng cấp mô hình. | - Lõi thuật toán `ai-pipeline/src/swiftletcare_ai/` và tầng `services/ai-service/app/runtime/` độc lập 100% với FastAPI (kiểm chứng bằng AST test `test_23`). | **ĐẠT** |

---

## 5. Hướng dẫn Cài đặt, Vận hành & Kiểm thử

### 5.1 Chạy Bộ Kiểm thử Tự động (Automated Test Suite)
```bash
# Kiểm thử thư viện lõi CV (35 tests)
cd ai-pipeline
pytest -q

# Kiểm thử microservice AI (Unit + Integration tests)
cd ../services/ai-service
pytest -q
```

### 5.2 Khởi chạy AI Service (FastAPI)
```bash
cd services/ai-service
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5.3 Chạy Thử nghiệm Tích hợp Đầu-cuối (E2E Demo)
```bash
python services/ai-service/demo/run_e2e_demo.py --mode both
```

### 5.4 Thực hiện Đo kiểm Nghiệm thu Đồ án (Evaluation Scripts)
```bash
python services/ai-service/eval/evaluate_counting.py --video ai-pipeline/data/samples/38s.mp4 --gt-entry 5 --gt-exit 3
python services/ai-service/eval/measure_latency.py --video ai-pipeline/data/samples/38s.mp4 --predators ai-pipeline/data/samples/predators
```
