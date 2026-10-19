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

Current responsibility direction:

- User and access management
- Farm administration
- Device/system administration
- Technician ↔ Farm assignment
- Platform administration

Admin frontend will be developed after Technician.

---

## 2. Important Domain Decisions

### Technician ↔ Farm Assignment

Assigned Farm is a shared Technician context, not a separate sidebar module.

Administrator will assign Technician to one or more farms.

Technician should be able to:

- know which farms are currently assigned;
- select/use assigned Farm context where required;
- receive notification when an assignment changes;
- access only authorized farms.

Farm Owner should also be able to see the Technician supporting a farm.

Basic Technician information available to Farm Owner should include at least:

- name;
- contact information;
- assignment/support status.

This information should eventually be accessible from Farm Management.

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

Current important technical baseline:

- Backend: Node.js / NestJS
- Database: MongoDB
- Cache: Redis
- IoT: ESP32 / ESP32-CAM
- Embedded: Arduino / FreeRTOS
- Communication: MQTT + HTTP
- AI: YOLO26 + ByteTrack
- Notifications: Firebase Cloud Messaging
- Storage: MinIO / S3 compatible storage

Mandatory course technologies:

- OpenAPI / Swagger
- Redis Cache
- Firebase Messaging
- Apache NiFi
- Microservices
- API Gateway
- Docker

Older documentation may contain outdated decisions such as Express, Tailwind, YOLOv8, YOLOv10, or additional actors.

Do not silently restore those decisions.

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