-- =============================================================================
-- CP8.3 — Notification Service Canonical Durable PostgreSQL Schema (notification_db)
-- =============================================================================
-- Database-per-Service Boundary:
--   - Owned exclusively by Notification Service (notification_db)
--   - Zero cross-service foreign keys (farm_id, zone_id, device_id, camera_id,
--     user_id are logical scalar external references)
--   - Message idempotency remains in Redis (swiftlet:idempotency:{eventId})
-- =============================================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(100) PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 1. alerts (Durable Operational Alert Lifecycle & Deduplication State)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alerts (
    alert_id VARCHAR(100) PRIMARY KEY,
    event_type VARCHAR(64) NOT NULL,
    source VARCHAR(50) NOT NULL,
    severity VARCHAR(30) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'OPEN',
    farm_id VARCHAR(100) NOT NULL,
    zone_id VARCHAR(100) NULL,
    device_id VARCHAR(100) NULL,
    camera_id VARCHAR(100) NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    snapshot_url VARCHAR(512) NULL,
    telemetry_snapshot JSONB NULL,
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ NULL,
    acknowledged_by VARCHAR(100) NULL,
    resolved_at TIMESTAMPTZ NULL,
    resolved_by VARCHAR(100) NULL,
    resolution_note TEXT NULL,
    source_event_id VARCHAR(100) NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_alerts_event_type CHECK (
        event_type IN (
            'PREDATOR_DETECTED',
            'HIGH_TEMPERATURE',
            'LOW_TEMPERATURE',
            'HIGH_HUMIDITY',
            'LOW_HUMIDITY',
            'AUDIO_FAULT',
            'DEVICE_OFFLINE',
            'COMMAND_FAILED'
        )
    ),
    CONSTRAINT chk_alerts_source CHECK (
        source IN ('AI', 'IOT_ENVIRONMENT', 'IOT_DEVICE')
    ),
    CONSTRAINT chk_alerts_severity CHECK (
        severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')
    ),
    CONSTRAINT chk_alerts_status CHECK (
        status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')
    ),
    CONSTRAINT chk_alerts_occurrence_count CHECK (occurrence_count >= 1)
);

-- Atomic active alert deduplication constraint:
-- At most one active (OPEN or ACKNOWLEDGED) alert per (farm_id, zone_id, source_id, event_type)
CREATE UNIQUE INDEX IF NOT EXISTS uq_alerts_active_dedup_key
    ON alerts (
        farm_id,
        COALESCE(zone_id, ''),
        COALESCE(device_id, camera_id, ''),
        event_type
    )
    WHERE status IN ('OPEN', 'ACKNOWLEDGED');

CREATE INDEX IF NOT EXISTS idx_alerts_farm_status_created_at
    ON alerts (farm_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_alerts_type_status
    ON alerts (event_type, status);

CREATE INDEX IF NOT EXISTS idx_alerts_last_occurred_at
    ON alerts (last_occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_alerts_created_at
    ON alerts (created_at DESC);

-- -----------------------------------------------------------------------------
-- 2. notifications (Durable User Notification Delivery & Read State)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    notification_id VARCHAR(100) PRIMARY KEY,
    alert_id VARCHAR(100) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    channel VARCHAR(30) NOT NULL,
    delivery_status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    failure_reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ NULL,
    read_at TIMESTAMPTZ NULL,
    CONSTRAINT chk_notifications_channel CHECK (
        channel IN ('IN_APP', 'FCM')
    ),
    CONSTRAINT chk_notifications_delivery_status CHECK (
        delivery_status IN ('PENDING', 'SENT', 'DELIVERED', 'FAILED', 'SUPPRESSED')
    )
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_created_at
    ON notifications (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notifications_alert_created_at
    ON notifications (alert_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notifications_user_read_at
    ON notifications (user_id, read_at);

-- -----------------------------------------------------------------------------
-- 3. user_devices (Durable FCM Device Token Registrations)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_devices (
    device_id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    fcm_token VARCHAR(255) UNIQUE NOT NULL,
    platform VARCHAR(30) NOT NULL,
    device_name VARCHAR(100) NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_user_devices_platform CHECK (
        platform IN ('WEB', 'ANDROID', 'IOS')
    )
);

CREATE INDEX IF NOT EXISTS idx_user_devices_user_enabled
    ON user_devices (user_id, is_enabled);

-- CP8.5 consumer inbox (migration 002_processed_events_inbox)
CREATE TABLE IF NOT EXISTS processed_events (
    event_id VARCHAR(100) PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    producer VARCHAR(50) NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_processed_events_processed_at
    ON processed_events (processed_at);
