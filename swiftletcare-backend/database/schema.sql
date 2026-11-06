CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS houses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    house_code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS zones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    house_id UUID NOT NULL REFERENCES houses(id) ON DELETE CASCADE,
    zone_code VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id VARCHAR(100) NOT NULL UNIQUE,
    house_id UUID NOT NULL REFERENCES houses(id) ON DELETE CASCADE,
    zone_id UUID REFERENCES zones(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS technicians (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(30),
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS technician_house_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    technician_id UUID NOT NULL REFERENCES technicians(id) ON DELETE CASCADE,
    house_id UUID NOT NULL REFERENCES houses(id) ON DELETE CASCADE,
    is_primary BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (technician_id, house_id)
);

CREATE INDEX IF NOT EXISTS idx_zones_house_id
    ON zones(house_id);

CREATE INDEX IF NOT EXISTS idx_devices_house_id
    ON devices(house_id);

CREATE INDEX IF NOT EXISTS idx_devices_zone_id
    ON devices(zone_id);

CREATE INDEX IF NOT EXISTS idx_technician_assignments_technician
    ON technician_house_assignments(technician_id);

CREATE INDEX IF NOT EXISTS idx_technician_assignments_house
    ON technician_house_assignments(house_id);

-- =========================================================
-- Telemetry history
-- =========================================================

CREATE TABLE IF NOT EXISTS telemetry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    device_id UUID NOT NULL
        REFERENCES devices(id) ON DELETE CASCADE,

    recorded_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    lux DOUBLE PRECISION,
    co2 DOUBLE PRECISION,

    audio_rms DOUBLE PRECISION,
    audio_healthy BOOLEAN,

    actuators JSONB,
    device_state JSONB,
    raw_payload JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_telemetry_device_id
    ON telemetry(device_id);

CREATE INDEX IF NOT EXISTS idx_telemetry_recorded_at
    ON telemetry(recorded_at);


-- =========================================================
-- Latest known state of each device
-- =========================================================

CREATE TABLE IF NOT EXISTS device_latest_state (
    device_id UUID PRIMARY KEY
        REFERENCES devices(id) ON DELETE CASCADE,

    recorded_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    lux DOUBLE PRECISION,
    co2 DOUBLE PRECISION,

    audio_rms DOUBLE PRECISION,
    audio_healthy BOOLEAN,

    actuators JSONB,
    device_state JSONB
);