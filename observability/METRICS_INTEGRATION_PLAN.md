# SWIFTLETCARE — OBSERVABILITY METRICS INTEGRATION PLAN
**Module:** CP10-A / CP10-B (Observability Foundation)  
**Status:** DRAFT SPECIFICATION (NO SERVICE CODE MODIFIED IN CP10-A)  
**Target:** Expose `/metrics` on all FastAPI microservices for Prometheus scraping.

---

## 1. Service Ownership Matrix

Per [`TEAM_TASK_CHECKLIST.md`](../docs/planning/TEAM_TASK_CHECKLIST.md), backend microservices belong to specific team members:

| Service | Port | Primary Owner | Module ID | Entrypoint Path |
| :--- | :---: | :---: | :---: | :--- |
| **API Gateway** | `8000` | **TV2** | B1 | `gateway/app/main.py` |
| **Management Service** | `8001` | **TV2** | B2, B3 | `services/management-service/app/main.py` |
| **IoT Service** | `8002` | **TV2** | B4, B5 | `services/iot-service/app/main.py` |
| **AI Service** | `8003` | **TV4** | B6, C1..C6 | `services/ai-service/app/main.py` |
| **Notification Service** | `8004` | **TV2** | B7 | `services/notification-service/app/main.py` |
| **Analytics Service** | `8005` | **TV2** | B8 | `services/analytics-service/app/main.py` |

> **Constraint Compliance:** During CP10-A, **no service code was modified**. All services remain intact to preserve code stability and team boundaries.

---

## 2. Standardized Instrumentator Specification

All services are built with **FastAPI**. The team standard for metrics instrumentation is **`prometheus-fastapi-instrumentator`** (clean, zero-boilerplate, asynchronous).

### 2.1. Dependency Specification
Add to each service's `requirements.txt`:
```
prometheus-fastapi-instrumentator>=7.0.0,<8.0.0
```

### 2.2. Standard 3-Line Integration Snippet
Each service owner adds the following to their `app/main.py`:

```python
from prometheus_fastapi_instrumentator import Instrumentator

# After app = FastAPI(...)
Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=False,
    excluded_handlers=["/metrics", "/health", "/docs", "/openapi.json"]
).instrument(app).expose(app, endpoint="/metrics")
```

---

## 3. Emitted Metrics & Dashboard Mapping

When instrumented, the `/metrics` endpoint automatically provides standard Prometheus metrics that map directly to the `SwiftletCare - Service Overview` Grafana dashboard:

| Prometheus Metric Name | Metric Type | Labels | Dashboard Panel |
| :--- | :--- | :--- | :--- |
| `up` | Gauge (Built-in) | `job`, `instance`, `tier` | **Microservices Health Status (1=UP, 0=DOWN)** |
| `http_requests_total` | Counter | `job`, `method`, `status`, `handler` | **Request Rate (Throughput req/s)** |
| `http_requests_total{status=~"5.."}` | Counter | `job`, `status` | **Error Rate (HTTP 5xx %)** |
| `http_request_duration_highr_seconds_bucket` | Histogram | `job`, `le` | **Duration (p95 Latency seconds)** |

---

## 4. Rollout Steps for CP10-B (When Approved)

1. **Step 1:** Owners (TV2 and TV4) review and merge the 3-line instrumentator snippet in their respective services.
2. **Step 2:** Start monitoring containers using the standalone compose file:
   ```bash
   docker compose -f observability/docker-compose.monitoring.yml up -d
   ```
3. **Step 3:** Open Prometheus at `http://localhost:9090/targets` to verify all 6 service targets transition to state `UP`.
4. **Step 4:** Open Grafana at `http://localhost:3000` (login `admin` / `admin`) to view the live `SwiftletCare - Service Overview` dashboard.
