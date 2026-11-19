# IoT Service — RabbitMQ Domain Event Producer Architecture (CP7.2)

> **TV1 SERVICE REFERENCE IMPLEMENTATION • LOCAL INTEGRATION VALIDATION ONLY • DO NOT PUSH FROM TV4**

---

## 1. Architectural Role & Boundary Separation

The SwiftletCare IoT Service acts as the gateway between physical hardware edge nodes (ESP32) and backend microservices (Notification, AI, Management):

```text
┌─────────────────┐
│ ESP32 Field Node│
└────────┬────────┘
         │ MQTT (JSON Telemetry, Heartbeats, Status LWT, ACKs)
         ▼
┌────────────────────────────────────────────────────────┐
│                      IoT Service                       │
│                                                        │
│  Ingestion & Presence & Command Tracking               │
│  Stateful Condition Evaluator (Hysteresis Deadband)    │
│  DeviceMetadataResolver (Farm/Zone Business Context)   │
└────────────────────────┬───────────────────────────────┘
                         │ DomainEventPublisher Port
                         │ (RabbitMQEventPublisher Adapter)
                         ▼
             swiftlet.domain.events (Topic Exchange)
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
notification.alert-events.v1   (Future AI)   (Future Management)
```

### Key Transport Distinctions:
- **MQTT (`swiftlet/*`)**: Device-to-Cloud bidirectional transport between field nodes and IoT Service.
- **RabbitMQ (`swiftlet.domain.events`)**: Cloud-internal asynchronous domain event publication from IoT Service to downstream backend consumers.

---

## 2. Core Rule: Telemetry ≠ Domain Event

Raw IoT telemetry samples are **never** published directly to RabbitMQ notification queues. 

```text
WRONG:
Telemetry (every 5s) ──> RabbitMQ ──> Flood Notification Service & Push FCM

CORRECT:
Telemetry (every 5s) ──> IoT Condition Evaluator
                             │
                             ├── Condition unchanged? ──> NO EVENT PUBLISHED
                             │
                             └── State transition?
                                   ├── INACTIVE -> ACTIVE  ──> Publish *.started event once
                                   └── ACTIVE -> INACTIVE  ──> Publish *.recovered event once
```

---

## 3. Condition Evaluator & Hysteresis

To eliminate threshold flapping around boundary values, the IoT Condition Evaluator enforces hysteresis deadbands:

| Condition | Threshold | Deadband | Trigger Criterion | Recovery Criterion |
| :--- | :---: | :---: | :--- | :--- |
| **High Temperature** | $31.0^\circ\text{C}$ | $0.5^\circ\text{C}$ | $\text{Temp} \ge 31.0^\circ\text{C}$ | $\text{Temp} \le 30.5^\circ\text{C}$ |
| **Low Temperature** | $25.0^\circ\text{C}$ | $0.5^\circ\text{C}$ | $\text{Temp} \le 25.0^\circ\text{C}$ | $\text{Temp} \ge 25.5^\circ\text{C}$ |
| **High Humidity** | $85.0\%$ | $2.0\%$ | $\text{Hum} \ge 85.0\%$ | $\text{Hum} \le 83.0\%$ |
| **Low Humidity** | $65.0\%$ | $2.0\%$ | $\text{Hum} \le 65.0\%$ | $\text{Hum} \ge 67.0\%$ |
| **Audio Fault** | Boolean | N/A | $\text{audioHealthy: } \text{true} \to \text{false}$ | $\text{audioHealthy: } \text{false} \to \text{true}$ |

---

## 4. Presence & Command Event Transitions

- **Presence Transitions**:
  - `ONLINE -> OFFLINE` (via explicit offline MQTT status or LWT broker disconnect): Emits `iot.device.offline` once.
  - `OFFLINE -> ONLINE` (via status or first heartbeat after offline): Emits `iot.device.online` once.
  - Periodic heartbeats while `ONLINE` do **not** generate RabbitMQ events.
- **Command Failures**:
  - Only genuine terminal failures (`MQTT publish failure` or device `ACK status: FAILED / ERROR`) emit `iot.command.failed` once.
  - States `PENDING`, `PUBLISHED`, and `SUCCESS` produce no alert events.
  - Subsequent success does not retroactively "recover" a past command failure.

---

## 5. Canonical Event Envelope V1

All events emitted to `swiftlet.domain.events` conform to the frozen CP7 canonical envelope:

```json
{
  "eventId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "eventType": "iot.environment.high_temperature.started",
  "eventVersion": "1.0",
  "occurredAt": "2026-10-28T00:30:00.000Z",
  "producer": "iot-service",
  "correlationId": null,
  "payload": {
    "farmId": "FARM-01",
    "zoneId": "ZONE-01",
    "deviceId": "SWC-NODE-001",
    "metric": "temperature",
    "value": 32.1,
    "threshold": 31.0,
    "unit": "C"
  }
}
```

Field naming rules:
- `eventId`: Unique UUIDv4.
- `eventType`: Canonical routing key string.
- `eventVersion`: Constant `"1.0"`.
- `occurredAt`: ISO-8601 UTC timestamp.
- `producer`: Constant `"iot-service"`.
- `correlationId`: Null for spontaneous environmental events; command UUID for command failure events.
- `payload`: Structured domain payload including business context (`farmId`, `zoneId`, `deviceId`).

---

## 6. Publisher Confirms vs. Consumer ACKs

| Semantic | Publisher Confirm | Consumer ACK |
| :--- | :--- | :--- |
| **Origin** | RabbitMQ Broker $\to$ IoT Service | Notification Service $\to$ RabbitMQ Broker |
| **Meaning** | Broker has accepted and routed/persisted message | Consumer has successfully processed domain alert |
| **Ownership** | **CP7.2 (IoT Service)** | Future CP7.3 (Notification Service) |

---

## 7. Configuration & Isolation Mode

IoT Service can run in complete isolation without RabbitMQ:
```env
# Disabled mode (unit tests and standalone local demo)
RABBITMQ_ENABLED=false

# Production / Integration mode
RABBITMQ_ENABLED=true
RABBITMQ_HOST=127.0.0.1
RABBITMQ_PORT=5672
RABBITMQ_USER=swiftlet
RABBITMQ_PASSWORD=swiftlet123
RABBITMQ_VHOST=/
RABBITMQ_EXCHANGE=swiftlet.domain.events
```
When `RABBITMQ_ENABLED=false`, the service utilizes `NoOpDomainEventPublisher`, completely avoiding broker connections.

---

## 8. Documented Reliability Limitations

1. **Lack of Transactional Outbox**:
   Publisher confirms guarantee that RabbitMQ accepted the message once `publish` succeeds. However, without a database-backed Transactional Outbox, if RabbitMQ crashes between the IoT state update and the AMQP publish, the event may be dropped.
2. **At-Least-Once Delivery**:
   Reconnection logic may redeliver events in partial failure scenarios. Downstream consumers (Notification Service) must rely on message idempotency (`eventId`).
