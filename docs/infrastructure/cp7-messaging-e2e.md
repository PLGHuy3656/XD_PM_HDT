# CP7.6 Cross-Service Messaging End-to-End Verification

## Overview

Checkpoint **CP7.6** validates the complete cross-service messaging backbone V1 connecting **IoT Service**, **AI Service**, and **Notification Service** through RabbitMQ (`swiftlet.domain.events`) and Redis-backed reliability infrastructure.

```text
IoT Service ─────┐
                 │
                 ▼
AI Service ──────┼─► RabbitMQ ──► Notification ──► Alert / Notification
                 │   (topic)      Consumer          Lifecycle
                 │                    │                 │
Redis ───────────┴────────────────────┼─────────────────┼─► FCM Push
(Idempotency / Lock)                  ▼                 ▼
                             Dead-Letter / Retry    WebSocket Broadcast
```

---

## 1. Verified Architecture & Matrix Summary

| Scenario | Path Verified | Producers / Adapters | Consumer & Store | Result |
| :--- | :--- | :--- | :--- | :---: |
| **E2E-01** | IoT High Temperature Started | `TelemetryService` $\to$ `DomainEventPublisher` | `RabbitMQAlertConsumer` + Redis | **PASS** |
| **E2E-02** | Repeated High Temperature Suppressed | IoT Condition Evaluator Dedup | No event emitted | **PASS** |
| **E2E-03** | IoT High Temperature Recovered | `TelemetryService` $\to$ `DomainEventPublisher` | Auto-resolves active Alert | **PASS** |
| **E2E-04** | Audio Fault + Recovery Lifecycle | `TelemetryService` (Audio) | Started $\to$ Dedup $\to$ Auto-resolved | **PASS** |
| **E2E-05** | Device Offline + Online Presence | `PresenceService` | Offline Alert OPEN $\to$ Online RESOLVED | **PASS** |
| **E2E-06** | Actuator Command Failed | `CommandService` | Alert OPEN (manual resolution) | **PASS** |
| **E2E-07** | AI Predator Detection to Alert | `DomainEventPublisherRuntimeSink` | CRITICAL Alert OPEN | **PASS** |
| **E2E-08** | Unknown Camera Metadata Isolation | Metadata Resolver Fallback | Event dropped safely (0 fake IDs) | **PASS** |
| **E2E-09** | Negative RabbitMQ Routing | Exchange topic matching | Raw telemetry & bird counts ignored | **PASS** |
| **E2E-10** | Same `eventId` Redelivery Suppression | Message idempotency | Redis marks `DONE`; 0 mutations | **PASS** |
| **E2E-11** | Different `eventId` Domain Dedup | Alert business deduplication | Increments `occurrence_count` (1 $\to$ 2) | **PASS** |
| **E2E-12** | Notification Restart Idempotency | Consumer instance replacement | Redis state survives; 0 duplicates | **PASS** |
| **E2E-13** | RabbitMQ Restart & Reconnect | Broker container bounce | Consumer recovers and processes | **PASS** |
| **E2E-14** | Redis Outage Behavior | Redis fail-fast check | Strictly raises, safe `nack(requeue=True)` | **PASS** |
| **E2E-15** | Bounded Delayed Retry via TTL | Retry Exchange & Queue | Attempt 1 fails $\to$ 5s TTL $\to$ Attempt 2 PASS | **PASS** |
| **E2E-16** | Malformed Message to DLQ | DLX Routing & Non-blocking | Malformed $\to$ DLQ; valid processed cleanly | **PASS** |
| **E2E-17** | FCM Push Notification Adapter | FCM Provider | Tokens and message payload verified | **PASS** |
| **E2E-18** | WebSocket Realtime Broadcast | `NotificationDomainEventSink` | Broadcasts created & updated events | **PASS** |
| **E2E-19** | Producer Broker Outage Limitation | Producer connection failure | Drops event (no transactional outbox) | **PASS** |
| **E2E-20** | Full Suite Regression | Pytest across all 5 modules | 483 passed, 0 failed, 0 skipped | **PASS** |

---

## 2. Live vs Simulated Components

### Live Components Under Test
1. **RabbitMQ Broker**: Real Docker container (`swiftletcare-rabbitmq`) running RabbitMQ 3.13 with Management plugin.
2. **Redis Service**: Real Docker container (`swiftletcare-redis`) running Redis 7 for distributed idempotency locking and message status tracking.
3. **AMQP Exchanges & Queues**: Real durable topic exchange `swiftlet.domain.events`, queues `notification.alert-events.v1`, `notification.alert-events.v1.retry`, and `notification.alert-events.v1.dlq`.
4. **IoT Application Pipeline**: Real IoT domain services (`TelemetryService`, `PresenceService`, `CommandService`, `DomainEventPublisher`) executing in isolated python runtime.
5. **AI Application Pipeline**: Real AI adapter (`DomainEventPublisherRuntimeSink`, `InMemoryCameraMetadataResolver`, `RabbitMQEventPublisher`) executing in isolated computer vision runtime.
6. **Notification Consumer**: Real `RabbitMQAlertConsumer` with asynchronous aio-pika loop, deserializer, mapper, and Redis-backed state machine.

### Simulated External Boundaries
- **ESP32 Hardware & MQTT Broker**: Telemetry and commands are driven into IoT application service methods rather than physical ESP32 flash over Wi-Fi.
- **RTSP Video Feeds**: Frame events are injected into the AI `DomainEventPublisherRuntimeSink` rather than streaming from physical RTSP cameras.
- **Google FCM Gateway**: Simulated with `FakeFCMProvider` capturing token delivery requests and verifying payload schema without calling external Google servers.

---

## 3. Reliability & Delivery Semantics

- **Guarantee**: **At-least-once delivery architecture** with **at-least-once processing idempotency** at the consumer.
- **Message Idempotency**: Tracked via `eventId` (UUID) with Redis atomic `SET NX` (`CLAIMED` $\to$ `DONE`).
- **Alert Deduplication**: High-level domain concept based on `(farm_id, device_id/camera_id, event_type, status=OPEN)`.
- **Fault Tolerance**:
  - Redis outage halts consumption safely via `nack(requeue=True)` to avoid unsafe duplicate execution.
  - Poison messages (malformed JSON, invalid schema) are rejected with `requeue=False` and routed to DLQ.
  - Transient processing exceptions route to `notification.alert-events.v1.retry` with a 5000ms TTL delay before retry.

---

## 4. Known Technical Debt & Future Scope

1. **Transactional Outbox Missing in Producers**: If RabbitMQ is unavailable when an IoT or AI condition transition occurs, the event is logged as failed and dropped. A transactional outbox pattern in MongoDB/PostgreSQL will be required for mission-critical audit trails in future milestones.
2. **FCM Retry Queue**: FCM network transport failures currently log an error without a dedicated dead-lettering mechanism for external push delivery.
3. **Cluster-Wide Idempotency Locks**: Redlock algorithm can be adopted if multi-master Redis cluster replication is introduced.
