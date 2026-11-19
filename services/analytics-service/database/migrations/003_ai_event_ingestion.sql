BEGIN;

CREATE TABLE IF NOT EXISTS public.ai_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_key CHAR(64) NOT NULL UNIQUE,
    source_event_id UUID,
    source_type TEXT NOT NULL
        CHECK (source_type IN ('vision', 'audio')),
    camera_id VARCHAR(100) NOT NULL,
    event_type VARCHAR(80) NOT NULL,
    label VARCHAR(100) NOT NULL,
    confidence DOUBLE PRECISION NOT NULL
        CHECK (confidence >= 0 AND confidence <= 1),
    observed_at TIMESTAMPTZ NOT NULL,
    farm_id UUID NOT NULL,
    farm_code VARCHAR(100) NOT NULL,
    farm_name VARCHAR(255) NOT NULL,
    zone_id UUID,
    zone_code VARCHAR(100),
    zone_name VARCHAR(255),
    payload JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_events_source_event_id
    ON public.ai_events (source_type, source_event_id)
    WHERE source_event_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ai_events_node_observed_at
    ON public.ai_events (camera_id, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_events_farm_observed_at
    ON public.ai_events (farm_id, observed_at DESC);

INSERT INTO schema_migrations (version, description)
VALUES ('003_ai_event_ingestion', 'AI vision and audio event store with deduplication indexes')
ON CONFLICT (version) DO NOTHING;

COMMIT;
