# Notification Service

FastAPI service that stores user notifications, streams new notifications over
WebSocket, and independently delivers email, Web Push, and Firebase Cloud
Messaging (FCM) messages.

## Requirements and setup

- Python 3.11+
- Isolated PostgreSQL database (`notification_db`)
- Management Service for bearer-token verification and farm recipient lookup
- RabbitMQ (`swiftlet.domain.events` topic exchange) for event-driven notifications
- Optional SMTP, VAPID, and Firebase service-account credentials

Run commands from this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `NOTIFICATION_DATABASE_URL` (or `DATABASE_URL`), `MANAGEMENT_SERVICE_URL`,
and `RABBITMQ_URL` (or `RABBITMQ_HOST`/`RABBITMQ_PORT`/`RABBITMQ_USER`/`RABBITMQ_PASSWORD`)
in `.env`. Apply `database/schema.sql` to `notification_db`. The script is
idempotent (tracked in `schema_migrations`) and creates notification,
subscription, FCM-token, and delivery tables without cross-service foreign keys.

Run the API:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8004
```

The service reads `.env` from this directory regardless of the process working
directory. The API starts without RabbitMQ or PostgreSQL, but event ingestion
and persistent delivery require both `RABBITMQ_URL` and `DATABASE_URL`.

### Optional delivery channels

- **Email:** configure `SMTP_HOST`, `SMTP_PORT`, and `SMTP_SENDER`; configure
  username/password when the SMTP provider requires authentication.
- **Web Push:** configure all `VAPID_*` values and register browser subscriptions
  through `POST /api/notifications/subscriptions`.
- **FCM:** configure `FIREBASE_SERVICE_ACCOUNT_PATH` with a Firebase Admin
  service-account JSON file (keep this file outside Git), optionally set
  `FIREBASE_PROJECT_ID`, then register a device token through
  `POST /api/notifications/fcm-tokens`, for example:

  ```json
  {"token":"<device-registration-token>","platform":"android"}
  ```

Unconfigured channels or users without a destination are marked `skipped`.
Delivery errors are retried independently for up to five attempts with
exponential backoff (5, 10, 20, and 40 seconds). A delivery worker lease allows abandoned
jobs to be recovered after a process crash. Delivery is at-least-once: if a
provider accepts a message but the service crashes before recording success, a
retry may deliver a duplicate. Realtime WebSocket delivery is best-effort;
clients can fetch persisted notifications after reconnecting.

## REST and WebSocket API

All REST endpoints below (except health and the public VAPID key) require the
Management Service bearer token.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `GET` | `/api/notifications` | List notifications; `limit` (1-100), `unread_only` |
| `POST` | `/api/notifications/{id}/read` | Mark one owned notification as read |
| `POST` | `/api/notifications/read-all` | Mark all of the user's notifications read |
| `GET` | `/api/notifications/push/vapid-public-key` | Get the public VAPID key |
| `POST` | `/api/notifications/subscriptions` | Register/update a Web Push subscription |
| `POST` | `/api/notifications/fcm-tokens` | Register/update an FCM token |
| `DELETE` | `/api/notifications/fcm-tokens` | Remove an FCM token (JSON body: `{"token":"..."}`) |
| `WS` | `/ws/notifications` | Authenticated realtime stream |

WebSocket clients send `{"type":"auth","authorization":"Bearer ..."}` within
five seconds after connecting. New notifications arrive as
`{"type":"notification","notification":{...}}`.

## RabbitMQ event contract

The service consumes routing keys `management.#`, `device.#`,
`environment.#`, and `ai.#` from the configured topic exchange. Supported
events must be JSON objects with this envelope:

```json
{
  "event_id": "UUID",
  "event_type": "environment.threshold_exceeded",
  "occurred_at": "2026-01-01T00:00:00Z",
  "recipient_user_ids": ["user-UUID"],
  "data": {}
}
```

`event_id` and recipient IDs must be UUIDs. The producer is responsible for
resolving authorized recipients; unsupported event types are acknowledged and
ignored. Current event types and useful `data` fields:

| Event type | Useful data |
|---|---|
| `management.technician_assigned` | `technician_id`, `technician_name`, `farm_name` |
| `device.command.acknowledged` | `node_id`, `action` or `command_id`, `status`, farm/zone fields |
| `environment.threshold_exceeded` | `metric`, `value`, `unit`, `threshold`, farm/zone fields |
| `device.offline` | `node_id`, farm/zone fields |
| `device.sensor.timeout` | `node_id`, `sensor_name` or `sensor_type`, farm/zone fields |
| `device.actuator.failed` | `node_id`, `actuator_name`, `error`, farm/zone fields |
| `ai.threat.detected` | `threat_type` or `label`, `confidence`, farm fields |
| `management.work_request.created` | `work_request_id`, `farm_name`, `priority` |
| `management.work_request.status_changed` | `work_request_id`, `status` |

The Management Service currently publishes technician assignment events; the
IoT backend publishes command acknowledgements. The other event types are
accepted contracts for producers to integrate; this service does not itself
detect telemetry thresholds, offline devices, AI threats, or work-request
changes.

RabbitMQ event-processing failures are retried three times via a 5-second
dead-letter delay, then routed to `{NOTIFICATION_QUEUE}.dead`. Database delivery
jobs are separate from event ingestion, so email/Push/FCM outages do not block
or lose an already-persisted in-app notification.

## Tests

```powershell
python -m unittest discover -s tests -v
```
