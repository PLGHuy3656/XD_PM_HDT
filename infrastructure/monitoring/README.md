# SwiftletCare Centralized Monitoring & Observability Stack (CP10)

## Overview
This directory contains the localized Prometheus, Grafana, Loki, and Promtail monitoring infrastructure for the SwiftletCare microservice ecosystem.

Designed under the **LOCAL-FIRST** principle:
- Zero cloud/external dependencies.
- Strict container memory limits (`mem_limit: 256m` for Prometheus/Grafana/Loki, `128m` for Promtail) to protect host memory.
- Binds all web UIs exclusively to `127.0.0.1` (`localhost`).
- Connects directly to `swiftletcare-network` to scrape container services (e.g. RabbitMQ) while reaching host services via `host.docker.internal`.

---

## Architecture Components

| Component | Image | Port | Description |
|-----------|-------|------|-------------|
| **Prometheus** | `prom/prometheus:v2.51.0` | `127.0.0.1:9090` | Time-series metrics collection and evaluation engine. |
| **Grafana** | `grafana/grafana:10.4.0` | `127.0.0.1:3000` | Analytics visualization and alerting UI (anonymous view-only access enabled). |
| **Loki** | `grafana/loki:2.9.5` | `127.0.0.1:3100` | Log aggregation engine. |
| **Promtail** | `grafana/promtail:2.9.5` | internal:9080 | Log shipping agent. |

---

## Directory Structure

```
infrastructure/monitoring/
├── docker-compose.monitoring.yml     # Isolated Docker Compose stack
├── README.md                          # Architecture and operational guide
├── prometheus/
│   ├── prometheus.yml                 # Target scrape configurations
│   └── rules/
│       └── alerts.yml                 # Alert definitions (ServiceDown, ErrorRate, Latency)
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/
│   │   │   └── datasources.yml        # Auto-provisioned Prometheus & Loki
│   │   └── dashboards/
│   │       └── dashboards.yml         # Auto-provisioned dashboard loader
│   └── dashboards/
│       ├── swiftletcare-system-overview.json            # Dashboard 1: System KPI & Service Health
│       └── swiftletcare-microservices-performance.json  # Dashboard 2: Deep dive per service
└── loki/
    ├── loki-config.yml                # Local single-binary Loki configuration
    └── promtail-config.yml            # Promtail log shipping configuration
```

---

## Target Services Monitored

| Target | Scrape Endpoint | Port | Ownership | Method |
|--------|-----------------|------|-----------|--------|
| **Prometheus** | `/metrics` | `9090` | TV4 (Infra) | Native internal |
| **API Gateway** | `/metrics` | `8000` | TV4 (Edge) | `prometheus-fastapi-instrumentator` |
| **Management Service** | `/metrics` | `8001` | TV1 (Core) | `prometheus-fastapi-instrumentator` |
| **IoT Service** | `/metrics` | `8002` | TV1 (IoT) | `prometheus-fastapi-instrumentator` |
| **AI Service** | `/metrics` | `8003` | TV4 (AI) | `prometheus-fastapi-instrumentator` |
| **Analytics Service** | `/metrics` | `8005` | TV3/TV4 (Analytics) | `prometheus-fastapi-instrumentator` |
| **RabbitMQ** | `/metrics` | `15692` | TV4 (Infra) | `rabbitmq_prometheus` plugin |

---

## Alerts Configured

1. `ServiceDown`: Triggers when `up == 0` for 1 minute (Severity: `critical`).
2. `HighHttpErrorRate`: Triggers when HTTP 5xx responses exceed 5% of total requests over 5 minutes (Severity: `warning`).
3. `SlowResponseLatency`: Triggers when p95 response latency exceeds 2.0 seconds over 5 minutes (Severity: `warning`).

---

## Running the Monitoring Stack

### Start Stack
```bash
docker compose -f infrastructure/monitoring/docker-compose.monitoring.yml up -d
```

### Stop Stack
```bash
docker compose -f infrastructure/monitoring/docker-compose.monitoring.yml down
```

### Accessing Dashboards
- **Grafana**: Open http://127.0.0.1:3000 (Default login: `admin` / `swiftletcare_admin` or view anonymously).
  - Open **Dashboards** > **SwiftletCare - System Overview**
  - Open **Dashboards** > **SwiftletCare - Microservices Performance**
- **Prometheus Targets & Alerts**: Open http://127.0.0.1:9090/targets and http://127.0.0.1:9090/alerts
