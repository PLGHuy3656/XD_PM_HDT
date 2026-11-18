BEGIN;

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

COMMIT;
