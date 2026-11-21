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
