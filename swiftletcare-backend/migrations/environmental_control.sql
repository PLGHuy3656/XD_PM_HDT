
BEGIN;

CREATE TABLE IF NOT EXISTS public.environment_control_configs (
    device_id UUID PRIMARY KEY
        REFERENCES public.devices(id),

    mode TEXT NOT NULL
        CHECK (mode IN ('AUTO', 'MANUAL')),

    target_temp DOUBLE PRECISION,
    target_hum DOUBLE PRECISION,
    temp_deadband DOUBLE PRECISION,
    hum_deadband DOUBLE PRECISION,
    co2_threshold DOUBLE PRECISION,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (target_temp IS NULL OR target_temp BETWEEN -20 AND 80),
    CHECK (target_hum IS NULL OR target_hum BETWEEN 0 AND 100),
    CHECK (temp_deadband IS NULL OR temp_deadband >= 0),
    CHECK (hum_deadband IS NULL OR hum_deadband >= 0),
    CHECK (co2_threshold IS NULL OR co2_threshold >= 0)
);

CREATE TABLE IF NOT EXISTS public.environment_control_commands (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    command_id TEXT NOT NULL UNIQUE,
    device_id UUID NOT NULL
        REFERENCES public.devices(id),

    action TEXT NOT NULL
        CHECK (action IN ('SET_RELAY', 'UPDATE_THRESHOLDS')),

    payload JSONB NOT NULL,

    status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'SUCCESS', 'FAILED', 'TIMEOUT')),

    response JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    acknowledged_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS
    idx_environment_control_commands_device_created
ON public.environment_control_commands (device_id, created_at DESC);

COMMIT;
