# SwiftletCare Alert & Notification Service (TV3 Reference Implementation)

> **TV3 Ownership Reference — Frozen at CP6.5**  
> This directory contains the complete, transport-neutral, tested domain and application reference implementation for SwiftletCare's Alert & Notification subsystem.

---

## 1. Purpose & Service Scope

The **Alert & Notification Service** manages:
1. **Operational Alert Lifecycles:** Detecting abnormal farm conditions (high/low temperature, abnormal humidity, audio sensor faults, offline gateways, actuator command failures, and predator sightings), deduplicating repeating conditions, and handling hysteresis auto-recovery.
2. **Notification Delivery:** Resolving eligible recipients (Farm Owners, Technicians, Managers) and delivering notifications across multiple channels:
   - **IN_APP:** Persistent notification inbox accessible via REST API and streamed live via WebSocket.
   - **FCM (Firebase Cloud Messaging):** Push notifications to registered mobile devices (Android, iOS, Web).

```
IoT Service (Telemetry/Presence/Command) ──┐
                                          ├── Input Events ──→ [ Alert & Notification Service ]
AI Service (Predator Detection) ──────────┘                         │
                                                                   ├── State Machine & Dedup
                                                                   ├── Recipient Resolver
                                                                   └── Multi-Channel Dispatch
                                                                        ├── IN_APP (REST/WS)
                                                                        └── FCM Push (Firebase)
```

---

## 2. Core Concepts: Alert vs. Notification

A strict separation is enforced between the farm's operational state and user communication:

| Dimension | `Alert` | `Notification` |
|---|---|---|
| **Identity** | Identifies an operational **condition** at a farm/zone/device. | Identifies a **message delivered to a specific user**. |
| **Cardinality** | 1 alert per active issue (deduplicated across time). | Many notifications per alert (1 per recipient / device). |
| **Lifecycle** | `OPEN` → `ACKNOWLEDGED` → `RESOLVED` | `PENDING` → `SENT` → `DELIVERED` / `FAILED` / `SUPPRESSED` |
| **Read State** | N/A (alerts are acknowledged/resolved). | `read_at: Optional[datetime]` (derived `is_read`). |

---

## 3. Canonical Contracts (Frozen V1)

### Alert Status
- `OPEN`: Condition active, unhandled.
- `ACKNOWLEDGED`: Operator has claimed/acknowledged the alert.
- `RESOLVED`: Condition resolved (by `SYSTEM` via recovery, or by human operator).

### Alert Severity
- `CRITICAL`: Immediate threat (e.g. `PREDATOR_DETECTED`, extreme temperature > 33°C).
- `HIGH`: Major equipment failure (`COMMAND_FAILED`, temperature breach).
- `MEDIUM`: Warning thresholds (`AUDIO_FAULT`, humidity breach).
- `LOW`: Minor notifications.

### Alert Event Types
- `PREDATOR_DETECTED`: AI visual detection (owl, snake, rat).
- `HIGH_TEMPERATURE`: Ambient temperature > `high_temp_celsius`.
- `LOW_TEMPERATURE`: Ambient temperature < `low_temp_celsius`.
- `HIGH_HUMIDITY`: Ambient humidity > `high_humidity_pct`.
- `LOW_HUMIDITY`: Ambient humidity < `low_humidity_pct`.
- `AUDIO_FAULT`: Audio sensor health flag false.
- `DEVICE_OFFLINE`: Gateway / node presence heartbeat lost.
- `COMMAND_FAILED`: IoT actuator command returned `FAILED`, `ERROR`, or `TIMEOUT`.

---

## 4. Deduplication & Recovery Mechanics

1. **Deduplication Key:** Active alerts are matched on `(farm_id, zone_id, device_id/camera_id, event_type)`.
2. **Occurrence Count:** Repeated signals increment `occurrence_count` and update `last_occurred_at` on the active alert. **No new notifications are spammed.**
3. **Hysteresis Deadband (Auto-Recovery):**
   - High Temperature triggers when $T > 31.0^\circ\text{C}$.
   - Auto-resolves only when $T \le 30.5^\circ\text{C}$ (recovery deadband = $0.5^\circ\text{C}$).
   - Low Temperature triggers when $T < 27.0^\circ\text{C}$, auto-resolves when $T \ge 27.5^\circ\text{C}$.
4. **Device Presence:**
   - `OFFLINE` status creates `DEVICE_OFFLINE` alert.
   - Subsequent `ONLINE` heartbeat auto-resolves the alert with `resolved_by = "SYSTEM"`.
5. **Human-Only Resolution:**
   - `PREDATOR_DETECTED` and `COMMAND_FAILED` alerts **never** auto-resolve; they require explicit operator resolution via `POST /api/v1/alerts/{alertId}/resolve`.

---

## 5. Recipient Resolution & Multi-Channel Delivery

1. [`RecipientResolver`](file:///d:/Development/Projects/XD_PM_HDT/services/notification-service/app/ports/recipient_resolver.py): Queries farm/zone memberships to identify users eligible for the alert based on role and severity.
2. **IN_APP Dispatch:** Exactly one `Notification(channel="IN_APP", delivery_status="SENT")` created per recipient.
3. **FCM Push Dispatch:** One `Notification(channel="FCM")` created per enabled device registered to the recipient:
   - On gateway accept: `delivery_status = "SENT"`. (Never automatically marked `DELIVERED`).
   - On error: `delivery_status = "FAILED"`, failure details recorded.
   - If token is reported unregistered/invalid: the device is **soft-disabled** (`UserDevice.is_enabled = False`) while preserving the database record.

---

## 6. Firebase FCM Adapter (`app/infrastructure/firebase/`)

The production adapter is encapsulated behind the abstract [`FCMProvider`](file:///d:/Development/Projects/XD_PM_HDT/services/notification-service/app/ports/fcm_provider.py) port.

### Modes
- `mock`: Uses [`MockFCMProvider`](file:///d:/Development/Projects/XD_PM_HDT/services/notification-service/app/services/mock_fcm_provider.py) for fast local unit testing without network dependencies.
- `firebase`: Backed by [`RealFirebaseMessagingClient`](file:///d:/Development/Projects/XD_PM_HDT/services/notification-service/app/infrastructure/firebase/client.py) using official `firebase-admin` SDK with lazy initialization.
- `disabled`: Backed by [`DisabledFCMProvider`](file:///d:/Development/Projects/XD_PM_HDT/services/notification-service/app/infrastructure/firebase/disabled_provider.py), suppressing push sends safely without throwing or impacting in-app notifications.

### Data Payload Sanitization & Security
- `sanitize_fcm_data()` guarantees all values are strings.
- Strips any local filesystem paths (e.g. `C:\...`, `/home/...`, `file://`) to prevent path traversal leaks.
- Preserves valid HTTP/HTTPS URLs (such as camera snapshot URLs).
- `redact_token()` redacts tokens in logs (`fcm_...7890`).

---

## 7. REST API & WebSocket Reference

### Public REST Routes
- `GET /health`: Health probe with non-sensitive FCM provider status.
- `GET /api/v1/alerts`: List alerts with filters (`farmId`, `zoneId`, `status`, `severity`, `eventType`).
- `GET /api/v1/alerts/{alertId}`: Detailed alert view.
- `POST /api/v1/alerts/{alertId}/acknowledge`: Acknowledge alert (`actorId`).
- `POST /api/v1/alerts/{alertId}/resolve`: Resolve alert (`actorId`, `resolutionNote`).
- `GET /api/v1/notifications`: User notification inbox (requires `X-User-Id` header).
- `POST /api/v1/notifications/{notificationId}/read`: Mark notification as read.
- `POST /api/v1/notifications/read-all`: Mark all notifications as read for user.
- `POST /api/v1/devices`: Register or update user device (`deviceId`, `userId`, `fcmToken`, `platform`).
- `DELETE /api/v1/devices/{deviceRegistrationId}`: Unregister a user device.

### Realtime WebSocket
- **Endpoint:** `/ws/notifications?userId={userId}`
- **Emitted Events:**
  - `alert.created`, `alert.updated`
  - `notification.created`, `notification.updated` (strictly scoped to authenticated `userId`).

### Internal Test Ingress (Hidden from public OpenAPI)
- `POST /internal/v1/events/iot/telemetry`
- `POST /internal/v1/events/iot/presence`
- `POST /internal/v1/events/iot/command`
- `POST /internal/v1/events/ai`

---

## 8. Configuration & Environment Variables

| Variable | Type | Default | Description |
|---|---|---|---|
| `FCM_PROVIDER` | `str` | `mock` | `mock`, `firebase`, or `disabled` |
| `FCM_ENABLED` | `bool` | `true` | Master push channel switch |
| `FIREBASE_PROJECT_ID` | `str` | `None` | Google Cloud / Firebase project ID |
| `FIREBASE_CREDENTIALS_PATH` | `str` | `None` | Path to `serviceAccountKey.json` |

*Security Warning: Never commit real credentials, service account JSON files, or private keys to version control.*

---

## 9. How to Run & Verify

### Running Automated Tests
```powershell
# Run all 109 Notification Service tests
$env:PYTHONPATH="services/notification-service;services/notification-service/app"
python -m pytest services/notification-service/tests
```

### Running the End-to-End Demonstration Scripts
```powershell
# Comprehensive Cases A-E validation
python services/notification-service/scripts/demo_final_e2e.py

# Firebase FCM specific validation
python services/notification-service/scripts/demo_fcm_e2e.py
```

### Starting the Local Development Server
```powershell
$env:PYTHONPATH="services/notification-service;services/notification-service/app"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8004 --reload
```
- OpenAPI Documentation: `http://127.0.0.1:8004/docs`
- Health Probe: `http://127.0.0.1:8004/health`

---

## 10. Technical Debt & CP7 Integration Roadmap

### Current Reference Limitations
1. **In-Memory Repositories:** Current repositories store data in RAM. TV3 must implement PostgreSQL persistence adapters backed by SQLAlchemy or Tortoise ORM for production.
2. **WebSocket Broadcast Authorization:** In this local reference, alert events are broadcast to active connections. In production, API Gateway / Management integration must filter alerts by farm ownership.
3. **Synchronous Ingress:** Current event ingestion uses `/internal/v1/events/*` REST endpoints for testing.

### CP7 RabbitMQ Integration Seam
In CP7, asynchronous message queues will replace HTTP event ingress:
```
RabbitMQ Exchange ("iot.events", "ai.events")
    ↓
app/infrastructure/rabbitmq/
    ├── connection.py    # AMQP robust connection manager
    ├── consumer.py      # Background worker listening to queues
    ├── topology.py      # Queue and binding declarations
    └── mapper.py        # Maps raw AMQP JSON into Canonical Input Events
         ↓
NotificationService.handle_telemetry_event()
NotificationService.handle_presence_event()
NotificationService.handle_command_event()
NotificationService.handle_ai_event()
```
The domain core, rule engine, alert lifecycle, and notification delivery pipelines **require zero changes** for RabbitMQ integration.
