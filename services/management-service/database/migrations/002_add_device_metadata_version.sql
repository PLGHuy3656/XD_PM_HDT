-- Migration 002: Add metadata_version column and automatic trigger to devices table (CP11.4-B1-R2-MGMT-R2)
-- Enforces database-level monotonic metadata versioning and updated_at maintenance on direct SQL updates.
-- Compatible with PostgreSQL 12 through PostgreSQL 18.

-- 0. Set lock timeout to avoid blocking operational queries indefinitely
SET lock_timeout = '5s';

-- 1. Add monotonic metadata_version column with default 1 (O(1) metadata-only operation in PG11+)
ALTER TABLE devices
ADD COLUMN IF NOT EXISTS metadata_version BIGINT NOT NULL DEFAULT 1;

-- 2. Trigger function to bump metadata_version and updated_at on any UPDATE
CREATE OR REPLACE FUNCTION trg_devices_update_metadata_version()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CLOCK_TIMESTAMP();
    NEW.metadata_version = COALESCE(OLD.metadata_version, 0) + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 3. Attach BEFORE UPDATE trigger to devices
DROP TRIGGER IF EXISTS trg_devices_metadata_version_bump ON devices;
CREATE TRIGGER trg_devices_metadata_version_bump
    BEFORE UPDATE ON devices
    FOR EACH ROW
    EXECUTE FUNCTION trg_devices_update_metadata_version();

-- ROLLBACK INSTRUCTIONS:
-- DROP TRIGGER IF EXISTS trg_devices_metadata_version_bump ON devices;
-- DROP FUNCTION IF EXISTS trg_devices_update_metadata_version();
-- ALTER TABLE devices DROP COLUMN IF EXISTS metadata_version;
