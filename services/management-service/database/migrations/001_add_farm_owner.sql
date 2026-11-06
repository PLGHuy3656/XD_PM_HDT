-- Migration 001: Add owner_id to farms table
-- Establishes FarmOwner 1 -> N Farm relationship with users(id)

ALTER TABLE farms
ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_farms_owner_id ON farms(owner_id);
