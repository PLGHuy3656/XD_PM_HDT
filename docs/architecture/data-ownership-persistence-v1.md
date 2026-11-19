# Data Ownership & Persistence Contract V1
**Project**: SwiftletCare / NestMate  
**Milestone**: CP8.0 — Architecture & Design Baseline  
**Status**: FROZEN CONTRACT V1  
**Scope**: Management Service, IoT Service, AI Service, Notification Service, Analytics Service (Future), Apache NiFi (Future)

---

## 1. Purpose

This document establishes the authoritative **Data Ownership and Persistence Contract V1** for SwiftletCare / NestMate. It governs:
1. Which service owns each business entity and data record.
2. The role of **PostgreSQL** (authoritative durable operational storage) vs. **Redis** (ephemeral cache, fast-access runtime state, atomic idempotency).
3. The boundary rules separating operational persistence from analytical persistence (CP9 / Apache NiFi).
4. The strict prohibition of cross-service foreign keys, shared databases, and cross-service direct writes.
5. The phased implementation roadmap for CP8 (CP8.1 through CP8.5).

---

## 2. Database-per-Service Principle

SwiftletCare strictly follows the **Database-per-Service** pattern:

```text
┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
│  Management Service  │   │     IoT Service      │   │      AI Service      │   │ Notification Service │
└──────────┬───────────┘   └──────────┬───────────┘   └──────────┬───────────┘   └──────────┬───────────┘
           │                          │                          │                          │
           ▼                          ▼                          ▼                          ▼
    ┌──────────────┐           ┌──────────────┐           ┌──────────────┐           ┌──────────────┐
    │management_db │           │    iot_db    │           │    ai_db     │           │notification_db
    └──────────────┘           └──────────────┘           └──────────────┘           └──────────────┘
      (PostgreSQL)               (PostgreSQL)               (PostgreSQL)               (PostgreSQL)
```

### Core Rules:
1. **Single Service Ownership**: Each database and each Redis key namespace is owned by exactly one service. No service shall connect directly to or issue queries against another service's PostgreSQL database or another service's Redis keys.
2. **Dedicated DB Users**:
   - `management_user` $\to$ `management_db`
   - `iot_user` $\to$ `iot_db`
   - `ai_user` $\to$ `ai_db`
   - `notification_user` $\to$ `notification_db`
   - `analytics_user` $\to$ `analytics_db` (CP9)
3. **No Cross-Database Foreign Keys**: Under no circumstances may a table in database $A$ contain a foreign key constraint pointing to a table in database $B$.
4. **No Cross-Service Redis Access**: Redis is an internal implementation detail owned by the service using it. Service $A$ must never directly read or write Service $B$'s Redis keys.
5. **Data Sharing Channels**: Data required across boundaries is shared exclusively via:
   - Synchronous HTTP/REST service-to-service API contracts (read-only query / lookup)
   - Realtime asynchronous domain events via RabbitMQ (`swiftlet.domain.events`)
   - Batch / historical synchronization via Apache NiFi ETL (CP9)

---

## 3. Authoritative Ownership Matrix

| Entity / Concept | Management Service | IoT Service | AI Service | Notification Service | Analytics Service (CP9) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **User & Account Status** | **OWNER** | — | — | — | — |
| **Role & RBAC** | **OWNER** | — | — | — | — |
| **Farm & Physical Facility** | **OWNER** | — | — | — | — |
| **Farm Ownership** | **OWNER** | — | — | — | — |
| **Zone Physical Sub-area** | **OWNER** | — | — | — | — |
| **Device Hardware Metadata** | **OWNER** | — | — | — | — |
| **Technician & Profile** | **OWNER** | — | — | — | — |
| **Technician Farm Assignment** | **OWNER** | — | — | — | — |
| **Camera Metadata & Config** | **OWNER** | — | — | — | — |
| **Sensor Telemetry History** | — | **OWNER** | — | — | — |
| **Latest Telemetry Cache** | — | **OWNER** | — | — | — |
| **Current Device Presence (Runtime)** | — | **OWNER** | — | — | — |
| **Device Presence History (Transitions)** | — | **OWNER** | — | — | — |
| **Device Command Lifecycle** | — | **OWNER** | — | — | — |
| **Command Ack / Result** | — | **OWNER** | — | — | — |
| **Condition Transition Evaluation**| — | **OWNER** | — | — | — |
| **DetectionResult (Per-frame)** | — | — | **OWNER** | — | — |
| **CountUpdate (Line-crossing)** | — | — | **OWNER** | — | — |
| **AIEvent (Predator Detected)** | — | — | **OWNER** | — | — |
| **Camera Technical Runtime Status**| — | — | **OWNER** | — | — |
| **Alert Lifecycle (State Machine)**| — | — | — | **OWNER** | — |
| **Notification Dispatch Record** | — | — | — | **OWNER** | — |
| **UserDevice (FCM Push Tokens)** | — | — | — | **OWNER** | — |
| **Message Idempotency Lease** | — | — | — | **OWNER** | — |
| **Hourly / Daily Bird Activity** | — | — | — | — | **OWNER** |
| **7 / 14 / 30 Day Trends** | — | — | — | — | **OWNER** |
| **Environment History Aggregates** | — | — | — | — | **OWNER** |
| **Bird ↔ Environment Correlation** | — | — | — | — | **OWNER** |

*Note*: External references (e.g., `farmId` in a telemetry record or `userId` in a notification) do **not** imply ownership. They are contextual identifier foreign references.

---

## 4. Role of PostgreSQL

PostgreSQL serves as the **durable system of record** for all authoritative business and operational truth:

```text
PostgreSQL Databases:
├── management_db
│   └── Authoritative physical topology, identities, roles, device/camera registry
├── iot_db
│   └── Historical telemetry, device command audits, meaningful presence transition history
├── ai_db
│   └── Line-crossing CountUpdate records, AIEvent audit records (predator detections)
├── notification_db
│   └── Operational alerts, notification dispatch records, user push device registrations
└── analytics_db (CP9)
    └── Aggregated historical analytical warehouse, trends, correlation datasets
```

### Invariants for PostgreSQL:
- **ACID Transactions**: Local relational integrity, constraints, and audit log consistency.
- **Authoritative Timestamps**: All business timestamps are stored in UTC using `TIMESTAMPTZ`.
- **Durable Operational Truth**: If disposable runtime/cache infrastructure (Redis) fails or restarts, PostgreSQL retains the complete authoritative historical and business truth without data loss.

---

## 5. Role of Redis

**Redis = disposable runtime, cache, and idempotency infrastructure.**  
**PostgreSQL = durable operational truth.**

Redis serves three strictly scoped operational purposes:
1. **Message Idempotency**: Atomic reservation (`SET NX EX`) and terminal state tracking (`DONE`) for consumer duplicate suppression.
2. **Ephemeral Live Runtime State**: High-frequency, volatile operational state (current device presence, live camera pipeline status) that is continuously updated from live activity and must not bloat PostgreSQL on every heartbeat or frame.
3. **Fast-Access Cache**: Read-through or write-through projections of the latest telemetry/count records to accelerate UI/dashboard queries.

```text
Redis Key Namespace Architecture (Strictly Service-Private):

notification:idempotency:{eventId}  (Implemented as swiftlet:idempotency:{eventId})
├── Value: "PROCESSING" (TTL: 60s) | "DONE" (TTL: 86400s)
└── Owner: Notification Service ONLY (Active in CP7.5/CP7.6)

iot:latest:{deviceId}
├── Value: JSON snapshot of latest AcceptedTelemetry
└── Owner: IoT Service ONLY (Target: CP8.4)

iot:presence:{deviceId}
├── Value: JSON snapshot of current runtime DevicePresence (ONLINE/OFFLINE, last_seen_at)
└── Owner: IoT Service ONLY (Target: CP8.4)

ai:latest:{cameraId}
├── Value: JSON snapshot of latest CountUpdate & Detection summary
└── Owner: AI Service ONLY (Target: CP8.4)

ai:runtime:{cameraId}
├── Value: JSON snapshot of CameraRuntimeStatus (fps, health, state)
└── Owner: AI Service ONLY (Target: CP8.4)
```

### Service Isolation Rule for Redis:
- Redis is an **internal implementation detail** owned by the specific service that writes a key namespace.
- No service may directly inspect or mutate another service's Redis keys (e.g., Management Service **must never** directly read `iot:presence:{deviceId}`). Cross-service queries must traverse HTTP/REST service contracts.

### Prohibitions for Redis:
- Redis is **NOT** a primary database.
- Redis is **NOT** the authoritative storage for users, passwords, farms, or devices.
- Redis is **NOT** the authoritative storage for historical telemetry or analytics.

### Redis Disaster Recovery Semantics by Category:
Redis loss **MUST NOT** cause loss of durable historical or business truth. Recovery behavior depends strictly on the data category:
- **A. Recoverable Cache** (`iot:latest:{deviceId}`, `ai:latest:{cameraId}`):
  - Rebuilt from PostgreSQL historical records where applicable, or repopulated upon the next incoming write.
- **B. Live Runtime State** (`ai:runtime:{cameraId}`, current `iot:presence:{deviceId}`):
  - **NOT** rebuilt from PostgreSQL historical rows.
  - Reconstructed organically from new live runtime observations, incoming device heartbeats, telemetry arrivals, or active camera pipeline execution.
- **C. Notification Message Idempotency** (`notification:idempotency:{eventId}` / `swiftlet:idempotency:{eventId}`):
  - Follows its established CP7 reliability and TTL semantics.
  - **NOT** reconstructed from PostgreSQL (it is transient transport-level deduplication state, distinct from durable domain `Alert` deduplication in `notification_db`).

---

## 6. Management Service — Authoritative Data

Management Service is the **sole authoritative master** for identity, authorization, organizational topology, and physical equipment registration.

```text
management_db Schema (PostgreSQL):
├── users (id UUID PK, email, password_hash, full_name, phone, status, timestamps)
├── roles (id UUID PK, name, description, created_at)
├── user_roles (user_id FK, role_id FK, assigned_at)
├── farms (id UUID PK, farm_code, name, address, status, owner_id FK, timestamps)
├── zones (id UUID PK, farm_id FK, zone_code, name, timestamps)
├── devices (id UUID PK, node_id, farm_id FK, zone_id FK, name, device_type, firmware_version, ip_address, is_active, timestamps)
├── technicians (id UUID PK FK->users, full_name, email, phone, status, timestamps)
└── technician_assignments (id UUID PK, technician_id FK, farm_id FK, is_primary, is_active, assigned_at)
```

### Security & Password Rules:
- Password hashes must use **Argon2id**. Plaintext passwords and JWT tokens must **never** be persisted in the database.
- `owner_id` links a `farm` to an owner `user`.
- Other services (IoT, AI, Notification) reference `farmId`, `zoneId`, `deviceId`, and `userId` as external opaque string/UUID values. They must never alter or create local authoritative mirrors of these tables.

---

## 7. IoT Service — Operational Data

IoT Service owns all ingestion, normalization, command dispatching, and condition monitoring for environmental sensors and hardware actuators.

```text
iot_db Schema Target (PostgreSQL - CP8.1):
├── telemetry_records
│   ├── id UUID PRIMARY KEY DEFAULT gen_random_uuid()
│   ├── device_id VARCHAR(100) NOT NULL
│   ├── farm_id VARCHAR(100)
│   ├── zone_id VARCHAR(100)
│   ├── temperature DOUBLE PRECISION
│   ├── humidity DOUBLE PRECISION
│   ├── lux DOUBLE PRECISION
│   ├── co2 DOUBLE PRECISION
│   ├── audio_rms DOUBLE PRECISION
│   ├── audio_healthy BOOLEAN
│   ├── misting_state BOOLEAN
│   ├── fan_state BOOLEAN
│   ├── heater_state BOOLEAN
│   ├── alarm_state BOOLEAN
│   ├── mode VARCHAR(20)
│   ├── network_rssi INTEGER
│   ├── free_heap INTEGER
│   ├── recorded_at TIMESTAMPTZ NOT NULL (device timestamp if present, fallback server)
│   ├── received_at TIMESTAMPTZ NOT NULL DEFAULT NOW() (authoritative server UTC)
│   └── raw_payload JSONB
│
├── device_commands
│   ├── command_id VARCHAR(100) PRIMARY KEY
│   ├── device_id VARCHAR(100) NOT NULL
│   ├── farm_id VARCHAR(100)
│   ├── zone_id VARCHAR(100)
│   ├── action VARCHAR(50) NOT NULL
│   ├── target VARCHAR(50) NOT NULL
│   ├── requested_state JSONB NOT NULL
│   ├── status VARCHAR(30) NOT NULL (PENDING, PUBLISHED, ACKNOWLEDGED, COMPLETED, FAILED)
│   ├── error VARCHAR(255)
│   ├── created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
│   ├── published_at TIMESTAMPTZ
│   ├── acked_at TIMESTAMPTZ
│   └── completed_at TIMESTAMPTZ
│
└── device_presence_history (Durable Presence Transition Audit)
    ├── id UUID PRIMARY KEY DEFAULT gen_random_uuid()
    ├── device_id VARCHAR(100) NOT NULL
    ├── farm_id VARCHAR(100)
    ├── zone_id VARCHAR(100)
    ├── previous_status VARCHAR(20) (ONLINE, OFFLINE, NULL on initial registration)
    ├── status VARCHAR(20) NOT NULL (ONLINE, OFFLINE)
    ├── transitioned_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    ├── last_seen_at TIMESTAMPTZ
    └── reason VARCHAR(100) (e.g., HEARTBEAT_RECEIVED, STALE_TIMEOUT)
```

### Separation of Current Runtime Presence vs. Presence Transition History:
1. **Current Device Presence (Runtime / Latest State)**:
   - Represents the live, high-frequency operational state (`ONLINE` / `OFFLINE`, `last_seen_at`, `last_ip`, `firmware_version`, `missed_heartbeats`).
   - Stored in **Redis** (`iot:presence:{deviceId}`).
   - Disposable and reconstructed from live heartbeats and incoming telemetry observations.
   - **Rule**: Routine heartbeats and telemetry arrivals **MUST NOT** insert a new PostgreSQL row on every tick.
2. **Device Presence History (Meaningful Transitions)**:
   - Represents discrete state transitions only (`ONLINE` $\to$ `OFFLINE` or `OFFLINE` $\to$ `ONLINE`).
   - Stored durably in **PostgreSQL** (`iot_db.device_presence_history`).
   - Provides a permanent operational audit trail corresponding to `iot.device.offline` and `iot.device.online` domain events.

### Telemetry Timestamp Rule:
- `received_at`: **Authoritative business timestamp** assigned by the server upon MQTT ingestion in UTC.
- Firmware device timestamp, if transmitted, is stored purely as supplementary metadata in `recorded_at`.

---

## 8. AI Service — Operational Data

AI Service owns video inference outputs, computer vision telemetry, and predator detection tracking.

```text
ai_db Schema Target (PostgreSQL - CP8.2):
├── ai_count_updates
│   ├── id UUID PRIMARY KEY DEFAULT gen_random_uuid()
│   ├── camera_id VARCHAR(100) NOT NULL
│   ├── farm_id VARCHAR(100)
│   ├── zone_id VARCHAR(100)
│   ├── frame_id BIGINT NOT NULL
│   ├── entry_count INTEGER NOT NULL
│   ├── exit_count INTEGER NOT NULL
│   ├── net_change INTEGER NOT NULL (strictly entry_count - exit_count)
│   ├── delta_entry INTEGER NOT NULL
│   ├── delta_exit INTEGER NOT NULL
│   ├── window_started_at TIMESTAMPTZ NOT NULL
│   ├── recorded_at TIMESTAMPTZ NOT NULL
│   └── created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
│
└── ai_events
    ├── event_id VARCHAR(100) PRIMARY KEY
    ├── event_type VARCHAR(50) NOT NULL (PREDATOR_DETECTED)
    ├── camera_id VARCHAR(100) NOT NULL
    ├── farm_id VARCHAR(100)
    ├── zone_id VARCHAR(100)
    ├── frame_id BIGINT NOT NULL
    ├── predator_class VARCHAR(50) NOT NULL (rat, snake)
    ├── confidence DOUBLE PRECISION NOT NULL
    ├── bbox JSONB NOT NULL ({x1, y1, x2, y2})
    ├── bbox_x1 DOUBLE PRECISION NOT NULL
    ├── bbox_y1 DOUBLE PRECISION NOT NULL
    ├── bbox_x2 DOUBLE PRECISION NOT NULL
    ├── bbox_y2 DOUBLE PRECISION NOT NULL
    ├── snapshot_ref VARCHAR(512)
    ├── detected_at TIMESTAMPTZ NOT NULL
    └── created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
```

### Selective Persistence Principle for AI:
1. **Per-frame `DetectionResult`**: Generated at 15–30 FPS. Storing raw bounding boxes for every frame into PostgreSQL would produce tens of millions of records per day, creating unacceptable disk and I/O pressure. **Per-frame detections are ephemeral** (kept in memory ring buffer and published to WebSocket for live viewing).
2. **`CountUpdate`**: Persisted periodically (e.g. per counting window). These records are durable and serve as the raw input for CP9 Analytics ETL.
3. **`AIEvent`**: High-value security events (predator detections). Persisted durably with snapshot references for traceability.
4. **Image Snapshots**: Raw image binaries are **never** stored in PostgreSQL. V1 stores snapshots on local filesystem (`outputs/snapshots/`) with relative path/URL references stored in the database. Future object storage (S3/MinIO) can replace the local filesystem seamlessly.

---

## 9. Notification Service — Operational Data

Notification Service owns the complete alert lifecycle state machine, user notifications, and multi-device FCM push tokens.

```text
notification_db Schema Target (PostgreSQL - CP8.3):
├── alerts
│   ├── alert_id VARCHAR(100) PRIMARY KEY
│   ├── event_type VARCHAR(100) NOT NULL
│   ├── source VARCHAR(50) NOT NULL (AI, IOT_ENVIRONMENT, IOT_DEVICE)
│   ├── severity VARCHAR(30) NOT NULL (LOW, MEDIUM, HIGH, CRITICAL)
│   ├── status VARCHAR(30) NOT NULL (OPEN, ACKNOWLEDGED, RESOLVED)
│   ├── farm_id VARCHAR(100) NOT NULL
│   ├── zone_id VARCHAR(100)
│   ├── device_id VARCHAR(100)
│   ├── camera_id VARCHAR(100)
│   ├── title VARCHAR(255) NOT NULL
│   ├── message TEXT NOT NULL
│   ├── snapshot_url VARCHAR(255)
│   ├── telemetry_snapshot JSONB
│   ├── occurrence_count INTEGER NOT NULL DEFAULT 1
│   ├── created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
│   ├── updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
│   ├── last_occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
│   ├── acknowledged_at TIMESTAMPTZ
│   ├── acknowledged_by VARCHAR(100)
│   ├── resolved_at TIMESTAMPTZ
│   ├── resolved_by VARCHAR(100)
│   ├── resolution_note TEXT
│   ├── source_event_id VARCHAR(100)
│   └── metadata JSONB
│
├── notifications
│   ├── notification_id VARCHAR(100) PRIMARY KEY
│   ├── alert_id VARCHAR(100) NOT NULL
│   ├── user_id VARCHAR(100) NOT NULL
│   ├── channel VARCHAR(30) NOT NULL (IN_APP, FCM)
│   ├── delivery_status VARCHAR(30) NOT NULL (PENDING, SENT, DELIVERED, FAILED, SUPPRESSED)
│   ├── title VARCHAR(255) NOT NULL
│   ├── body TEXT NOT NULL
│   ├── data JSONB
│   ├── failure_reason TEXT
│   ├── created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
│   ├── sent_at TIMESTAMPTZ
│   └── read_at TIMESTAMPTZ
│
└── user_devices
    ├── device_id VARCHAR(100) PRIMARY KEY
    ├── user_id VARCHAR(100) NOT NULL
    ├── fcm_token VARCHAR(255) UNIQUE NOT NULL
    ├── platform VARCHAR(30) NOT NULL (WEB, ANDROID, IOS)
    ├── device_name VARCHAR(100)
    ├── is_enabled BOOLEAN NOT NULL DEFAULT TRUE
    ├── created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    └── updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
```

### Alert & Notification Invariants:
1. `OPEN` $\to$ `ACKNOWLEDGED` $\to$ `RESOLVED` (and direct `OPEN` $\to$ `RESOLVED`) transitions remain valid.
2. Read state is represented by `read_at TIMESTAMPTZ`, **never** as a delivery status enum.
3. Message processing idempotency remains in Redis (`swiftlet:idempotency:{eventId}`), separate from domain Alert deduplication.

---

## 10. Analytics Service — Future Ownership (CP9)

Analytics Service is scheduled for **CP9**. It owns all derived, aggregated, and correlation data models:

```text
analytics_db (CP9 Target):
├── hourly_bird_activity (farm_id, zone_id, camera_id, hour_timestamp, total_entry, total_exit, net_movement)
├── daily_bird_activity (farm_id, zone_id, date, total_entry, total_exit, peak_activity_hour)
├── environment_hourly_aggregates (farm_id, zone_id, metric, min_val, max_val, avg_val, std_dev)
├── bird_environment_correlations (farm_id, zone_id, period_start, correlation_temp_entry, correlation_humidity_entry)
└── alert_statistics (farm_id, period, alert_count_by_type, mean_time_to_resolve_minutes)
```

### Cardinal Rule:
Analytics Service **never** owns operational truth. IoT Service owns raw telemetry; AI Service owns raw counts; Notification Service owns operational alerts. Analytics DB receives transformed read-only projections.

---

## 11. Apache NiFi Data Flow (Future CP9)

NiFi acts as the **data movement and historical ETL pipeline**, decoupled from realtime message queuing:

```text
Operational Databases (PostgreSQL):
┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│ management_db  │  │     iot_db     │  │     ai_db      │  │notification_db │
└───────┬────────┘  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘
        │                   │                   │                   │
        └─────────────┐     │     ┌─────────────┘                   │
                      ▼     ▼     ▼                                 ▼
                 ┌────────────────────────────────────────────────────┐
                 │                    Apache NiFi                     │
                 │   - CDC / Periodic Polling / Transformation ETL    │
                 │   - Scrubbing, Windowing, Aggregations             │
                 └─────────────────────────┬──────────────────────────┘
                                           │
                                           ▼
                               ┌──────────────────────┐
                               │     analytics_db     │
                               └──────────────────────┘
```

### RabbitMQ vs. NiFi Distinction:
- **RabbitMQ**: Realtime, low-latency, point-in-time asynchronous domain events triggering reactive operations (e.g. threshold crossed $\to$ push alert).
- **NiFi**: Bulk, high-throughput, scheduled historical data synchronization and aggregation for business intelligence. Raw telemetry is **not** routed through RabbitMQ to reach Analytics.

---

## 12. External Reference Rule & No Cross-Service Foreign Keys

### Forbidden Patterns:
```sql
-- STRICTLY FORBIDDEN: Cross-database foreign keys
ALTER TABLE iot.telemetry ADD CONSTRAINT fk_iot_farm FOREIGN KEY (farm_id) REFERENCES management.farms(id);
ALTER TABLE notification.alerts ADD CONSTRAINT fk_alert_user FOREIGN KEY (acknowledged_by) REFERENCES management.users(id);
```

### Permitted Patterns:
- External identifiers (`farm_id`, `zone_id`, `device_id`, `camera_id`, `user_id`) are stored as plain `VARCHAR` or `UUID` fields without database-enforced relational integrity across databases.
- Service-local foreign keys (e.g., `notifications.alert_id REFERENCES alerts(alert_id)`) are fully permitted because both tables reside within `notification_db`.
- Validation of external IDs is handled at the application layer via REST queries or cached configuration.

---

## 13. Data Classification & Volume Table

| Data Concept | Authoritative Owner | Durability | Physical Store | Source of Truth | Volume Tier | Analytics ETL Source? |
| :--- | :--- | :---: | :--- | :--- | :---: | :---: |
| **User & Account** | Management | Durable | PostgreSQL (`management_db`) | Management | LOW | Optional (for tenant mapping) |
| **Role & RBAC** | Management | Durable | PostgreSQL (`management_db`) | Management | LOW | No |
| **Farm & Ownership**| Management | Durable | PostgreSQL (`management_db`) | Management | LOW | **Yes** |
| **Zone Facility** | Management | Durable | PostgreSQL (`management_db`) | Management | LOW | **Yes** |
| **Device Metadata** | Management | Durable | PostgreSQL (`management_db`) | Management | LOW | **Yes** |
| **Camera Metadata** | Management | Durable | PostgreSQL (`management_db`) | Management | LOW | **Yes** |
| **Technician & Assignment**| Management | Durable | PostgreSQL (`management_db`) | Management | LOW | No |
| **Raw Telemetry** | IoT | Durable | PostgreSQL (`iot_db`) | IoT Service | **HIGH** | **Yes** (Aggregated by NiFi) |
| **Latest Telemetry**| IoT | Ephemeral | Redis (`iot:latest:{id}`) | IoT Service | LOW | No |
| **Current Device Presence (Runtime)** | IoT | Ephemeral | Redis (`iot:presence:{id}`) | IoT Service | MEDIUM | No |
| **Device Presence History (Transitions)** | IoT | Durable | PostgreSQL (`iot_db`) | IoT Service | LOW/MEDIUM | Maybe (uptime/availability) |
| **Device Commands** | IoT | Durable | PostgreSQL (`iot_db`) | IoT Service | MEDIUM | Optional (audit) |
| **Per-frame Detections**| AI | Ephemeral | In-Memory / WebSocket | AI Service | **VERY HIGH** | No (discarded) |
| **CountUpdate** | AI | Durable | PostgreSQL (`ai_db`) | AI Service | MEDIUM/HIGH | **Yes** (Primary bird traffic) |
| **AIEvent (Predator)**| AI | Durable | PostgreSQL (`ai_db`) | AI Service | MEDIUM | **Yes** (Predator patterns) |
| **Camera Runtime** | AI | Ephemeral | Redis (`ai:runtime:{id}`) | AI Service | LOW | No |
| **Alert Record** | Notification | Durable | PostgreSQL (`notification_db`)| Notification | MEDIUM | **Yes** (Incident statistics) |
| **Notification Log**| Notification | Durable | PostgreSQL (`notification_db`)| Notification | MEDIUM | Optional |
| **UserDevice (FCM)**| Notification | Durable | PostgreSQL (`notification_db`)| Notification | LOW | No |
| **Message Idempotency**| Notification | Ephemeral | Redis (`swiftlet:idempotency:*`)| Notification | MEDIUM | No |

---

## 14. Current vs. Target Gap Analysis

| Service | Data Concept | Current Implementation | Target Persistence (CP8) | Identified Gap | Action Plan |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **Management** | Core entities & Presence Read | PostgreSQL (`management_db`) + `LegacyIoTAdapter` SQL read | PostgreSQL (`management_db`) + HTTP service contract to IoT Service | `LegacyIoTAdapter` reads legacy DB directly | **CP8.1**: Retire legacy SQL read; call IoT HTTP API |
| **IoT** | Raw Telemetry | `InMemoryTelemetryRepository` | PostgreSQL (`iot_db`) table `telemetry_records` | No durable storage; lost on restart | **CP8.1** |
| **IoT** | Device Command | `InMemoryCommandRepository` | PostgreSQL (`iot_db`) table `device_commands` | Command audit log lost on restart | **CP8.1** |
| **IoT** | Device Presence History (Transitions) | Not persisted | PostgreSQL (`iot_db`) table `device_presence_history` | `ONLINE` $\leftrightarrow$ `OFFLINE` transitions lost on restart | **CP8.1** |
| **IoT** | Current Device Presence (Runtime) | `InMemoryDevicePresenceRepository` | Redis (`iot:presence:{id}`) | Runtime state only in process memory | **CP8.4** |
| **IoT** | Latest Telemetry | In-memory latest lookup | Redis cache (`iot:latest:{id}`) | No shared fast-access cache | **CP8.4** |
| **AI** | CountUpdate | In-memory state store | PostgreSQL (`ai_db`) table `ai_count_updates` | Historical bird counts lost on restart | **CP8.2** |
| **AI** | AIEvent | In-memory ring buffer (max 500) | PostgreSQL (`ai_db`) table `ai_events` | Predator events evicted / lost on restart | **CP8.2** |
| **AI** | Detections | In-memory latest detection | Ephemeral in-memory (frozen) | Intentionally ephemeral | *No gap (Design decision)* |
| **AI** | Camera Runtime | In-memory latest status | Redis (`ai:runtime:{id}`) | Runtime health only in process memory | **CP8.4** |
| **Notification**| Alerts | `InMemoryAlertRepository` | PostgreSQL (`notification_db`) table `alerts` | Alerts lost on restart | **CP8.3** |
| **Notification**| Notifications | `InMemoryNotificationRepository` | PostgreSQL (`notification_db`) table `notifications` | Dispatch history lost on restart | **CP8.3** |
| **Notification**| User Devices | `InMemoryUserDeviceRepository` | PostgreSQL (`notification_db`) table `user_devices` | FCM tokens lost on restart | **CP8.3** |
| **Notification**| Idempotency | Redis (`swiftlet:idempotency:*`) | Redis (`swiftlet:idempotency:*`) | Fully operational (CP7.5/7.6) | *No gap (Preserve)* |

---

## 15. Cross-Service Reference Audit & Boundary Violations

### Audit Findings:
1. **`LegacyIoTAdapter` in Management Service**:
   - Location: `services/management-service/app/adapters/legacy_iot_adapter.py`
   - Issue: Connects via `LEGACY_IOT_DATABASE_URL` directly to the old monolithic database `swiftletcare` and queries `public.device_latest_state`.
   - Frozen Boundary Resolution:
     ```text
     Management Service
         ↓ HTTP/service contract (GET /api/v1/devices/{deviceId}/presence | GET /api/iot/devices/{device_id}/presence)
     IoT Service
         ↓
     IoT repositories / Redis
     ```
     - Management Service **MUST NOT** directly access `iot_db`, IoT Redis keys (`iot:presence:{deviceId}`, `iot:latest:{deviceId}`), or IoT internal repositories.
     - Redis is an internal implementation detail owned exclusively by the service using it.
     - In CP8.1, `LegacyIoTAdapter` direct SQL dependency is replaced by `IoTServiceAdapter` (`services/management-service/app/adapters/iot_service_adapter.py`), a service-to-service HTTP client calling IoT Service's canonical presence API routes (`GET /api/iot/devices/{device_id}/presence` and `GET /api/iot/devices/presence`).
2. **Old Monolithic Schema in `swiftletcare-backend`**:
   - Location: `swiftletcare-backend/database/schema.sql`
   - Issue: Contains monolithic foreign keys (`telemetry.device_id REFERENCES devices(id)`).
   - Resolution: This legacy monolith is superseded by the modular microservices. The new service databases (`iot_db`, `ai_db`, `notification_db`) must strictly implement independent schemas with zero foreign keys to `management_db`.

---

## 16. Database Indexing Strategy

Critical access paths identified for CP8 implementation:

### IoT Service (`iot_db`):
- `idx_telemetry_device_time`: `(device_id, recorded_at DESC)` — high-frequency range queries per device.
- `idx_telemetry_farm_time`: `(farm_id, recorded_at DESC)` — facility-wide aggregations.
- `idx_telemetry_zone_time`: `(zone_id, recorded_at DESC)` — zone-specific environment trends.
- `idx_commands_device_created`: `(device_id, created_at DESC)` — device command history.
- `idx_presence_history_device_time`: `(device_id, transitioned_at DESC)` — device presence transition audit queries.

### AI Service (`ai_db`):
- `idx_ai_count_updates_camera_recorded_at`: `(camera_id, recorded_at DESC)` — per-camera count history queries.
- `idx_ai_count_updates_camera_window`: `(camera_id, window_started_at DESC)` — line-crossing time-series ETL.
- `idx_ai_count_updates_farm_recorded_at`: `(farm_id, recorded_at DESC)` — farm-level bird traffic.
- `idx_ai_count_updates_zone_recorded_at`: `(zone_id, recorded_at DESC)` — zone-level bird traffic.
- `idx_ai_count_updates_recorded_at`: `(recorded_at DESC)` — global time-range ETL.
- `idx_ai_events_camera_detected_at`: `(camera_id, detected_at DESC)` — predator audit history per camera.
- `idx_ai_events_farm_detected_at`: `(farm_id, detected_at DESC)` — predator audit history per farm.
- `idx_ai_events_type_detected_at`: `(event_type, detected_at DESC)` — event type filtering.
- `idx_ai_events_detected_at`: `(detected_at DESC)` — recent predator events query.

### Notification Service (`notification_db`):
- `uq_alerts_active_dedup_key`: `(farm_id, COALESCE(zone_id, ''), COALESCE(device_id, camera_id, ''), event_type) WHERE status IN ('OPEN', 'ACKNOWLEDGED')` — atomic domain alert deduplication constraint and lookup.
- `idx_alerts_farm_status_created_at`: `(farm_id, status, created_at DESC)` — active/historical alerts per farm dashboard.
- `idx_alerts_type_status`: `(event_type, status)` — alert type and status filtering.
- `idx_alerts_last_occurred_at`: `(last_occurred_at DESC)` — latest occurrence ordering.
- `idx_alerts_created_at`: `(created_at DESC)` — chronological alert queries.
- `idx_notifications_user_created_at`: `(user_id, created_at DESC)` — user inbox notifications.
- `idx_notifications_alert_created_at`: `(alert_id, created_at DESC)` — notifications associated with an alert.
- `idx_notifications_user_read_at`: `(user_id, read_at)` — unread/read inbox filtering.
- `idx_user_devices_user_enabled`: `(user_id, is_enabled)` — enabled devices lookup per user.
- `user_devices_fcm_token_key`: `(fcm_token)` UNIQUE — token uniqueness and fast device lookup.

---

## 17. Deferred Decisions & Technical Debt

1. **Raw Telemetry Retention Policy**:
   - Production retention (e.g. 30 days vs. 90 days vs. 1 year) is **TBD / Configurable**. Raw telemetry will not be dropped automatically until business SLAs are established. CP9 NiFi aggregations will relieve query pressure from raw historical telemetry.
2. **Transactional Outbox Pattern**:
   - Producer broker outages currently drop events if RabbitMQ is offline during emission. Transactional outbox tables (`outbox_events`) in `iot_db` and `ai_db` are documented as future reliability hardening.
3. **Object Storage for AI Snapshots**:
   - V1 persists snapshots to local filesystem paths. S3/MinIO cloud object storage integration is deferred to post-CP8.
4. **Command Execution TIMEOUT State**:
   - Automatic background transition of unacknowledged commands to `TIMEOUT` remains deferred. The contract currently supports `PENDING`, `PUBLISHED`, `ACKNOWLEDGED`, `COMPLETED`, `FAILED`.
5. **Distributed Cascade Policy**:
   - Deleting a farm or device in Management Service does **not** cascade into `iot_db` or `notification_db`. Historical operational telemetry and audit logs must remain preserved for historical accountability.

---

## 18. CP8 Phased Implementation Roadmap

```text
CP8.0: Data Ownership & Persistence Contract V1  [FROZEN / BASELINE]
  │
  ▼
CP8.1: IoT Service Durable Persistence
  ├── Provision iot_db in PostgreSQL & create schema migrations
  ├── Implement PostgreSQL repositories (telemetry_records, device_commands, device_presence_history transitions)
  └── Retire LegacyIoTAdapter direct SQL read in Management Service (replace with IoT HTTP API contract)
  │
  ▼
CP8.2: AI Service Durable Persistence
  ├── Provision ai_db in PostgreSQL & create schema migrations
  ├── Implement PostgreSQL repositories for CountUpdate & AIEvent
  └── Maintain selective persistence (per-frame DetectionResult remains ephemeral)
  │
  ▼
CP8.3: Notification Service Persistence Audit & Hardening
  ├── Provision notification_db in PostgreSQL & create schema migrations
  ├── Implement PostgreSQL repositories for Alert, Notification, UserDevice
  └── Enforce zero cross-service foreign keys to users/farms
  │
  ▼
CP8.4: Redis Runtime State & Fast Cache
  ├── Implement iot:latest:{deviceId} & current runtime iot:presence:{deviceId} in Redis
  ├── Implement ai:latest:{cameraId} & live ai:runtime:{cameraId} in Redis
  └── Preserve notification:idempotency:{eventId} reliability
  │
  ▼
CP8.5: Cross-Service Persistence Integration E2E
  ├── Service & container restart survival verification for durable PostgreSQL records
  ├── Redis flush recovery verification (cache rebuild vs. live runtime reconstruction vs. idempotency TTL)
  └── 100% regression test verification across all services
```
