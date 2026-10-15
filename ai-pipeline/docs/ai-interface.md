# AI ↔ Backend Interface Contract (Draft v0.1)

Thống nhất giữa phân hệ AI và Backend. Model có thể retrain/thay thế **không** làm đổi contract này (AI Model Interface).
`timestamp` = epoch seconds. `bbox` = `[x1, y1, x2, y2]` pixel. `cameraId` duy nhất cho mỗi camera/node.

| kind        | HTTP (mặc định)        | MQTT topic                          | Khi nào gửi |
|-------------|------------------------|-------------------------------------|-------------|
| counts      | POST /api/ai/counts    | swiftletcare/ai/{cameraId}/counts   | mỗi `report_interval_s` (mặc định 5 s) + khi kết thúc |
| events      | POST /api/ai/events    | swiftletcare/ai/{cameraId}/events   | khi phát hiện thiên địch / biến động đàn |
| detections  | POST /api/ai/detections| swiftletcare/ai/{cameraId}/detections | TẮT mặc định (tiết kiệm băng thông, AI-NFR-006) |

## counts
```json
{"cameraId":"CAM-01","timestamp":1728135000,"entryCount":125,"exitCount":98,"netChange":27}
```
`entryCount/exitCount` là **tích luỹ** từ lúc pipeline khởi động; Backend tính delta theo cửa sổ nếu cần.

## events
```json
{"cameraId":"CAM-01","eventType":"PREDATOR_DETECTED","class":"snake","confidence":0.91,
 "timestamp":1728135000,"snapshot":"snapshot_url","bbox":[250,160,340,230]}
```
`eventType`: `PREDATOR_DETECTED` | `FLOCK_ANOMALY`. Snapshot có bounding box (bằng chứng, AI-FR-014).
Luồng thiên địch: AI → Backend → MQTT trigger → IoT node (còi/đèn). **AI không điều khiển IoT trực tiếp.**

## detections (tuỳ chọn)
```json
{"cameraId":"CAM-01","timestamp":1728135000,
 "detections":[{"class":"swiftlet","confidence":0.94,"trackId":21,"bbox":[120,80,165,140]}]}
```

## Câu hỏi mở cần chốt với Backend
- Kênh chính: HTTP hay MQTT? `snapshot` là URL (MinIO) hay đường dẫn local?
- Đồng bộ thời gian AI node ↔ Backend (NTP) — Assumption 6.1.