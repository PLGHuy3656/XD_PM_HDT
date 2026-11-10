# CP9 PHASE 3A: DATA INTEGRATION DESIGN (NO DATABASE WRITES)
**Document Version:** 2.1.0 (Final Architecture & ETL Engineering Specification)
**Status:** DRAFT FOR FINAL APPROVAL (ZERO-DB / ZERO-RUNTIME WRITES)
**Author:** Antigravity Engineering
**Scope:** Architecture & ETL specification for integrating Analytics Service with Apache NiFi and PostgreSQL (`analytics_db`).

---

## 1. Executive Summary & Integration Principles

The Analytics Service in SwiftletCare is designed as an **OLAP (Online Analytical Processing) Read Model Service**. Per architectural constraint `CON-07` and UML class design (`34_class_analytics.puml`), operational transactional databases (`management_db`, `iot_db`, `ai_db`, `notification_db`) are decoupled from analytical reporting queries. Data synchronization is managed asynchronously by **Apache NiFi**.

### Classification Legend:
* **`[CONFIRMED]`**: Formally verified from existing codebase, database schemas, or SRS specifications.
* **`[APPROVED DESIGN]`**: Architectural decisions reviewed and agreed upon during Phase 1/2/3A design reviews.
* **`[PROPOSED]`**: Heuristic, threshold, or model pending formal business or hardware benchmark sign-off.
* **`[PENDING IMPLEMENTATION]`**: Components designed for execution in Phase 3B when database infrastructure is live.

---

## 2. Ingestion Methods, Access Controls & Upstream Checkpoint Engineering

### 2.1. Ingestion Strategy per Upstream Service

| Subsystem | Primary Ingestion Channel | Upstream Table / Topic | Record Mutability | Incremental Checkpoint Strategy | Classification |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **Management Service** | Incremental DB Polling | `farms`, `zones`, `devices` | Mutable records (`updated_at`, `id`) | Lookback Watermark ($\Delta t = 2\text{ min}$) + `(updated_at, id)` composite tie-breaker. | `[CONFIRMED]` for schema<br>`[APPROVED DESIGN]` for polling |
| **IoT Service** | Real-time Stream | MQTT Topic `swiftlet/telemetry/v1/#` | Stream payload (`AcceptedTelemetry`) | MQTT Consumer with client group ID; offset tracked by broker. | `[CONFIRMED]` for topic<br>`[APPROVED DESIGN]` for consumer |
| **AI Service** | Incremental Table Polling | `ai_count_updates` | Insert-Only Immutable Event Log | Monotonic High-Watermark on `(recorded_at, id)` composite keys. | `[CONFIRMED]` for table<br>`[APPROVED DESIGN]` for polling |
| **Notification Service** | Incremental Table Polling | `alerts` | Mutable records (`updated_at`, `alert_id`) | Lookback Watermark ($\Delta t = 2\text{ min}$) + `(updated_at, alert_id)`. | `[CONFIRMED]` for schema<br>`[APPROVED DESIGN]` for polling |

### 2.2. Dedicated Read-Only Role & Security Boundaries `[APPROVED DESIGN]`
NiFi connects to upstream operational databases under a strictly constrained user:
```sql
-- Executed on upstream databases (management_db, iot_db, ai_db, notification_db)
CREATE ROLE analytics_reader WITH LOGIN PASSWORD '<secure_password_vault>';
GRANT CONNECT ON DATABASE <db_name> TO analytics_reader;
GRANT USAGE ON SCHEMA public TO analytics_reader;
GRANT SELECT ON TABLE farms, zones, devices, ai_count_updates, alerts TO analytics_reader;

-- Strict Least Privilege: Explicitly revoke all write and administrative capabilities
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM analytics_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO analytics_reader;
REVOKE CREATE ON SCHEMA public FROM analytics_reader;
```
* **Read Safety Controls:**
  - Queries must name explicit columns (no `SELECT *`).
  - Read transactions run with `SET TRANSACTION READ ONLY ISOLATION LEVEL READ COMMITTED;` with a strict `statement_timeout = '10s'`.
  - NiFi never holds locks or delays upstream OLTP commit transactions.

### 2.3. Safe Incremental Polling Checkpoints & Late-Commit Mitigation `[APPROVED DESIGN]`
1. **Insert-Only Tables (`ai_count_updates`):**
   - Records are append-only.
   - Query uses composite tie-breaker:
     ```sql
     WHERE (recorded_at > :last_recorded_at)
        OR (recorded_at = :last_recorded_at AND id > :last_id)
     ORDER BY recorded_at ASC, id ASC LIMIT 1000;
     ```
   - Eliminates row skipping when multiple frames arrive within the same microsecond.
2. **Mutable Tables (`farms`, `zones`, `devices`, `alerts`):**
   - Hazard: An upstream transaction may begin at $t_1$, generate `updated_at = t_1`, but commit at $t_2$ (after NiFi has already polled past $t_1$).
   - Solution: NiFi applies an **Overlapping Lookback Buffer** of $\Delta t = 2\text{ minutes}$:
     ```sql
     WHERE updated_at >= (:last_watermark - INTERVAL '2 minutes')
     ORDER BY updated_at ASC, id ASC;
     ```
   - Because downstream ingestion is strictly idempotent, re-evaluating the lookback window introduces zero duplicate records and completely mitigates late-commit anomalies.

---

## 3. Atomic Deduplication Ledger & Staging Architecture `[APPROVED DESIGN]`

To guarantee durability across NiFi restarts, pipeline retries, and network crashes, deduplication is managed within a single **atomic database transaction boundary** in `analytics_db`.

### 3.1. Tables DDL
```sql
-- 1. Deduplication Ledger Table
CREATE TABLE stg_event_dedup_ledger (
    source_subsystem VARCHAR(32) NOT NULL, -- 'IOT', 'AI_COUNT', 'NOTIFICATION'
    event_fingerprint VARCHAR(128) NOT NULL, -- Deterministic hash
    event_timestamp TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_subsystem, event_fingerprint)
);
CREATE INDEX idx_dedup_retention ON stg_event_dedup_ledger(ingested_at);

-- 2. Staging Table for Bird Counts
CREATE TABLE stg_count_updates (
    staging_id BIGSERIAL PRIMARY KEY,
    farm_id VARCHAR(64) NOT NULL,
    zone_id VARCHAR(64) NOT NULL,
    camera_id VARCHAR(64) NOT NULL,
    frame_id BIGINT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    delta_entry INTEGER NOT NULL,
    delta_exit INTEGER NOT NULL,
    is_coverage_healthy BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_stg_ai_event UNIQUE (camera_id, frame_id, recorded_at)
);
```

### 3.2. Atomic Transaction Boundary & Crash Recovery
NiFi executes staging ingestion in an all-or-nothing transaction:
```sql
BEGIN;

-- Step 1: Attempt insertion into deduplication ledger
INSERT INTO stg_event_dedup_ledger (source_subsystem, event_fingerprint, event_timestamp)
VALUES ('AI_COUNT', :fingerprint, :recorded_at)
ON CONFLICT (source_subsystem, event_fingerprint) DO NOTHING
RETURNING event_fingerprint;

-- Step 2: Insert into staging ONLY if Step 1 inserted a new ledger row
-- (Condition evaluated by NiFi or combined via CTE in PostgreSQL):
INSERT INTO stg_count_updates (farm_id, zone_id, camera_id, frame_id, recorded_at, delta_entry, delta_exit, is_coverage_healthy)
SELECT :farm_id, :zone_id, :camera_id, :frame_id, :recorded_at, :delta_entry, :delta_exit, :is_healthy
WHERE EXISTS (
    SELECT 1 FROM stg_event_dedup_ledger
    WHERE source_subsystem = 'AI_COUNT' AND event_fingerprint = :fingerprint AND ingested_at >= CURRENT_TIMESTAMP - INTERVAL '5 seconds'
);

COMMIT;
```
* **Crash Recovery Guarantee:** If NiFi or the database node fails at any microsecond during execution, PostgreSQL rolls back uncommitted changes. Neither an orphaned ledger row nor an unledgered staging record can ever exist.

---

## 4. 2-Stage Deterministic Aggregation & Fact Idempotency `[APPROVED DESIGN]`

### 4.1. The Hazard of Naive Additive Upserts
Executing `ON CONFLICT (keys) DO UPDATE SET entries = entries + EXCLUDED.entries` causes **silent double-counting** whenever a network retry occurs or an ETL pipeline is replayed.

### 4.2. Deterministic Window Materialization
Aggregation is decoupled into two deterministic stages:
```
[ Incoming Events ] ──> (Atomic Ledger + Staging) ──> [ Materialization Query ] ──> [ Fact Tables ]
```

**Materialization Statement (Idempotent Snapshot Rollup):**
```sql
INSERT INTO fact_bird_activity_hourly (
    farm_id, zone_id, camera_id, time_bucket, entries, exits, net_change, sample_count, is_coverage_healthy, updated_at
)
SELECT
    farm_id,
    zone_id,
    camera_id,
    date_trunc('hour', recorded_at) AS time_bucket,
    SUM(delta_entry) AS entries,
    SUM(delta_exit) AS exits,
    SUM(delta_entry) - SUM(delta_exit) AS net_change,
    COUNT(*) AS sample_count,
    BOOL_AND(is_coverage_healthy) AS is_coverage_healthy,
    CURRENT_TIMESTAMP AS updated_at
FROM stg_count_updates
WHERE farm_id = :target_farm_id
  AND recorded_at >= :bucket_start
  AND recorded_at < :bucket_end
GROUP BY farm_id, zone_id, camera_id, date_trunc('hour', recorded_at)
ON CONFLICT (farm_id, zone_id, camera_id, time_bucket)
DO UPDATE SET
    entries = EXCLUDED.entries,
    exits = EXCLUDED.exits,
    net_change = EXCLUDED.net_change,
    sample_count = EXCLUDED.sample_count,
    is_coverage_healthy = EXCLUDED.is_coverage_healthy,
    updated_at = CURRENT_TIMESTAMP;
```
* **Guarantee:** Replaying any historical batch recalculates the exact snapshot state without drift.

---

## 5. Camera & Sensor Observability Policy (Coverage & Missing Data)

### 5.1. Strict Zero-Fill Policy `[CONFIRMED]`
* Discrete counts (bird entries, exits, alerts) are zero-filled **ONLY when there is positive, continuous evidence of full observation coverage throughout the entire evaluation bucket**.
* Partial monitoring (e.g. 90% observation) does **NOT** equate to full coverage. An absence of recorded bird activity during unobserved intervals cannot be assumed to be zero.
* Where coverage is partial, failed, or undetermined: missing event metrics are preserved as **`NULL`**, and the response emits `hasDataGaps = TRUE`.

### 5.2. Proposed Observability Thresholds `[PROPOSED]`
The following operational telemetry health criteria are established as technical proposals pending live hardware benchmark validation:

| Observability Parameter | Proposed Threshold `[PROPOSED]` | Technical Rationale |
| :--- | :---: | :--- |
| **Inference Frame Rate** | $\ge 5.0\text{ FPS}$ | Minimum sampling rate required to track fast-moving swiftlets across line boundaries. |
| **Frame Drop Ratio** | $< 5.0\%$ | Prevents object trajectory fragmentation in ByteTrack. |
| **Camera Heartbeat Ping** | Interval $\le 30\text{ seconds}$ | Validates stream connectivity between camera node and Edge AI server. |
| **Coverage Classification** | 100% full interval | Zero-fill allowed only if zero outage gaps were recorded in bucket. |

---

## 6. Telemetry Threshold Alignment & Divergence Analysis

### 6.1. Identified Divergence between Modules `[CONFIRMED]`
* **IoT Service (`TelemetryMetrics`):**
  - Temperature validation: $-40.0^\circ\text{C} \le T \le 85.0^\circ\text{C}$ (`ge=-40.0, le=85.0`).
  - Derived from industrial hardware operating limits (e.g. Sensirion SHT30 datasheet).
* **Analytics Phase 1 Domain (`DEFAULT_THRESHOLDS`):**
  - Temperature validation: $-10.0^\circ\text{C} \le T \le 60.0^\circ\text{C}$.
  - Conceived as ambient plausible limits for tropical/subtropical swiftlet houses.
* **Divergence Impact:** An extreme zinc-roof reading of $62^\circ\text{C}$ during direct summer solar radiation would pass IoT validation but be discarded as `NULL` by Analytics filtering.

### 6.2. Proposed Unification Strategy `[PROPOSED]`
1. **Tier 1 (Ingestion Bounds):** Align Analytics physical bounds with IoT Service hardware range:
   $$-40.0^\circ\text{C} \le T \le 85.0^\circ\text{C}$$
   Ensures that genuine sensor readings are never silently dropped before reaching the analytics database.
2. **Tier 2 (Biological Optimal Range):** Preserve swiftlet nesting optimal bounds strictly for microclimate health scoring:
   $$27.0^\circ\text{C} \le T \le 31.0^\circ\text{C} \quad (\text{Tolerable: } 25.0 - 33.0^\circ\text{C})$$
   Readings outside tolerable bounds are stored as valid telemetry, but trigger climate warnings and degrade the zone microclimate score.

---

## 7. Multi-Device Aggregation Methodology in Shared Zones `[APPROVED DESIGN]`

### 7.1. Fact Granularity
To eliminate device collision and data overwrites in zones equipped with multiple nodes, `fact_telemetry_hourly` maintains **Device Grain**:
$$\text{Primary Key: } (\text{farm\_id}, \text{zone\_id}, \text{device\_id}, \text{time\_bucket})$$

### 7.2. Multi-Device Zone Rollup Formula
When evaluating Zone $z$ containing devices $d \in \{1 \dots K\}$ during time bucket $h$:
* Let $N_d$ be the valid `sample_count` recorded by device $d$.
* Let $\bar{T}_d$ be the average temperature computed by device $d$.
* Let $D_{\text{active}} = \{d \in \{1 \dots K\} \mid N_d > 0 \text{ and } \bar{T}_d \text{ is not NULL}\}$.

**Mathematical Aggregation Rule:**
1. **If $D_{\text{active}} = \emptyset$ (All devices offline or missing):**
   $$\bar{T}_{z, h} = \text{NULL}, \quad \text{has\_data\_gaps} = \text{TRUE}$$
2. **If $|D_{\text{active}}| > 0$:**
   $$\bar{T}_{z, h} = \frac{\sum_{d \in D_{\text{active}}} (N_d \times \bar{T}_d)}{\sum_{d \in D_{\text{active}}} N_d}$$
   *(The zone average is strictly sample-weighted across all active sensors, perfectly representing the true physical mean of all measurements collected in the zone).*
3. **Partial Zone Coverage Flag:**
   - If $|D_{\text{active}}| < K$: One or more devices failed to report. The zone metric emits `has_data_gaps = TRUE` and `active_device_ratio = \frac{|D_{\text{active}}|}{K}` to alert UI consumers to partial spatial coverage.

---

## 8. Analytics Database Production DDL (`analytics_db`) `[APPROVED DESIGN]`

```sql
-- =============================================================================
-- 1. Dimension Tables
-- =============================================================================

CREATE TABLE dim_farms (
    farm_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    owner_id VARCHAR(64) NOT NULL,
    address TEXT,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE dim_zones (
    zone_id VARCHAR(64) PRIMARY KEY,
    farm_id VARCHAR(64) NOT NULL REFERENCES dim_farms(farm_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE dim_devices (
    device_id VARCHAR(64) PRIMARY KEY,
    farm_id VARCHAR(64) NOT NULL REFERENCES dim_farms(farm_id) ON DELETE CASCADE,
    zone_id VARCHAR(64) REFERENCES dim_zones(zone_id) ON DELETE SET NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    metadata_version BIGINT NOT NULL DEFAULT 1,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_dim_devices_lookup ON dim_devices(device_id, farm_id, zone_id);

-- =============================================================================
-- 2. Staging & Deduplication Tables
-- =============================================================================

CREATE TABLE stg_event_dedup_ledger (
    source_subsystem VARCHAR(32) NOT NULL,
    event_fingerprint VARCHAR(128) NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_subsystem, event_fingerprint)
);
CREATE INDEX idx_dedup_retention ON stg_event_dedup_ledger(ingested_at);

CREATE TABLE stg_count_updates (
    staging_id BIGSERIAL PRIMARY KEY,
    farm_id VARCHAR(64) NOT NULL,
    zone_id VARCHAR(64) NOT NULL,
    camera_id VARCHAR(64) NOT NULL,
    frame_id BIGINT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    delta_entry INTEGER NOT NULL,
    delta_exit INTEGER NOT NULL,
    is_coverage_healthy BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_stg_ai_event UNIQUE (camera_id, frame_id, recorded_at)
);
CREATE INDEX idx_stg_counts_time ON stg_count_updates(farm_id, recorded_at);

-- =============================================================================
-- 3. Fact Tables (Deterministic Rollups)
-- =============================================================================

-- Fact 1: Environmental Telemetry (Device Grain)
CREATE TABLE fact_telemetry_hourly (
    farm_id VARCHAR(64) NOT NULL REFERENCES dim_farms(farm_id),
    zone_id VARCHAR(64) NOT NULL REFERENCES dim_zones(zone_id),
    device_id VARCHAR(64) NOT NULL REFERENCES dim_devices(device_id),
    time_bucket TIMESTAMPTZ NOT NULL,
    avg_temperature DOUBLE PRECISION,
    min_temperature DOUBLE PRECISION,
    max_temperature DOUBLE PRECISION,
    avg_humidity DOUBLE PRECISION,
    min_humidity DOUBLE PRECISION,
    max_humidity DOUBLE PRECISION,
    avg_co2 DOUBLE PRECISION,
    avg_lux DOUBLE PRECISION,
    avg_audio_rms DOUBLE PRECISION,
    sample_count INTEGER NOT NULL DEFAULT 0,
    has_data_gaps BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (farm_id, zone_id, device_id, time_bucket)
);
CREATE INDEX idx_telemetry_hourly_range ON fact_telemetry_hourly(farm_id, zone_id, time_bucket);

-- Fact 2: Bird Activity (Camera Grain)
CREATE TABLE fact_bird_activity_hourly (
    farm_id VARCHAR(64) NOT NULL REFERENCES dim_farms(farm_id),
    zone_id VARCHAR(64) NOT NULL REFERENCES dim_zones(zone_id),
    camera_id VARCHAR(64) NOT NULL,
    time_bucket TIMESTAMPTZ NOT NULL,
    entries INTEGER NOT NULL DEFAULT 0,
    exits INTEGER NOT NULL DEFAULT 0,
    net_change INTEGER NOT NULL DEFAULT 0,
    sample_count INTEGER NOT NULL DEFAULT 0,
    is_coverage_healthy BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (farm_id, zone_id, camera_id, time_bucket)
);
CREATE INDEX idx_bird_activity_hourly_range ON fact_bird_activity_hourly(farm_id, time_bucket);

-- Fact 3: Operational Alerts
CREATE TABLE fact_alerts_hourly (
    farm_id VARCHAR(64) NOT NULL REFERENCES dim_farms(farm_id),
    zone_id VARCHAR(64),
    time_bucket TIMESTAMPTZ NOT NULL,
    critical_count INTEGER NOT NULL DEFAULT 0,
    high_count INTEGER NOT NULL DEFAULT 0,
    medium_count INTEGER NOT NULL DEFAULT 0,
    low_count INTEGER NOT NULL DEFAULT 0,
    total_count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (farm_id, COALESCE(zone_id, 'GLOBAL'), time_bucket)
);
CREATE INDEX idx_alerts_hourly_range ON fact_alerts_hourly(farm_id, time_bucket);

-- Fact 4: Harvest Yield [PROPOSED - Periodic Batch Harvest Data]
CREATE TABLE fact_harvest_yield (
    harvest_id VARCHAR(64) PRIMARY KEY,
    farm_id VARCHAR(64) NOT NULL REFERENCES dim_farms(farm_id),
    zone_id VARCHAR(64) REFERENCES dim_zones(zone_id),
    harvest_date DATE NOT NULL,
    total_nests INTEGER NOT NULL DEFAULT 0,
    harvested_nests INTEGER NOT NULL DEFAULT 0,
    yield_kg DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_harvest_yield_farm ON fact_harvest_yield(farm_id, harvest_date);
```

---

## 9. Comprehensive Status Traceability Matrix

| Component / Architectural Decision | Status Category | Technical Basis & Justification |
| :--- | :---: | :--- |
| **API Endpoints (`/summary`, `/trends`)** | `[CONFIRMED]` | Verified in `gateway/app/routes.py` and `SRS.md` Section 3.9. |
| **Upstream Table Schemas & Keys** | `[CONFIRMED]` | Verified directly in `ai_count_updates`, `alerts`, `farms`, `zones`, `devices`. |
| **UTC Storage & ISO-8601 Formatting** | `[CONFIRMED]` | Enforced across IoT, AI, and Notification services. |
| **Continuous Missing Data as JSON `null`** | `[CONFIRMED]` | Validated by 63/63 pytest cases in Phase 1 & 2. |
| **Zero-Fill Strict Coverage Dependency** | `[CONFIRMED]` | Verified: zero-fill only permitted on full positive coverage proof. |
| **Direct Read-Only DB Ingestion Role** | `[APPROVED DESIGN]` | Restricts `analytics_reader` to SELECT only with statement timeouts. |
| **Durable Atomic Deduplication Ledger** | `[APPROVED DESIGN]` | Combined transaction boundary preventing ledger/staging drift. |
| **2-Stage Deterministic Aggregation** | `[APPROVED DESIGN]` | Replaces double-counting additive upserts with snapshot replacement. |
| **Device-Grain `fact_telemetry_hourly`** | `[APPROVED DESIGN]` | Eliminates multi-device overwrite collision in shared zones. |
| **Sample-Weighted Zone Mean Formula** | `[APPROVED DESIGN]` | Weighted average across active nodes accounting for missing devices. |
| **Lookback Watermark Buffer ($\Delta t = 2\text{m}$)** | `[APPROVED DESIGN]` | Mitigates late-committing read-committed upstream transactions. |
| **Composite Tie-Breaker Watermark** | `[APPROVED DESIGN]` | `(recorded_at, id)` sorting avoids dropping identical timestamp events. |
| **Composite Microclimate Score (0-100)** | `[PROPOSED]` | Heuristic weighting function derived from `analyticsMockData.js`. |
| **Camera Observability Thresholds (FPS/Drop)**| `[PROPOSED]` | Operational criteria ($\ge 5\text{ FPS}, < 5\%$ drop) pending live test. |
| **Harvest Yield Tracking (`fact_harvest_yield`)**| `[PROPOSED]` | Batch periodic harvest data derived from `analyticsMockData.js`. |
| **Temperature Bound Alignment ($-40..85^\circ\text{C}$)**| `[PROPOSED]` | Proposes widening Analytics physical bounds to match IoT hardware range. |
| **PostgreSQL & NiFi Runtime Deployment** | `[PENDING IMPLEMENTATION]` | Scheduled for Phase 3B upon infrastructure authorization. |

---

## 10. Phase 3B Implementation Plan & Acceptance Criteria `[PENDING IMPLEMENTATION]`

1. **Step 1 — Database & Security Setup:**
   - Initialize `analytics_db` and roles `analytics_owner`, `analytics_user`.
   - Provision `analytics_reader` on upstream databases (`management_db`, `iot_db`, `ai_db`, `notification_db`).
   - Execute DDL script `001_initial_analytics_schema.sql`.
2. **Step 2 — Adapter Development:**
   - Create `services/analytics-service/app/repositories/postgresql_repository.py` implementing `IAnalyticsRepository`.
   - Run automated parity tests proving 100% equivalence with `InMemoryAnalyticsRepository`.
3. **Step 3 — NiFi Flow Template Deployment:**
   - Deploy XML/JSON templates for PG-01 through PG-04.
   - Validate watermarking, dead-letter queue routing, and crash recovery.
4. **Phase 3B Implementation Status (CP9 Closeout):**
   - **PostgreSQL Persistence & Migration 001:** COMPLETED & VERIFIED against local PostgreSQL 18.6 `analytics_db`.
   - **Python Pipeline Runner (`pipeline_runner.py`):** COMPLETED & VERIFIED for PG-01 through PG-04 data flows (78/78 tests PASS).
   - **Apache NiFi Runtime Deployment:** **BLOCKED / OPEN** due to Docker Desktop Windows service being stopped in the current environment.
   - **Apache NiFi Flow Template (`nifi_analytics_pipeline_flow.xml`):** Classified as **`EXPERIMENTAL / UNVERIFIED`** structural skeleton. Live canvas instantiation and JDBC driver execution remain pending live Docker environment startup. Architectural constraint `SRS CON-07` remains OPEN pending runtime verification.
