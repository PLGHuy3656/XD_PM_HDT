# Analytics Service

FastAPI microservice that aggregates historical environmental telemetry for
devices the current user is authorized to monitor, evaluates environmental
alerts, and summarizes AI bird counts and actual harvest records.

## Requirements and setup

- Python 3.11+
- PostgreSQL IoT database containing the `devices` and `telemetry` tables
- Management Service for bearer-token verification and device-level access
- RabbitMQ for delivering alert notifications
- ReportLab for PDF report generation

Run commands from this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `DATABASE_URL` to the IoT database used by `swiftletcare-backend` and
`MANAGEMENT_SERVICE_URL` to the Management Service. The Analytics Service reads
telemetry from the IoT database and asks Management Service for the devices the
bearer token may monitor; it does not access management tables directly.
Apply `database/migrations/001_telemetry_analytics_index.sql` to the IoT
database to support time-range aggregation without blocking telemetry writes.
Apply `database/migrations/002_analytics_domains.sql` to that same database to
create alert/outbox, AI count, and harvest data tables. Apply
`database/migrations/003_ai_event_ingestion.sql` to create the AI event store
and deduplication indexes. Apply
`database/migrations/004_bird_movement_history.sql` to store tracked swiftlet
positions. Configure the same
random `ANALYTICS_SERVICE_TOKEN` in both this service and Management Service.
Set a separate high-entropy `AI_INGEST_TOKEN` for the AI pipeline. Configure
`RABBITMQ_URL` to publish threshold and anomaly events to the shared
`swiftletcare.events` topic exchange. If RabbitMQ is not configured, alert
events remain pending in the outbox and will not reach Notification Service.

Run the API on port `8003`:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8003
```

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `GET` | `/api/analytics/telemetry` | Aggregate authorized device telemetry |
| `GET` | `/api/analytics/telemetry/report.csv` | Download authorized telemetry as CSV |
| `GET` | `/api/analytics/telemetry/report.pdf` | Download authorized telemetry as PDF |
| `GET` | `/api/analytics/birds` | Aggregate authorized AI bird-count snapshots |
| `GET` | `/api/analytics/alerts` | List environmental threshold/anomaly alerts |
| `GET` | `/api/analytics/harvest` | Summarize actual harvest records |
| `GET` | `/api/analytics/ai-events` | List authorized Vision and Audio events |
| `GET` | `/api/analytics/ai-events/{event_id}` | Get one authorized AI event and its complete payload |
| `GET` | `/api/analytics/bird-movements` | Query tracked bird positions for an authorized camera |
| `POST` | `/api/analytics/harvest` | Record a harvest with farm/zone authorization |
| `POST` | `/api/ai/counts` | Ingest cumulative AI count snapshots |
| `POST` | `/api/ai/detections` | Ingest tracked detections for movement history |
| `POST` | `/api/ai/events` | Ingest a Vision event |
| `POST` | `/api/ai/audio/events` | Ingest an Audio anomaly event |

All `/api/analytics/*` endpoints require the Management Service bearer token
in the `Authorization` header. Farm and zone query parameters are constrained
to resources accessible to that user. Telemetry and alert/bird endpoints accept
the following `period` values:

- `period`: `1h`, `6h`, `24h`, `7d`, or `30d` (default `24h`)
- `farm_id`: filter to an authorized farm ID/code
- `zone_id`: filter to an authorized zone ID/code

The telemetry response contains a summary and time-bucketed average, minimum, and maximum
for temperature, humidity, CO₂, illuminance, and audio RMS. Buckets are minute
for `1h`, hour for `6h` and `24h`, and day for `7d` and `30d`.

`POST /api/ai/counts` uses the AI interface payload (`cameraId`, epoch-second
`timestamp`, cumulative `entryCount`, `exitCount`, and `netChange`) and requires
`X-AI-Ingest-Token`. Cumulative values are stored as snapshots; bird analytics
calculates deltas and handles counter resets. Harvest records require
`farm_id`, optional `zone_id`, `harvest_date`, `nest_count`, and `yield_kg`;
the authenticated user is recorded as `recorded_by`.

Bird counts can be queried from `/api/analytics/birds` by `period`, authorized
`farm_id`, `zone_id`, and optional `camera_id` (the Management `node_id`). The
API aggregates cumulative count snapshots into entries/exits and net change.
Periods `7d` and `30d` return daily buckets; shorter periods return minute/hour
buckets. The camera filter is checked against the authenticated user's active,
monitorable devices.

Tracked movement requires the AI pipeline to POST detection batches to
`/api/ai/detections` with the same `X-AI-Ingest-Token`. Only `swiftlet`
detections with a `trackId` are retained; each point stores the timestamp,
confidence, bounding box, and its center in image pixels. Exact retries are
deduplicated. Query `/api/analytics/bird-movements?camera_id=CAM-01&period=24h`
with a user bearer token; optional `track_id` and `limit` further scope the
history. Camera access is checked through Management Service. These points
describe image-plane positions, not calibrated physical/geographic paths.

Vision and Audio event endpoints require the same `X-AI-Ingest-Token`.
`cameraId` must match an active Management device's `node_id`; Management
provides the authoritative farm/zone mapping and notification recipients.
Events are stored in the Analytics database and published through its
transactional outbox to Notification Service. Supply a UUID `eventId` for
idempotent retries; events without one are deduplicated by normalized payload.
New events return HTTP 202, duplicates HTTP 200, invalid payloads HTTP 422, and
unknown/inactive camera IDs HTTP 404. `GET /api/analytics/ai-events` applies
the caller's authorized-device scope and accepts `period`, `source_type`,
`event_type`, `camera_id`, `farm_id`, and `zone_id` filters. It also accepts
an optional timezone-aware `start` and `end` pair for a custom time range,
plus `limit` (1-500) and `offset` for pagination. The default period is `7d`;
when both custom timestamps are supplied they take precedence over `period`.
The detail endpoint returns the same event shape and payload as the list and
returns 404 if the event does not belong to one of the caller's authorized
devices.

The Vision payload supports `PREDATOR_DETECTED` and `FLOCK_ANOMALY` with class,
confidence, epoch-second timestamp, and optional bounding box, snapshot
metadata, track ID, and detail. Audio currently accepts `AUDIO_ANOMALY` with
label, confidence, and timestamp, plus optional RMS, threshold, and detail.
Farm is the project's current location entity (there is no House entity in the
Management schema); the stored mapping includes farm and optional zone. Snapshot
values are stored as metadata only; Analytics does not fetch or verify image
URLs. The Web client previews a snapshot only when its reference can be loaded
by the browser, and overlays pixel-coordinate bounding boxes when both image and
box metadata are available. See `ai-pipeline/docs/ai-interface.md` for JSON
contracts.

The Analytics monitoring worker starts when `DATABASE_URL` and
`ANALYTICS_SERVICE_TOKEN` are configured. It uses configured temperature,
humidity, and CO₂ control thresholds; illuminance threshold alerts are omitted
until a configured threshold exists. Anomaly detection uses the preceding
seven days (excluding the latest five minutes), median ± 3 × MAD, and
requires at least 30 observations. Alert events are sent to the Notification
Service through RabbitMQ and persisted in an outbox for retry.

The Farm Owner Analytics page displays real telemetry, bird-count snapshots,
environmental alerts, and recorded harvests, and allows CSV/PDF downloads.
The AI pipeline must actively POST its count snapshots to `/api/ai/counts`;
configure the same `AI_INGEST_TOKEN` in the sender. The current AI repository
contains the count contract and configuration but does not yet include a
running camera/publisher loop, so deploy that producer before expecting bird
counts to appear.
Vision/Audio ingestion APIs are ready to receive events, but the AI repository
does not yet contain a running camera publisher or audio detector. Deploy and
configure those producers before expecting real events or notifications.
The AI package now includes an HTTP publisher for counts, detections, and
Vision events. The repository still has no live camera/tracker runtime; tracked
movement history is populated only when that runtime calls
`publish_detections()` with detections containing `trackId`.

## Tests

```powershell
python -m pytest -q
```
