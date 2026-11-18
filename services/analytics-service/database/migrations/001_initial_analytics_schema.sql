-- =============================================================================
-- Migration 001: Initial Analytics Service Durable Persistence Schema (CP9)
-- Database: analytics_db (OLAP Read Model)
-- Compatible: PostgreSQL 14 - 18+
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------------------------
-- 0. Schema Version Tracking
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(64) PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 1. Dimension Tables
-- Synchronized asynchronously from management_db (farms, zones, devices)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dim_farms (
    farm_id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    owner_id VARCHAR(100) NOT NULL,
    address TEXT,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dim_zones (
    zone_id VARCHAR(100) PRIMARY KEY,
    farm_id VARCHAR(100) NOT NULL REFERENCES dim_farms(farm_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dim_zones_farm ON dim_zones(farm_id);

CREATE TABLE IF NOT EXISTS dim_devices (
    device_id VARCHAR(100) PRIMARY KEY,
    farm_id VARCHAR(100) NOT NULL REFERENCES dim_farms(farm_id) ON DELETE CASCADE,
    zone_id VARCHAR(100) REFERENCES dim_zones(zone_id) ON DELETE SET NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    metadata_version BIGINT NOT NULL DEFAULT 1,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dim_devices_lookup ON dim_devices(device_id, farm_id, zone_id);
CREATE INDEX IF NOT EXISTS idx_dim_devices_zone ON dim_devices(zone_id);

-- -----------------------------------------------------------------------------
-- 2. Staging & Deduplication Tables
-- Atomic transaction boundary for NiFi / ETL ingestion
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS stg_event_dedup_ledger (
    source_subsystem VARCHAR(32) NOT NULL, -- 'IOT', 'AI_COUNT', 'NOTIFICATION'
    event_fingerprint VARCHAR(128) NOT NULL, -- Deterministic hash (sha256/md5)
    event_timestamp TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_subsystem, event_fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_dedup_retention ON stg_event_dedup_ledger(ingested_at);

CREATE TABLE IF NOT EXISTS stg_count_updates (
    staging_id BIGSERIAL PRIMARY KEY,
    farm_id VARCHAR(100) NOT NULL,
    zone_id VARCHAR(100) NOT NULL,
    camera_id VARCHAR(100) NOT NULL,
    frame_id BIGINT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    delta_entry INTEGER NOT NULL,
    delta_exit INTEGER NOT NULL,
    is_coverage_healthy BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_stg_ai_event UNIQUE (camera_id, frame_id, recorded_at)
);

CREATE INDEX IF NOT EXISTS idx_stg_counts_time ON stg_count_updates(farm_id, recorded_at);

-- -----------------------------------------------------------------------------
-- 3. Fact Tables (Deterministic Rollups & Aggregations)
-- -----------------------------------------------------------------------------

-- Fact 1: Environmental Telemetry (Device Grain)
CREATE TABLE IF NOT EXISTS fact_telemetry_hourly (
    farm_id VARCHAR(100) NOT NULL REFERENCES dim_farms(farm_id),
    zone_id VARCHAR(100) NOT NULL REFERENCES dim_zones(zone_id),
    device_id VARCHAR(100) NOT NULL REFERENCES dim_devices(device_id),
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

CREATE INDEX IF NOT EXISTS idx_telemetry_hourly_range ON fact_telemetry_hourly(farm_id, zone_id, time_bucket);
CREATE INDEX IF NOT EXISTS idx_telemetry_hourly_farm_time ON fact_telemetry_hourly(farm_id, time_bucket);

-- Fact 2: Bird Activity (Camera Grain)
CREATE TABLE IF NOT EXISTS fact_bird_activity_hourly (
    farm_id VARCHAR(100) NOT NULL REFERENCES dim_farms(farm_id),
    zone_id VARCHAR(100) NOT NULL REFERENCES dim_zones(zone_id),
    camera_id VARCHAR(100) NOT NULL,
    time_bucket TIMESTAMPTZ NOT NULL,
    entries INTEGER NOT NULL DEFAULT 0,
    exits INTEGER NOT NULL DEFAULT 0,
    net_change INTEGER NOT NULL DEFAULT 0,
    sample_count INTEGER NOT NULL DEFAULT 0,
    is_coverage_healthy BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (farm_id, zone_id, camera_id, time_bucket)
);

CREATE INDEX IF NOT EXISTS idx_bird_activity_hourly_range ON fact_bird_activity_hourly(farm_id, time_bucket);
CREATE INDEX IF NOT EXISTS idx_bird_activity_zone_time ON fact_bird_activity_hourly(zone_id, time_bucket);

-- Fact 3: Operational Alerts (Hourly Rollup)
CREATE TABLE IF NOT EXISTS fact_alerts_hourly (
    farm_id VARCHAR(100) NOT NULL REFERENCES dim_farms(farm_id),
    zone_id VARCHAR(100) NOT NULL DEFAULT 'GLOBAL',
    time_bucket TIMESTAMPTZ NOT NULL,
    critical_count INTEGER NOT NULL DEFAULT 0,
    high_count INTEGER NOT NULL DEFAULT 0,
    medium_count INTEGER NOT NULL DEFAULT 0,
    low_count INTEGER NOT NULL DEFAULT 0,
    total_count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (farm_id, zone_id, time_bucket)
);

CREATE INDEX IF NOT EXISTS idx_alerts_hourly_range ON fact_alerts_hourly(farm_id, time_bucket);

-- Fact 4: Harvest Yield
CREATE TABLE IF NOT EXISTS fact_harvest_yield (
    harvest_id VARCHAR(100) PRIMARY KEY,
    farm_id VARCHAR(100) NOT NULL REFERENCES dim_farms(farm_id),
    zone_id VARCHAR(100) REFERENCES dim_zones(zone_id),
    harvest_date DATE NOT NULL,
    total_nests INTEGER NOT NULL DEFAULT 0,
    harvested_nests INTEGER NOT NULL DEFAULT 0,
    yield_kg DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_harvest_yield_farm ON fact_harvest_yield(farm_id, harvest_date);

-- -----------------------------------------------------------------------------
-- 4. Record Migration Applied
-- -----------------------------------------------------------------------------
INSERT INTO schema_migrations (version, description)
VALUES ('001_initial_analytics_schema', 'Initial CP9 Analytics OLAP schema with dimensions, staging ledger, and hourly fact rollups')
ON CONFLICT (version) DO NOTHING;
