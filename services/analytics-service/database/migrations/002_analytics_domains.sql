-- =============================================================================
-- Migration 002: Operational Analytics Domains (PR #29)
-- Database: analytics_db (Isolated Analytics Persistence — No Cross-DB FKs)
-- Compatible: PostgreSQL 14 - 18+ | Idempotent & Replay-Safe
-- =============================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(64) PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Analytics-owned telemetry read model (decoupled from IoT Service storage)
CREATE TABLE IF NOT EXISTS public.analytics_telemetry_samples (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    node_id VARCHAR(100) NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    co2 DOUBLE PRECISION,
    lux DOUBLE PRECISION,
    audio_rms DOUBLE PRECISION,
    target_temp DOUBLE PRECISION,
    temp_deadband DOUBLE PRECISION,
    target_hum DOUBLE PRECISION,
    hum_deadband DOUBLE PRECISION,
    co2_threshold DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (node_id, recorded_at)
);

CREATE INDEX IF NOT EXISTS idx_analytics_telemetry_node_recorded_at
    ON public.analytics_telemetry_samples (node_id, recorded_at DESC);

CREATE TABLE IF NOT EXISTS public.analytics_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_key TEXT NOT NULL,
    node_id VARCHAR(100) NOT NULL,
    farm_id UUID,
    farm_name TEXT,
    zone_name TEXT,
    alert_type TEXT NOT NULL
        CHECK (alert_type IN ('threshold_exceeded', 'anomaly_detected')),
    metric TEXT NOT NULL
        CHECK (metric IN ('temperature', 'humidity', 'co2', 'lux')),
    value DOUBLE PRECISION NOT NULL,
    threshold DOUBLE PRECISION,
    direction TEXT NOT NULL,
    baseline JSONB NOT NULL DEFAULT '{}'::jsonb,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_analytics_alert_active_key
    ON public.analytics_alerts (alert_key)
    WHERE resolved_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_analytics_alerts_farm_opened
    ON public.analytics_alerts (farm_id, opened_at DESC);

CREATE TABLE IF NOT EXISTS public.analytics_event_outbox (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(150) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ,
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_analytics_event_outbox_pending
    ON public.analytics_event_outbox (next_attempt_at, created_at)
    WHERE published_at IS NULL;

CREATE TABLE IF NOT EXISTS public.ai_count_snapshots (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    camera_id VARCHAR(100) NOT NULL,
    reported_at TIMESTAMPTZ NOT NULL,
    entry_count BIGINT NOT NULL CHECK (entry_count >= 0),
    exit_count BIGINT NOT NULL CHECK (exit_count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (camera_id, reported_at)
);

CREATE INDEX IF NOT EXISTS idx_ai_count_snapshots_camera_time
    ON public.ai_count_snapshots (camera_id, reported_at DESC);

CREATE TABLE IF NOT EXISTS public.harvest_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farm_id UUID NOT NULL,
    zone_id UUID,
    harvest_date DATE NOT NULL,
    nest_count INTEGER NOT NULL CHECK (nest_count >= 0),
    yield_kg NUMERIC(12, 3) NOT NULL CHECK (yield_kg >= 0),
    notes TEXT,
    recorded_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_harvest_records_farm_date
    ON public.harvest_records (farm_id, harvest_date DESC);

INSERT INTO schema_migrations (version, description)
VALUES (
    '002_analytics_domains',
    'Operational analytics tables (telemetry samples read model, alerts, outbox, AI count snapshots, harvest records)'
)
ON CONFLICT (version) DO NOTHING;

COMMIT;
