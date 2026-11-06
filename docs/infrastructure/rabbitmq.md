# SwiftletCare RabbitMQ Infrastructure & Messaging Topology (CP7.1)

> **TV4 Integration Ownership — RabbitMQ Reference Documentation**  
> Frozen Topology & Infrastructure Contract for Asynchronous Domain Messaging

---

## 1. Purpose & Overview

RabbitMQ serves as the **asynchronous backend message broker** for SwiftletCare. It decouples high-throughput upstream producers (**IoT Service**, **AI Service**) from downstream consumers (**Alert & Notification Service**, **Analytics Service**), enabling:
- Guaranteed at-least-once message delivery.
- Asynchronous task processing independent of HTTP request-response cycles.
- Traffic smoothing and consumer rate-limiting via configurable prefetch.
- Bounded retry loops and Dead Letter Queue (DLQ) forensic isolation for unprocessable payloads.

---

## 2. RabbitMQ vs. MQTT (Separation of Concerns)

A clear distinction is maintained between IoT device telemetry ingestion and backend microservice messaging:

```
[ ESP32 Nodes / Edge Gateways ]
             │
             │ MQTT Protocol (Port 1883, lightweight, low-overhead QoS)
             ▼
      [ EMQX Broker ]
             │
             ▼
      [ IoT Service ] ── (Evaluates thresholds & state transitions)
             │
             │ AMQP Protocol (Port 5672, topic exchange, durable queues)
             ▼
     [ RabbitMQ Broker ]
             │
      ┌──────┴──────┐
      ▼             ▼
[ Notification ] [ Analytics ]
```

| Dimension | MQTT (EMQX) | RabbitMQ (AMQP 0-9-1) |
|---|---|---|
| **Boundary** | Edge Device $\leftrightarrow$ IoT Service | Service $\leftrightarrow$ Service (Backend) |
| **Protocol** | MQTT 3.1.1 / 5.0 | AMQP 0-9-1 |
| **Typical Payload** | Raw sensor telemetry, actuator commands | Domain condition events, alerts, lifecycle triggers |
| **Consumer Pattern**| Wildcard topic subscriptions (e.g. `swiftlet/+/telemetry`) | Durable named queues, dead-letter exchanges, retries |
| **Buffering** | Ephemeral or broker-cached | Persistent, disk-backed named queues |

---

## 3. Topology Specification (Frozen V1)

### A. Exchanges

| Exchange Name | Type | Durable | Auto-Delete | Purpose |
|---|---|:---:|:---:|---|
| `swiftlet.domain.events` | `topic` | `true` | `false` | Canonical domain event exchange for all services. |
| `swiftlet.notification.retry` | `direct` | `true` | `false` | Ingress exchange for transient notification retries. |
| `swiftlet.notification.retry-return` | `direct` | `true` | `false` | Return exchange routing expired retry messages back to main queue. |
| `swiftlet.notification.dlx` | `direct` | `true` | `false` | Dead Letter Exchange for permanently failed notifications. |

### B. Queues & Arguments

| Queue Name | Durable | Arguments | Purpose |
|---|:---:|---|---|
| `notification.alert-events.v1` | `true` | `x-dead-letter-exchange: swiftlet.notification.dlx`<br>`x-dead-letter-routing-key: notification.alert-events.v1.dlq` | Primary ingress queue for Alert & Notification Service. Rejections with `requeue=False` route automatically to DLQ. |
| `notification.alert-events.v1.retry` | `true` | `x-message-ttl: 5000` (configurable)<br>`x-dead-letter-exchange: swiftlet.notification.retry-return`<br>`x-dead-letter-routing-key: notification.alert-events.v1.retry-return` | Holds transiently failed messages until TTL expires, then dead-letters back to main queue. |
| `notification.alert-events.v1.dlq` | `true` | None | Stores permanently rejected / poison messages for SRE forensics. |

### C. Bindings

```text
swiftlet.domain.events (topic)
   ├── "iot.environment.#"    ──→ notification.alert-events.v1
   ├── "iot.audio.#"          ──→ notification.alert-events.v1
   ├── "iot.device.#"         ──→ notification.alert-events.v1
   ├── "iot.command.failed"   ──→ notification.alert-events.v1
   └── "ai.predator.detected" ──→ notification.alert-events.v1

swiftlet.notification.retry (direct)
   └── "notification.alert-events.v1.retry" ──→ notification.alert-events.v1.retry

swiftlet.notification.retry-return (direct)
   └── "notification.alert-events.v1.retry-return" ──→ notification.alert-events.v1

swiftlet.notification.dlx (direct)
   └── "notification.alert-events.v1.dlq" ──→ notification.alert-events.v1.dlq
```

### D. Explicitly Excluded Bindings (Anti-Patterns)
The Notification main queue **must not** bind to:
- `iot.telemetry.#` (High-frequency raw data; belongs to TimescaleDB).
- `ai.count.#` (Bird counting analytics; belongs to Analytics Service).
- `ai.entry.#` / `ai.exit.#` (Flock traffic analytics; belongs to Analytics Service).

---

## 4. Retry & Dead-Letter (DLQ) Architecture

```
                 Incoming Domain Event
                           │
                           ▼
              notification.alert-events.v1 (Main)
                           │
             ┌─────────────┴─────────────┐
        (Success)                   (Failure)
             │                           │
          ACK to broker         Is failure temporary?
                                         │
                         ┌───────────────┴───────────────┐
                     [ YES ]                          [ NO ]
                        │                          (Schema/Poison)
                        ▼                                │
                 Publish to retry                        ▼
          swiftlet.notification.retry             Publish to DLX
                        │                    swiftlet.notification.dlx
                        ▼                                │
         notification.alert-events.v1.retry              ▼
                        │                   notification.alert-events.v1.dlq
                   Wait TTL                              │
                        ▼                           (SRE Manual Audit)
                DLX on expiration
        swiftlet.notification.retry-return
                        │
                        ▼
          notification.alert-events.v1 (Main)
```

### Bounded Retry Metadata (`x-death` vs Application Counter)
When RabbitMQ dead-letters a message due to TTL expiration, it automatically populates the `x-death` array in the message headers:
```json
{
  "x-death": [
    {
      "count": 1,
      "exchange": "swiftlet.notification.retry",
      "queue": "notification.alert-events.v1.retry",
      "reason": "expired",
      "routing-keys": ["notification.alert-events.v1.retry"],
      "time": 1798389073
    }
  ]
}
```
In CP7.5, consumers may inspect `x-death[0].count` or maintain an explicit application header `x-retry-count` to bound retries (e.g. max 3 attempts) before forwarding to `swiftlet.notification.dlx`.

---

## 5. Docker Infrastructure & Networking

### Docker Service Specification (`docker-compose.yml`)
- **Image:** `rabbitmq:3.13-management`
- **Container Name:** `swiftletcare-rabbitmq`
- **Volume:** `swiftletcare_rabbitmq_data` mapped to `/var/lib/rabbitmq` for persistent Mnesia database storage across restarts.
- **Network:** Connected to `swiftletcare-network` (configured as an external Docker network; must be created prior to starting services).
- **Healthcheck:** Executes `rabbitmq-diagnostics -q ping` every 10 seconds.

### Addressing & Connection Strings
- **Host Machine (Local Dev / Tests):**
  `amqp://swiftlet:swiftlet123@localhost:5672/`
- **Container-to-Container (Docker Network):**
  `amqp://swiftlet:swiftlet123@rabbitmq:5672/`
- **Management UI:**
  `http://localhost:15672/` (Default credentials: `swiftlet` / `swiftlet123` via `.env.example`).

---

## 6. Environment Configuration Contract

| Environment Variable | Default | Purpose |
|---|---|---|
| `RABBITMQ_BIND_IP` | `127.0.0.1` | Host interface IP binding for AMQP and HTTP UI (use `0.0.0.0` if LAN access is explicitly required) |
| `RABBITMQ_AMQP_PORT` | `5672` | AMQP port exposed to host |
| `RABBITMQ_MANAGEMENT_PORT`| `15672` | Management HTTP UI / API port |
| `RABBITMQ_DEFAULT_USER` | `swiftlet` | Default administrator username |
| `RABBITMQ_DEFAULT_PASS` | `swiftlet123` | Default administrator password |
| `RABBITMQ_PREFETCH` | `10` | Consumer concurrency buffer setting (conservative dev default) |
| `RABBITMQ_RETRY_TTL_MS` | `5000` | Retry queue message time-to-live in milliseconds |
| `REDIS_BIND_IP` | `127.0.0.1` | Host interface IP binding for Redis (use `0.0.0.0` if LAN access is required) |
| `REDIS_PORT` | `6379` | Redis port exposed to host |

---

## 7. Operational & Verification Procedures

### Prerequisites & Dependencies
- **Broker & Cache:** Docker & Docker Compose v2+.
- **Python Runtime:** Python 3.10+ (Standard library `urllib.request`, `json`, `base64`, `uuid`, `time`, `logging` covers declarator and live verifier; no extra pip packages required for topology bootstrap).
- **Testing:** `pytest>=8.0` for running automated offline/unit test suites.

### Running RabbitMQ & Redis

**Windows (PowerShell):**
```powershell
# Create the external Docker network if it does not already exist
docker network create swiftletcare-network 2>$null

# Start broker and cache in detached mode
docker compose up -d rabbitmq redis

# Check container health status
docker ps --filter "name=swiftletcare-"
```

**Linux / macOS (Bash / Zsh):**
```bash
# Create the external Docker network if it does not already exist
docker network create swiftletcare-network 2>/dev/null || true

# Start broker and cache in detached mode
docker compose up -d rabbitmq redis

# Check container health status
docker ps --filter "name=swiftletcare-"
```

### Applying Topology Idempotently

**Windows (PowerShell):**
```powershell
$env:PYTHONPATH="."
python -c "from infrastructure.rabbitmq.declarator import RabbitMQDeclarator; RabbitMQDeclarator().apply_topology()"
```

**Linux / macOS (Bash / Zsh):**
```bash
PYTHONPATH=. python3 -c "from infrastructure.rabbitmq.declarator import RabbitMQDeclarator; RabbitMQDeclarator().apply_topology()"
```

### Running Automated Offline Topology Tests (No Broker Required)

**Cross-platform:**
```bash
pytest tests/test_rabbitmq_topology_offline.py -v
```

### Running Automated Live Verification Suite (Requires Running Broker)

**Windows (PowerShell):**
```powershell
$env:PYTHONPATH="."
python infrastructure/rabbitmq/verifier.py
```

**Linux / macOS (Bash / Zsh):**
```bash
PYTHONPATH=. python3 infrastructure/rabbitmq/verifier.py
```
This script executes:
1. Main routing verification (`ai.predator.detected` $\rightarrow$ received count = 1).
2. Wildcard routing verification (`iot.environment.high_temperature.started` $\rightarrow$ received count = 1).
3. Negative routing verification (`iot.telemetry.raw`, `ai.count.updated`, `management.user.updated` $\rightarrow$ received count = 0).
4. Retry-Return verification (Message held in retry queue $\rightarrow$ TTL expires $\rightarrow$ routes back to main queue).
5. Inspection of `x-death` metadata.
6. Dead Letter Queue verification (`swiftlet.notification.dlx` $\rightarrow$ `notification.alert-events.v1.dlq`).

---

## 8. Troubleshooting

- **Container fails healthcheck:** Run `docker logs swiftletcare-rabbitmq` to inspect Erlang crash dumps or port collisions on 5672/15672.
- **Messages not routing to main queue:** Verify binding exact match or wildcard (`#`). Inspect exchanges via Management UI: `http://localhost:15672/#/exchanges`.
- **Messages not returning from retry queue:** Ensure `swiftlet.notification.retry-return` exchange exists and `notification.alert-events.v1` has an active binding for routing key `notification.alert-events.v1.retry-return`.
