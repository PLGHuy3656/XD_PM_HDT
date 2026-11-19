# Notification Service RabbitMQ Consumer Adapter V1 (CP7.4)

## 1. Overview & Architecture Boundary

The Notification Service RabbitMQ Consumer Adapter connects `notification-service` to the asynchronous message broker topology declared in CP7.1 (`swiftlet.domain.events` exchange and `notification.alert-events.v1` queue).

```
RabbitMQ Broker
   │
   │ delivery
   ▼
[notification.alert-events.v1]
   │
   ▼
RabbitMQAlertConsumer (Infrastructure Input Adapter)
   │  - Message prefetch & deserialization
   │  - Canonical envelope schema validation (v1.0)
   │  - Producer authorization verification
   │  - Transport idempotency check (eventId store)
   ▼
EventMapper (Translation Layer)
   │  - Translates canonical payload to typed input DTOs
   ▼
NotificationService (Application Facade / Seam)
   │
   ├── AlertRuleEngine (Evaluates hysteresis & thresholds)
   ├── AlertLifecycleService (OPEN -> ACKNOWLEDGED -> RESOLVED)
   ├── RecipientResolver (Resolves users by farm/roles)
   ├── NotificationRepository / AlertRepository (Persistence)
   ├── WebSocketSink (Realtime in-app delivery via WebSocket)
   └── FCMProvider (Push delivery via Firebase Cloud Messaging)
   │
   ▼
RabbitMQ ACK (Acknowledged ONLY after domain processing completes)
```

### Core Architecture Axioms

1. **RabbitMQ Consumer = Infrastructure Input Adapter $\ne$ AlertRuleEngine**:
   - The consumer adapter is strictly an ingress transport component.
   - It contains zero domain business logic, threshold values, or lifecycle transition rules.
   - It delegates all business actions directly to the existing `NotificationService` application seam (`handle_condition_transition`, `handle_ai_event`, `handle_presence_event`, `handle_command_event`).
2. **Alert Deduplication $\ne$ Message Idempotency**:
   - **Message Idempotency (Transport Level)**: If the exact same message (`eventId=111`) is redelivered (due to network retries, broker rebalance, unacknowledged socket drop), the consumer detects `idempotency_store.has_processed("111")` and immediately ACKs the message. It does NOT increment `occurrence_count`, create an Alert, create a Notification, or dispatch an FCM push.
   - **Alert Deduplication (Domain Level)**: If two separate, genuine domain occurrences happen (`eventId=222` and `eventId=333`) for the same active condition (e.g., continuous high temperature above 31°C before recovery), `AlertLifecycleService` matches the active alert by `dedup_key`, increments `occurrence_count` (1 $\to$ 2), and updates `last_occurred_at`.
3. **ACK $\ne$ Publisher Confirm**:
   - **Publisher Confirm** is sent by RabbitMQ to the upstream producer (`iot-service`, `ai-service`) to confirm that the broker has received and routed/persisted the published message.
   - **Consumer ACK** is sent by `notification-service` back to the broker to confirm that the message was received and successfully handled by the application layer.
   - ACKs occur ONLY after successful domain processing.
4. **Retry Queue $\ne$ DLQ**:
   - **Retry Queue (`notification.alert-events.v1.retry`)**: A queue configured with TTL (`x-message-ttl: 5000ms`) and dead-letter return exchange for temporary, retryable failures (e.g., downstream database lock or transient service unavailability).
   - **Dead Letter Queue (`notification.alert-events.v1.dlq`)**: A permanent sink for poison/fatal messages that cannot be processed (malformed JSON, invalid canonical envelope, unsupported `eventVersion != '1.0'`, unauthorized producer mismatch, missing mandatory payload IDs). Permanent errors are rejected with `requeue=False`.
5. **FCM SENT $\ne$ DELIVERED**:
   - `FCM SENT` indicates that Firebase Cloud Messaging accepted the multicast push HTTP request from the backend and returned a message ID.
   - It does NOT guarantee that the mobile handset received or displayed the push notification (user may be offline, battery-saver restricted, or notifications disabled).
6. **No Exactly-Once Delivery Guarantee**:
   - The distributed messaging architecture guarantees **at-least-once delivery** combined with **idempotent consumer processing**.
   - Exactly-once delivery is impossible across distributed AMQP networks; duplicate messages can and will occur.

---

## 2. Ingress Topology & Routing Keys

The consumer binds to `notification.alert-events.v1` which receives events routed from `swiftlet.domain.events`:

| Routing Key Pattern | Producer | Event Type Description | Application Seam Handler |
|---|---|---|---|
| `iot.environment.high_temperature.started` | `iot-service` | High temperature breached threshold | `handle_condition_transition` |
| `iot.environment.high_temperature.recovered` | `iot-service` | Temperature normalized | `handle_condition_transition` |
| `iot.environment.low_temperature.started` | `iot-service` | Low temperature breached threshold | `handle_condition_transition` |
| `iot.environment.low_temperature.recovered` | `iot-service` | Temperature normalized | `handle_condition_transition` |
| `iot.environment.high_humidity.started` | `iot-service` | High humidity breached threshold | `handle_condition_transition` |
| `iot.environment.high_humidity.recovered` | `iot-service` | Humidity normalized | `handle_condition_transition` |
| `iot.environment.low_humidity.started` | `iot-service` | Low humidity breached threshold | `handle_condition_transition` |
| `iot.environment.low_humidity.recovered` | `iot-service` | Humidity normalized | `handle_condition_transition` |
| `iot.audio.fault.started` | `iot-service` | Audio subsystem hardware fault | `handle_condition_transition` |
| `iot.audio.fault.recovered` | `iot-service` | Audio subsystem returned to healthy | `handle_condition_transition` |
| `iot.device.offline` | `iot-service` | Device heartbeat timed out | `handle_presence_event` |
| `iot.device.online` | `iot-service` | Device reconnected | `handle_presence_event` |
| `iot.command.failed` | `iot-service` | Actuator command execution failure | `handle_command_event` |
| `ai.predator.detected` | `ai-service` | Confirmed predator (rat/snake) detection | `handle_ai_event` |

### Excluded Event Types
- Raw telemetry (`iot.telemetry.*`) is never consumed by Notification Service.
- Non-predator AI events (`ai.count.*`, `ai.entry.*`, `ai.exit.*`, swiftlet-only detections) are never consumed by Notification Service.

---

## 3. Envelope Validation & Security Policy

All messages delivered to the queue must conform to the canonical JSON envelope:

```json
{
  "eventId": "UUIDv4",
  "eventType": "string",
  "eventVersion": "1.0",
  "occurredAt": "ISO-8601 UTC timestamp",
  "producer": "iot-service | ai-service",
  "correlationId": "optional string",
  "payload": { ... }
}
```

### Rejection & Error Rules:
1. **Malformed JSON**: Reject with `requeue=False` (routes to DLQ, avoids poison loop).
2. **Missing required envelope fields**: Reject with `requeue=False`.
3. **Unsupported eventVersion**: Only `eventVersion == "1.0"` is accepted; others rejected with `requeue=False`.
4. **Producer Mismatch**:
   - `ai.predator.detected` MUST originate from `ai-service`.
   - `iot.*` MUST originate from `iot-service`.
   - Mismatches are rejected with `requeue=False` as unauthorized.
5. **Missing Mandatory Payload Keys**:
   - `farmId` and `deviceId`/`cameraId` missing $\to$ rejected with `requeue=False`.

---

## 4. CP7.5 Reliable Ingress Architecture (Durable Idempotency + Bounded Retry + DLQ)

### A. Durable Message Idempotency with Redis
CP7.5 replaces ephemeral memory tracking with `RedisIdempotencyStore` (with graceful fallback to `InMemoryIdempotencyStore` in test/isolated environments):
- **Atomic Claim**: Consumers execute `SET swiftlet:notification:event_claim:<eventId> "PROCESSING" NX EX <claim_ttl>` before beginning domain operations.
  - Returns `True`: Consumer successfully obtained the processing lease.
  - Returns `False`: Message is either currently being processed by another consumer or has already completed.
- **Completion State**: Upon successful domain processing, the consumer records `SET swiftlet:notification:event_claim:<eventId> "DONE" XX KEEPTTL` (or refreshes with standard 24h retention `retention_ttl_seconds`).
- **Release on Transient Failure**: If processing fails due to a retryable error, the consumer executes `release_claim(event_id)` (deleting the `"PROCESSING"` key) so subsequent retry deliveries can re-claim the lease immediately without waiting for `claim_ttl` expiration.
- **Cross-Process Survival**: Redis guarantees that duplicate redeliveries (`eventId=111`) are suppressed even after complete Notification Service pod restarts, broker reconnection, or across multiple horizontally-scaled consumer replicas.

### B. Bounded Delayed Retry Architecture
- **No Poison Loops**: Replaces unbounded `requeue=True` with bounded delayed retries routed through RabbitMQ.
- **Header Tracking**: Retries are tracked via the `x-retry-count` message header (default max: 3 attempts).
- **Delayed Return Mechanism**:
  1. On temporary error (e.g. database transient failure), consumer increments `x-retry-count`.
  2. Consumer publishes message to direct exchange `swiftlet.notification.retry` with routing key `notification.alert-events.v1.retry`.
  3. The retry queue holds the message for `x-message-ttl: 5000` (5000ms delay).
  4. On expiration, RabbitMQ DLX routes the message via `swiftlet.notification.retry-return` back to `notification.alert-events.v1` for reprocessing.
- **Retry Exhaustion**: Once `x-retry-count >= RABBITMQ_MAX_RETRIES`, the message is published directly to `swiftlet.notification.dlx` with routing key `notification.alert-events.v1.dlq` for operator investigation.

### C. Dead Letter Queue (DLQ) Topology
The main ingress queue `notification.alert-events.v1` is configured with broker-level DLX arguments:
- `x-dead-letter-exchange: "swiftlet.notification.dlx"`
- `x-dead-letter-routing-key: "notification.alert-events.v1.dlq"`

Permanent errors (malformed JSON, invalid canonical envelope, unsupported `eventVersion != '1.0'`, unauthorized producer mismatch, missing mandatory IDs) are rejected via `reject(requeue=False)` and automatically diverted by RabbitMQ into `notification.alert-events.v1.dlq`.

### D. Publish-then-ACK Safety
When republishing messages to the retry exchange or DLX, the consumer strictly adheres to **Publish-then-ACK safety**:
1. Open a publisher-confirms channel to RabbitMQ.
2. Publish the updated message with headers (`x-retry-count`, `x-original-queue`, `x-error-reason`).
3. Await publisher confirmation from the broker.
4. **ONLY AFTER** confirmation is received from RabbitMQ, call `message.ack()` on the original message.
This guarantees zero message loss even if a crash occurs during republishing.

### E. Crash Windows and Delivery Semantics
- **At-Least-Once Delivery**: The messaging pipeline provides guaranteed at-least-once delivery.
- **Crash Window 1 (Crash during domain processing)**: The Redis claim remains in `"PROCESSING"` state until `claim_ttl` (default 60s) expires. Upon timeout, redelivered message can be re-claimed.
- **Crash Window 2 (Crash after publish confirmation but before original message ACK)**: RabbitMQ re-delivers the original unacknowledged message. The consumer checks Redis, finds `"PROCESSING"` or `"DONE"`, and safely drops/ACKs the duplicate without double-executing side-effects.
- **Producer Outbox Limitation**: Upstream producers (`iot-service`, `ai-service`) publish directly to RabbitMQ using publisher confirms but do not currently persist to a transactional outbox table. If the broker is unreachable during domain publishing, messages are logged and dropped upstream. Full transactional outbox belongs to subsequent checkpoints.
