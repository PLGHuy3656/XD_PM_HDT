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
create alert/outbox, AI count, and harvest data tables. Configure the same
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
| `POST` | `/api/analytics/harvest` | Record a harvest with farm/zone authorization |
| `POST` | `/api/ai/counts` | Ingest cumulative AI count snapshots |

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

## Tests

```powershell
python -m pytest -q
```
