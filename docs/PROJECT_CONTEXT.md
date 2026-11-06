# NestMate — Current Project Context

> Context for developers and AI coding assistants.
>
> This file records current project decisions, development state, and working rules.
> It does NOT replace `README.md`, SRS, or `FRONTEND_CONVENTIONS.md`.
>
> Before modifying frontend code, read:
> 1. `docs/PROJECT_CONTEXT.md`
> 2. `docs/FRONTEND_CONVENTIONS.md`
> 3. Relevant current source code

---

## 1. Current Scope

NestMate currently has three primary actors:

- `FARM_OWNER`
- `TECHNICIAN`
- `ADMIN`

Do not automatically reintroduce actors found in older documents or the reference project, such as:

- Sales Staff
- Buyer
- Marketplace user
- Operator

Any scope expansion requires explicit team approval.

### Farm Owner

Current functional scope:

- Dashboard
- Farm Management
- Environment Monitoring & Control
- Devices
- Swiftlet / AI Monitoring
- Alerts
- Analytics / Yield
- Account Settings

### Technician

Current target navigation:

- Dashboard
- Environment
- Devices
- Installation
- Diagnostics
- Alerts
- Account Settings

Technician does **not** own farms.

Administrator assigns Technician to farms. Technician works within assigned Farm/Zone scope.

### Administrator

Current implemented navigation and responsibility scope:

- Dashboard (`/admin/dashboard`)
- Người dùng (`/admin/users`) — User and access management
- Nhà yến (`/admin/farms`) — Farm administration & Technician ↔ Farm assignment
- Thiết bị (`/admin/devices`) — Read-only system-wide device registry & provisioning overview
- Hệ thống (`/admin/system`) — System health overview, default thresholds, and Audit Log (kept inside System)

---

## 2. Important Domain Decisions

### Canonical Farm & Device Data

Canonical Farms in frontend mock data:

- `farm-binh-an` — **Nhà yến Bình An** (`NM-BA-01`)
- `farm-phu-an` — **Nhà yến Phú An** (`NM-PA-02`)

Canonical device location:

- `ESP32-CTRL-04` → **Nhà yến Phú An** → **Khu vực D**

### Technician ↔ Farm Assignment

Assigned Farm is a shared Technician context, not a separate sidebar module.

Canonical relationship:

- `Technician -> 0..N Farms`
- `Farm -> 1 primary Technician when operational`

Administrator assigns Technician to one or more farms. Do not convert this relationship to many-to-many.

Technician should be able to:

- know which farms are currently assigned;
- select/use assigned Farm context where required;
- receive notification when an assignment changes;
- access only authorized farms.

Farm Owner can view the Technician supporting a farm, including:

- name;
- contact information;
- assignment/support status.

---

### Technician Environment

Technician Environment exists primarily for technical diagnosis.

It may expose:

- temperature;
- humidity;
- CO₂;
- light;
- telemetry state;
- node/controller information;
- technical notes.

It must NOT become a duplicate of Farm Owner Environment Control.

Manual technical actions remain subject to backend authorization.

---

### Technician Alerts

Technician Alerts contains two functional groups.

#### Technical Alerts

Examples:

- Node disconnected
- Sensor timeout
- MQTT/connectivity issue
- Abnormal sensor reading
- Actuator failure

#### Work Requests

Requests may come from:

- Farm Owner
- Administrator

Typical workflow:

`NEW → IN_PROGRESS → DONE`

Work requests may include Farm, Zone, sender, priority, status, description, and technical context.

---

### Installation

Installation is a dedicated Technician module.

Its direction includes:

- Farm/Zone selection;
- device registration;
- device activation;
- sensor/node configuration;
- connectivity verification;
- installation validation.

Exact workflow must be checked against requirements and the reference project before implementation.

---

### OTA / Maintenance / Tickets

The reference project contains richer modules such as:

- OTA
- Maintenance
- Tickets / SLA / Chat

These are **not current primary NestMate modules**.

Do not add them to navigation or implementation without approval.

---

## 3. Current Technical Decisions

### Current Implementation (Verified in Repository)

- **Frontend (`frontend/`):** React, Vite, React Router, Plain CSS (three-role UI for `FARM_OWNER`, `TECHNICIAN`, `ADMIN`).
- **Backend (`swiftletcare-backend/`):** Python + FastAPI (`fastapi[standard]`, `pydantic-settings`, `python-dotenv`).
- **Database:** PostgreSQL (Supabase-compatible) accessed via `psycopg` v3 (`psycopg[binary]`) with `Jsonb`.
- **IoT / MQTT:**
  - Embedded Firmware (`firmware/esp32/`): ESP32 with Arduino / FreeRTOS dual-core, DHT22 + sensor modules, local Hysteresis AUTO/MANUAL control, `PubSubClient`.
  - Backend MQTT Subscriber (`swiftletcare-backend/app/telemetry.py`): Python `paho-mqtt`.
- **AI Vision Pipeline (`ai-pipeline/`):** Python, YOLO26 (`ultralytics`) + ByteTrack + `CentroidTracker` fallback, Virtual Line entry/exit counting, predator detection, JSONL/HTTP/MQTT publishers.

### Planned / Target Course Architecture (Not Yet Integrated in Repository)

The following technologies remain part of the target course architecture and must be distinguished from currently operational services:

- **Redis Cache** — Caching and real-time state layer
- **Firebase Cloud Messaging (FCM)** — Push notifications
- **Apache NiFi** — IoT data flow orchestration and synchronization
- **Microservices** — Multi-service decomposition for domain modules
- **API Gateway** — Centralized routing and access gateway
- **Docker** — Containerized deployment and orchestration
- **OpenAPI / Swagger** — Full domain REST API documentation (beyond initial FastAPI `/health` and `/mqtt/status` endpoints)
- **Audio AI & Mobile (React Native)** — Planned multi-modal audio anomaly pipeline and mobile client

Older documentation may contain legacy assumptions such as Node.js/NestJS, Express, MongoDB, Tailwind, YOLOv8, YOLOv10, or additional actors. Do not present unimplemented services or replaced stack items (such as MongoDB or Node.js/NestJS) as currently running in the repository.

### Remaining Integration Technical Debt (Backend / Integration Phase)

1. **MQTT Topic & Payload Contract Alignment:**
   - `firmware/esp32/sketch.ino` currently publishes to `swiftlet/telemetry/swc-h01-f01-node01` (3 segments) with fields `temp`, `soundOk`, `wifiRssi`.
   - `swiftletcare-backend/app/telemetry.py` and `schemas.py` currently subscribe to `swiftlet/telemetry/+/+` (`swiftlet/telemetry/{house_code}/{node_id}`, 4 segments) expecting `temperature`, `audioRms`, `audioHealthy`, `networkRssi`.
2. **AI HTTP Publisher Default Port:**
   - `ai-pipeline/configs/pipeline.yaml` defaults `publishers.http.base_url` to `http://localhost:3000` whereas FastAPI runs on port `8000` by default.
3. **Domain CRUD APIs & Backend Authentication:**
   - Frontend currently uses canonical mock state and `localStorage` authentication (`AuthContext.jsx`) pending Backend REST CRUD and auth endpoints.

---

## 4. Frontend Decisions

Frontend currently uses:

- React
- Vite
- React Router
- Plain CSS
- Context/localStorage for current mock authentication

Do not introduce a new framework/state/UI library without a clear requirement.

Current feature organization:

```text
components/features/
├── account/
├── farm-owner/
├── technician/
└── admin/
```
