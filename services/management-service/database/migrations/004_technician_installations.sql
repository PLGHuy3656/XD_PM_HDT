BEGIN;

CREATE TABLE IF NOT EXISTS technician_installations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id UUID NOT NULL UNIQUE
        REFERENCES devices(id) ON DELETE CASCADE,
    technician_id UUID NOT NULL
        REFERENCES technicians(id) ON DELETE CASCADE,
    farm_id UUID NOT NULL
        REFERENCES farms(id) ON DELETE CASCADE,
    zone_id UUID REFERENCES zones(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'REGISTERED'
        CHECK (
            status IN (
                'REGISTERED',
                'CONFIGURED',
                'ACTIVATED',
                'VALIDATED',
                'HANDED_OVER'
            )
        ),
    configuration JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(configuration) = 'object'),
    validation_report JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(validation_report) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    configured_at TIMESTAMPTZ,
    activated_at TIMESTAMPTZ,
    validated_at TIMESTAMPTZ,
    handed_over_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_technician_installations_owner_recent
    ON technician_installations (technician_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_technician_installations_farm_status
    ON technician_installations (farm_id, status);

COMMIT;
