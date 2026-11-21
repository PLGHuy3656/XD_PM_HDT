-- Management Service Database Schema (management_db)
-- Checkpoint 3: Real Database Ownership for Management Domain

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Roles (RBAC)
CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed System Roles
INSERT INTO roles (name, description) VALUES
    ('ADMIN', 'System Administrator with full access'),
    ('FARM_OWNER', 'Owner of swiftlet farming facilities'),
    ('TECHNICIAN', 'Field technician responsible for device maintenance')
ON CONFLICT (name) DO NOTHING;

-- 2. Users (Identity / RBAC)
-- TODO(MANAGEMENT-IDENTITY):
-- Legacy backend lacked an authentication/user persistence table.
-- The schema below establishes the persistent identity foundation.
-- password_hash must store salted hashes (e.g., Argon2id or bcrypt) when auth endpoints are implemented.
-- Plaintext passwords and mock tokens must never be persisted.
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    full_name VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. User Roles (Junction table)
CREATE TABLE IF NOT EXISTS user_roles (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, role_id)
);

-- 4. Farms (Core physical facility)
CREATE TABLE IF NOT EXISTS farms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farm_code VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
    approval_status VARCHAR(20) NOT NULL DEFAULT 'APPROVED',
    approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    rejection_reason TEXT,
    owner_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Zones (Physical sub-areas in a farm)
CREATE TABLE IF NOT EXISTS zones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    zone_code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(farm_id, zone_code)
);

-- 6. Devices (Device Registry & Metadata)
-- Runtime telemetry and latest state belong to IoT Service (iot_db)
CREATE TABLE IF NOT EXISTS devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id VARCHAR(100) UNIQUE NOT NULL,
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    zone_id UUID REFERENCES zones(id) ON DELETE SET NULL,
    name VARCHAR(255),
    device_type VARCHAR(100) NOT NULL DEFAULT 'ENVIRONMENT_MONITOR',
    firmware_version VARCHAR(50),
    ip_address VARCHAR(50),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata_version BIGINT NOT NULL DEFAULT 1
);

-- 7. Technicians (Technician Domain Profile, linked to users)
CREATE TABLE IF NOT EXISTS technicians (
    id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(50),
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 8. Technician Farm Assignments
CREATE TABLE IF NOT EXISTS technician_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    technician_id UUID NOT NULL REFERENCES technicians(id) ON DELETE CASCADE,
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    is_primary BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(technician_id, farm_id)
);

-- Indexes for query optimization
CREATE INDEX IF NOT EXISTS idx_farms_owner_id ON farms(owner_id);
CREATE INDEX IF NOT EXISTS idx_zones_farm_id ON zones(farm_id);
CREATE INDEX IF NOT EXISTS idx_devices_farm_id ON devices(farm_id);
CREATE INDEX IF NOT EXISTS idx_devices_zone_id ON devices(zone_id);
CREATE INDEX IF NOT EXISTS idx_technician_assignments_tech ON technician_assignments(technician_id);
CREATE INDEX IF NOT EXISTS idx_technician_assignments_farm ON technician_assignments(farm_id);


-- Trigger to maintain devices.metadata_version and devices.updated_at on any UPDATE
CREATE OR REPLACE FUNCTION trg_devices_update_metadata_version()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CLOCK_TIMESTAMP();
    NEW.metadata_version = COALESCE(OLD.metadata_version, 0) + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_devices_metadata_version_bump ON devices;
CREATE TRIGGER trg_devices_metadata_version_bump
    BEFORE UPDATE ON devices
    FOR EACH ROW
    EXECUTE FUNCTION trg_devices_update_metadata_version();


-- Migration 004 (INT03-R1): additive, idempotent, safe to re-run.
-- 1) management_event_outbox: business events recorded AFTER the business transaction commits and
--    published to RabbitMQ (exchange swiftlet.domain.events) by a background dispatcher with retry.
-- 2) inspection_requests (+ history): Owner "Yêu cầu kiểm tra" minimum viable workflow
--    NEW -> ACCEPTED -> IN_PROGRESS -> COMPLETED, NEW/ACCEPTED -> CANCELLED (by owner).
-- No existing table/column is altered or dropped. All FKs stay inside management_db.

CREATE TABLE IF NOT EXISTS management_event_outbox (
    id UUID PRIMARY KEY,
    event_type VARCHAR(150) NOT NULL,
    envelope JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'PUBLISHED', 'FAILED')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error TEXT,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_management_event_outbox_pending
    ON management_event_outbox (status, next_attempt_at);

CREATE TABLE IF NOT EXISTS inspection_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_code VARCHAR(30) UNIQUE NOT NULL,
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    zone_id UUID REFERENCES zones(id) ON DELETE SET NULL,
    device_id UUID REFERENCES devices(id) ON DELETE SET NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    priority VARCHAR(10) NOT NULL DEFAULT 'MEDIUM'
        CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')),
    status VARCHAR(20) NOT NULL DEFAULT 'NEW'
        CHECK (status IN ('NEW', 'ACCEPTED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')),
    requested_by UUID NOT NULL REFERENCES users(id),
    assigned_technician_id UUID REFERENCES technicians(id) ON DELETE SET NULL,
    result_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
    accepted_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_inspection_requests_farm ON inspection_requests (farm_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_inspection_requests_tech ON inspection_requests (assigned_technician_id);
CREATE INDEX IF NOT EXISTS idx_inspection_requests_status ON inspection_requests (status);

CREATE TABLE IF NOT EXISTS inspection_request_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES inspection_requests(id) ON DELETE CASCADE,
    from_status VARCHAR(20),
    to_status VARCHAR(20) NOT NULL,
    action VARCHAR(30) NOT NULL,
    actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inspection_request_history_request
    ON inspection_request_history (request_id, created_at);
