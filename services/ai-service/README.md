# SwiftletCare AI Service — Local Reference Prototype (CP5.2 + CP5.3)

> **OWNERSHIP & GIT SAFETY NOTICE**
> The AI Pipeline (`ai-pipeline/`) and AI Service bounded context belong to **TV2**.
> This `services/ai-service/` directory is a **LOCAL REFERENCE PROTOTYPE** built for contract and integration validation.
> **DO NOT COMMIT. DO NOT PUSH.**

## Overview

CP5.2 and CP5.3 implement the **AI Runtime Adapter, Canonical V1 Domain Model, FastAPI REST API V1, and WebSocket V1 (`/ws/ai`)** around TV2's existing `swiftletcare_ai` computer-vision pipeline:

```text
AIRuntimeManager
  └── CameraPipeline (one per cameraId)
        ├── FrameSource       (swiftletcare_ai.video_source)
        ├── YoloDetector      (swiftletcare_ai.detector — encapsulates Ultralytics 640x640 letterbox + normalize)
        ├── Tracker           (swiftletcare_ai.tracker — ByteTrackTracker / CentroidTracker)
        ├── LineCounter       (swiftletcare_ai.counter)
        ├── PredatorMonitor   (swiftletcare_ai.predator)
        └── SnapshotStore     (swiftletcare_ai.snapshot)
              │
              ▼
        RuntimeEventSink      (CompositeRuntimeSink)
              ├── InMemoryAIRuntimeStateStore   ──► FastAPI REST API V1 (/health, /api/v1/ai/...)
              └── WebSocketRuntimeSink          ──► AIWebSocketManager  (/ws/ai)
```

## REST API V1 & WebSocket V1 Endpoints

- `GET /health` -> `{"service": "ai-service", "status": "ok"}`
- `GET /api/v1/ai/cameras` -> `List[CameraRuntimeStatus]`
- `GET /api/v1/ai/cameras/{cameraId}/status` -> `CameraRuntimeStatus`
- `GET /api/v1/ai/cameras/{cameraId}/detections/latest` -> `DetectionResult`
- `GET /api/v1/ai/cameras/{cameraId}/counts/latest` -> `CountUpdate`
- `GET /api/v1/ai/events?cameraId=&limit=` -> `List[AIEvent]`
- `GET /api/v1/ai/events/{eventId}` -> `AIEvent`
- `GET /api/v1/ai/snapshots/{filename}` -> JPEG file response (path-traversal hardened)
- `WS /ws/ai?cameraId=` -> Canonical V1 envelope (`detection.updated`, `count.updated`, `ai.event`, `camera.status`)

## Canonical V1 Contract Decisions

1. **Single ISO-8601 UTC Timestamps (`...Z`):**
   - `DetectionResult.capturedAt`
   - `CountUpdate.recordedAt`, `CountUpdate.windowStartedAt`
   - `AIEvent.detectedAt`
   - `CameraRuntimeStatus.updatedAt`, `CameraRuntimeStatus.lastFrameAt`
   - Duplicate Unix epoch `timestamp` fields are strictly forbidden.
2. **Pixel Bounding Boxes + Frame Dimensions:**
   - `BoundingBox`: `{"x1": float, "y1": float, "x2": float, "y2": float}` in source frame pixels.
   - `DetectionResult.frame`: `{"width": int, "height": int}`.
   - `bboxNormalized` and CSS percentages are excluded from backend V1 contracts.
3. **Honest Counting Semantics (`CountUpdate`):**
   - Exposes `entryCount`, `exitCount`, `netChange = entryCount - exitCount`, `deltaEntry >= 0`, `deltaExit >= 0`, and `windowStartedAt`.
   - `netChange` represents movement balance within the current counting window, **not** absolute house occupancy or total bird population (`occupancy`, `currentBirdCount`, `totalBirdPopulation` are forbidden).
4. **Immediate AI Events (`AIEvent`):**
   - V1 supports `eventType = "PREDATOR_DETECTED"` (`class: "rat" | "snake"`).
   - Does not emit `FLOCK_ANOMALY`, `AUDIO`, or per-bird `ENTRY`/`EXIT` event records.
5. **Preprocessing Boundary:**
   - No standalone `preprocessing.py` exists; letterbox resizing (`640x640`), BGR-to-RGB conversion, and `[0, 1]` normalization are performed internally by Ultralytics `YOLO.predict()` inside `YoloDetector.detect()`.
