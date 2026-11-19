# SwiftletCare AI Service (`services/ai-service`)

Dịch vụ AI chuẩn hóa Canonical V1 cho hệ sinh thái **SwiftletCare**, kết hợp thư viện lõi thị giác máy tính (`ai-pipeline/src/swiftletcare_ai`) với hạ tầng Microservice đầy đủ (**FastAPI REST API V1**, **WebSocket V1**, **PostgreSQL `ai_db`**, **Redis Runtime/Cache**, **RabbitMQ Topic Exchange**, và **HTTP Backend Sink**).

## 1. Kiến trúc Tổng thể

```text
AIRuntimeManager (LockedDetector + PruningSnapshotStore)
  └── CameraPipeline (mỗi cameraId một luồng xử lý độc lập)
        ├── FrameSource       (swiftletcare_ai.video_source + Auto-reconnect exponential backoff)
        ├── FrameCleaner      (swiftletcare_ai.frame_clean — lọc ảnh đen/hỏng, cân bằng sáng gamma)
        ├── YoloDetector      (swiftletcare_ai.detector — YOLO26 models/best.pt)
        ├── DetectionFilter   (swiftletcare_ai.postfilter — lọc nhiễu diện tích & cross-class IOU)
        ├── Tracker           (swiftletcare_ai.tracker — ByteTrackTracker / CentroidTracker)
        ├── LineCounter       (swiftletcare_ai.counter — đếm chim ra/vào qua vạch ảo + cửa sổ thời gian)
        ├── PredatorMonitor   (swiftletcare_ai.predator — xác nhận chuột/rắn qua N-frame + cooldown)
        └── SnapshotStore     (swiftletcare_ai.snapshot — lưu bằng chứng hình ảnh JPEG)
              │
              ▼
        CompositeRuntimeSink
              ├── InMemoryAIRuntimeStateStore
              │     ├── Redis Runtime & Cache (`ai:runtime:{cameraId}`, `ai:latest:{cameraId}`)
              │     ├── PostgreSQL Persistence (`ai_db.ai_count_updates`, `ai_db.ai_events`)
              │     └── In-Memory Ring Buffer (Count history, recent events, live detections)
              ├── WebSocketRuntimeSink          ──► AIWebSocketManager (/ws/ai, hỗ trợ throttle detection_max_hz)
              ├── DomainEventPublisherRuntimeSink──► RabbitMQ Async Producer (`swiftletcare.events` -> `ai.predator.detected`)
              ├── RabbitMQRuntimeSink           ──► RabbitMQ Topic Exchange (`swiftletcare.ai` -> `ai.predator.detected`, `ai.count.updated`)
              └── HttpBackendSink               ──► HTTP POST Fallback (/api/ai/events, /counts, /status)
```

## 2. Danh mục REST API V1 & WebSocket V1

- `GET /health` -> `{"service": "ai-service", "status": "ok"}`
- `POST /api/v1/ai/analyze` -> Phân tích một ảnh tĩnh đơn lẻ (multipart/base64/raw bytes; hỗ trợ `annotate=true` trả về header `X-Snapshot-Url`)
- `GET /api/v1/ai/cameras` -> `List[CameraRuntimeStatus]`
- `GET /api/v1/ai/cameras/{cameraId}/status` -> `CameraRuntimeStatus`
- `POST /api/v1/ai/cameras/{cameraId}/start` -> Khởi chạy camera đã đăng ký hoặc truyền JSON body (`CameraStartRequest`) để khởi chạy động từ Management Service
- `POST /api/v1/ai/cameras/{cameraId}/stop` -> Dừng luồng xử lý camera và chuyển về `OFFLINE`
- `GET /api/v1/ai/cameras/{cameraId}/detections/latest` -> `DetectionResult` mới nhất
- `GET /api/v1/ai/cameras/{cameraId}/counts/latest` -> `CountUpdate` mới nhất
- `GET /api/v1/ai/cameras/{cameraId}/counts` -> Truy vấn lịch sử `CountUpdate` bền vững từ PostgreSQL
- `GET /api/v1/ai/cameras/{cameraId}/counts/history` -> Truy vấn lịch sử `CountUpdate` theo cửa sổ đếm (`limit=20`)
- `POST /api/v1/ai/cameras/{cameraId}/counts/reset` -> Đặt lại bộ đếm vào/ra và cửa sổ đếm về `0`
- `GET /api/v1/ai/events?cameraId=&farmId=&limit=` -> `List[AIEvent]`
- `GET /api/v1/ai/events/{eventId}` -> `AIEvent`
- `GET /api/v1/ai/snapshots/{filename}` -> Phục vụ ảnh chụp bằng chứng JPEG (chống path traversal)
- `WS /ws/ai?cameraId=` -> Kênh WebSocket V1 (`detection.updated`, `count.updated`, `ai.event`, `camera.status`)

## 3. Hướng dẫn Chạy & Kiểm thử

```bash
# 1. Chạy bộ kiểm thử tự động của AI Service
cd services/ai-service
pytest -q

# 2. Chạy bộ kiểm thử lõi thuật toán thị giác máy tính
cd ../../ai-pipeline
pytest -q

# 3. Chạy thử nghiệm E2E tích hợp (Synthetic + Real Model YOLO26)
python services/ai-service/demo/run_e2e_demo.py --mode both

# 4. Chạy kịch bản đo kiểm nghiệm thu (NFR Latency & Counting Accuracy)
python services/ai-service/eval/measure_latency.py
python services/ai-service/eval/evaluate_counting.py
```
