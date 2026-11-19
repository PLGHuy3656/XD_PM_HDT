-- Migration 003: Add Farm Approval Workflow columns (approval_status, approved_by, approved_at, rejection_reason)
-- Existing farms default to 'APPROVED' so existing operations are preserved.

ALTER TABLE farms
    ADD COLUMN IF NOT EXISTS approval_status VARCHAR(20) NOT NULL DEFAULT 'APPROVED',
    ADD COLUMN IF NOT EXISTS approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS rejection_reason TEXT;

CREATE INDEX IF NOT EXISTS idx_farms_approval_status ON farms(approval_status);
