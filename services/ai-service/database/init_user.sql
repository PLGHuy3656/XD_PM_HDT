-- =============================================================================
-- SwiftletCare AI Service — Dedicated Role & Database Provisioning (CP8.2)
-- =============================================================================
-- Least-privilege role: ai_user
-- Dedicated database:   ai_db
-- AI Service MUST NOT access management_db, iot_db, notification_db, or swiftletcare.
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ai_user') THEN
        CREATE ROLE ai_user WITH
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOREPLICATION
            PASSWORD 'CHANGE_ME_AI_PASSWORD';
    END IF;
END
$$;

-- Run from superuser connection to create database if not exists:
-- CREATE DATABASE ai_db OWNER ai_user;

REVOKE ALL ON DATABASE ai_db FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE ai_db TO ai_user;

-- Connect to ai_db before running schema grants:
-- \c ai_db
GRANT USAGE, CREATE ON SCHEMA public TO ai_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ai_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ai_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ai_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO ai_user;
