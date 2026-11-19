-- =============================================================================
-- CP8.5 — Notification consumer inbox (durable idempotency)
-- =============================================================================
-- One row per domain event whose effects are committed in notification_db.
-- Written in the same transaction as the alert/notification changes, so the row
-- exists if and only if those changes are committed. No foreign keys (CP8.0).
-- =============================================================================

CREATE TABLE IF NOT EXISTS processed_events (
    event_id VARCHAR(100) PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    producer VARCHAR(50) NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_processed_events_processed_at
    ON processed_events (processed_at);

INSERT INTO schema_migrations (version, description)
VALUES (
    '002_processed_events_inbox',
    'CP8.5 consumer inbox: processed_events committed atomically with notification effects'
)
ON CONFLICT (version) DO NOTHING;
