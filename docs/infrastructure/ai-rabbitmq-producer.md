# AI Service — RabbitMQ Domain Event Producer Architecture (CP7.3)

> **TV2 SERVICE REFERENCE IMPLEMENTATION • LOCAL INTEGRATION VALIDATION ONLY • DO NOT PUSH FROM TV4**

---

## 1. Architectural Role & Boundary Separation

The SwiftletCare AI Service processes video streams, runs computer vision inference (YOLO detection, ByteTrack tracking, line crossing counting, and predator monitoring), and publishes domain events to RabbitMQ:

```text
┌───────────────────────────┐
│ Camera / RTSP Video Stream│
└─────────────┬─────────────┘
              │ Video Frames
              ▼
┌────────────────────────────────────────────────────────┐
│                      AI Pipeline                       │
│                                                        │
│  YOLO Detection (swiftlet, rat, snake)                 │
│  ByteTrack Tracker (swiftlet trajectories)             │
│  LineCounter (movement balance within counting window) │
│  PredatorMonitor (debounce streak + cooldown window)   │
└─────────────────────────────┬──────────────────────────┘
                              │ Canonical AIEvent (PREDATOR_DETECTED)
                              ▼
┌────────────────────────────────────────────────────────┐
│                      AI Service                        │
│                                                        │
│  CameraPipeline & AIRuntimeManager                     │
│  DomainEventPublisherRuntimeSink (Filter & Mapper)     │
│  CameraMetadataResolver (Farm/Zone Context Resolution) │
└─────────────────────────────┬──────────────────────────┘
                              │ DomainEventPublisher Port
                              │ (RabbitMQEventPublisher Adapter)
                              ▼
                  swiftlet.domain.events (Topic Exchange)
                              │
             ┌────────────────┴────────────────┐
             │ routing_key: ai.predator.detected
             ▼
notification.alert-events.v1
```

### Key Transport Distinctions:
- **WebSocket (`/ws/cameras/{camera_id}`)**: Realtime visualization transport delivering raw detections, tracking bounding boxes, FPS, and live count updates to operator dashboards.
- **RabbitMQ (`swiftlet.domain.events`)**: Cloud-internal asynchronous domain event transport delivering actionable alerts (predator intrusions) to Notification Service.

---

## 2. Core Rule: Detection ≠ Domain Event

Raw visual detections and high-frequency counting metrics are **never** published directly to RabbitMQ notification queues.

```text
WRONG:
Detection / Count Frame (every 30ms) ──> RabbitMQ ──> Flood Notification Queue & FCM Push

CORRECT:
Detection Frame (every 30ms) ──> RuntimeEventSink
                                       │
                                       ├── Swiftlet detection? ──> Dashboards only (WebSocket); NO RABBITMQ
                                       │
                                       ├── Count update?       ──> Dashboards only (WebSocket); NO RABBITMQ
                                       │
                                       ├── Status update?      ──> Dashboards only (WebSocket); NO RABBITMQ
                                       │
                                       └── Predator detection? (rat | snake)
                                             │
                                             └── Debounced & Cooldown satisfied?
                                                   │
                                                   ├── YES ──> Publish ai.predator.detected ONCE per episode
                                                   └── NO  ──> Suppress (already alerted in current episode)
```

---

## 3. Predator Monitoring & Domain Alert Authority

To prevent alert flooding when a predator remains visible across multiple video frames, deduplication and debounce are owned exclusively by the AI Pipeline domain engine:

1. **Pipeline Level (`PredatorMonitor`)**:
   - `min_consecutive_frames` (default: 3 frames): Debounces transient detection noise / false positives.
   - `cooldown_s` (default: 30.0s): Once fired, subsequent frames of the same predator class on that camera are suppressed during the cooldown window.
2. **Sink Level (`DomainEventPublisherRuntimeSink`)**:
   - Acts as a pure transport adapter: It maps validated `AIEvent` instances to `DomainEvent` without maintaining a secondary duplicate cooldown timer. This guarantees that any legitimate event `PredatorMonitor` fires after cooldown is faithfully delivered.

### Supported Predator Classes:
Only `rat` and `snake` are recognized domain predator alerts in Contract V1:
- `swiftlet` detections are filtered out from domain event publication.
- Out-of-spec classes (such as `owl`, `cat`, `dog`) are rejected at schema validation.

---

## 4. Canonical Event Envelope & Payload Schema

AI Service emits events wrapped in the canonical CP7 `DomainEvent` envelope:

```json
{
  "eventId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "eventType": "ai.predator.detected",
  "eventVersion": "1.0",
  "occurredAt": "2026-10-28T14:35:00.000Z",
  "producer": "ai-service",
  "correlationId": null,
  "payload": {
    "farmId": "FARM-01",
    "zoneId": "ZONE-01",
    "cameraId": "CAM-01",
    "predatorClass": "rat",
    "confidence": 0.915,
    "snapshotRef": "rat_cam01.jpg",
    "frameWidth": 1920,
    "frameHeight": 1080,
    "bbox": {
      "x": 300.0,
      "y": 400.0,
      "width": 80.0,
      "height": 50.0
    }
  }
}
```

### Coordinate & Dimension Mapping:
- **Source Model BBox**: Pixel coordinates `(x1, y1, x2, y2)`.
- **Domain Event BBox**: Derived pixel format `{"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1}`.
- **Resolution**: Cached dynamically from `CameraRuntimeStatus` or detection frames (`frameWidth`, `frameHeight`).
- **Metadata Fallback Policy**: If `farmId` or `zoneId` cannot be resolved for a camera, the event is safely dropped with diagnostic logging. The production runtime NEVER fabricates fake business identifiers (e.g. `FARM-01`/`ZONE-01`).

---

## 5. Information Security & Snapshot Reference Sanitization

To prevent leaking local server directory structures across microservice boundaries:
- Internal file paths (e.g., `C:\app\data\snapshots\rat_123.jpg` or `/var/snapshots/rat_123.jpg`) are sanitized by `DomainEventPublisherRuntimeSink` using `Path(snapshot).name`.
- Downstream microservices only receive safe, opaque identifiers (e.g. `rat_123.jpg`), preserving strict information security.

---

## 6. Port & Adapter Decoupling & Reliability Model

The AI domain and runtime layers have zero hard dependencies on `aio-pika` or RabbitMQ:

```text
Domain / Pipeline Layer:
   AIEvent ("PREDATOR_DETECTED")
              ↓
   DomainEventPublisherRuntimeSink
              ↓
   DomainEventPublisher (Port / ABC)
        ├── NoOpDomainEventPublisher       (Default when RABBITMQ_ENABLED=false)
        ├── InMemoryDomainEventPublisher   (Unit testing & verification)
        └── RabbitMQEventPublisher         (Adapter for live RabbitMQ topology)
```

### Reliability & Delivery Characteristics:
- **Durable Topology**: Topic exchange `swiftlet.domain.events` and queue `notification.alert-events.v1` are declared durable.
- **Persistent Messages**: Messages are tagged `DeliveryMode.PERSISTENT` to be written to disk by the broker upon receipt.
- **Publisher Confirms**: Confirm channels wait for broker acknowledgment before completing publication.
- **Absence of Transactional Outbox**: The AI Service does NOT implement an outbox table or persistent disk queue buffer. If RabbitMQ is offline or unreachable at the instant an event is published, the event is logged as failed and dropped.
- **Delivery Semantics**: Best-effort at-most-once across broker outage windows; at-least-once across network retry boundaries. There is **no exactly-once guarantee**.
- **Fault Isolation**: Broker failures increment failure counters and log diagnostics without disrupting live video feeds, computer vision tracking, or local WebSocket streaming.

---

## 7. Topology & Routing Configuration

- **Exchange**: `swiftlet.domain.events` (Topic, Durable)
- **Routing Key**: `ai.predator.detected`
- **Destination Queue**: `notification.alert-events.v1`
- **Delivery Mode**: `aio_pika.DeliveryMode.PERSISTENT`
- **Publisher Confirms**: Enabled (`channel(publisher_confirms=True)`)
