-- =============================================================================
-- CP8.3 — Notification Service Dedicated Database & Least-Privilege User Setup
-- =============================================================================
-- Creates dedicated notification_user and notification_db according to frozen
-- CP8.0 Data Ownership & Persistence Contract V1.
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'notification_user') THEN
        CREATE ROLE notification_user WITH
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOREPLICATION
            PASSWORD 'notification_dev_pass_2026';
    ELSE
        ALTER ROLE notification_user WITH
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOREPLICATION
            PASSWORD 'notification_dev_pass_2026';
    END IF;
END
$$;

-- Note: CREATE DATABASE cannot run inside a DO/transaction block;
-- see apply_migrations.py which executes CREATE DATABASE with autocommit=True.
GRANT ALL PRIVILEGES ON DATABASE notification_db TO notification_user;
