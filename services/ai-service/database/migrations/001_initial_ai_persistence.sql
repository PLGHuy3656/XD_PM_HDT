-- =============================================================================
-- Migration 001: Initial AI Service Durable Persistence Schema (CP8.2)
-- Database: ai_db
-- Tables:   schema_migrations, ai_count_updates, ai_events
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(64) PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ai_count_updates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id VARCHAR(100) NOT NULL,
    farm_id VARCHAR(100),
    zone_id VARCHAR(100),
    frame_id BIGINT NOT NULL DEFAULT 0 CHECK (frame_id >= 0),
    entry_count INTEGER NOT NULL CHECK (entry_count >= 0),
    exit_count INTEGER NOT NULL CHECK (exit_count >= 0),
    net_change INTEGER NOT NULL CHECK (net_change = entry_count - exit_count),
    delta_entry INTEGER NOT NULL DEFAULT 0 CHECK (delta_entry >= 0),
    delta_exit INTEGER NOT NULL DEFAULT 0 CHECK (delta_exit >= 0),
    window_started_at TIMESTAMPTZ NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_count_updates_camera_recorded_at
    ON ai_count_updates (camera_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_count_updates_camera_window
    ON ai_count_updates (camera_id, window_started_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_count_updates_farm_recorded_at
    ON ai_count_updates (farm_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_count_updates_zone_recorded_at
    ON ai_count_updates (zone_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_count_updates_recorded_at
    ON ai_count_updates (recorded_at DESC);

CREATE TABLE IF NOT EXISTS ai_events (
    event_id VARCHAR(100) PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL CHECK (event_type = 'PREDATOR_DETECTED'),
    camera_id VARCHAR(100) NOT NULL,
    farm_id VARCHAR(100),
    zone_id VARCHAR(100),
    frame_id BIGINT NOT NULL DEFAULT 0 CHECK (frame_id >= 0),
    predator_class VARCHAR(50) NOT NULL CHECK (predator_class IN ('rat', 'snake')),
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    bbox JSONB NOT NULL,
    bbox_x1 DOUBLE PRECISION NOT NULL CHECK (bbox_x1 >= 0.0),
    bbox_y1 DOUBLE PRECISION NOT NULL CHECK (bbox_y1 >= 0.0),
    bbox_x2 DOUBLE PRECISION NOT NULL CHECK (bbox_x2 >= bbox_x1),
    bbox_y2 DOUBLE PRECISION NOT NULL CHECK (bbox_y2 >= bbox_y1),
    snapshot_ref VARCHAR(512),
    detected_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_events_camera_detected_at
    ON ai_events (camera_id, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_events_farm_detected_at
    ON ai_events (farm_id, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_events_type_detected_at
    ON ai_events (event_type, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_events_detected_at
    ON ai_events (detected_at DESC);

INSERT INTO schema_migrations (version, description)
VALUES ('001_initial_ai_persistence', 'Initial CP8.2 AI durable persistence tables (ai_count_updates, ai_events)')
ON CONFLICT (version) DO NOTHING;
