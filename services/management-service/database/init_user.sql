-- Management Service Database User Provisioning
-- Checkpoint 3: Dedicated Non-Superuser Principal
-- Run this script as PostgreSQL superuser (e.g. postgres) to provision management_user.
-- Parameterize or replace 'CHANGE_ME_MANAGEMENT_PASSWORD' with a secure secret in deployment.

-- 1. Create Role / User
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'management_user') THEN
        CREATE ROLE management_user WITH
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOINHERIT
            PASSWORD 'CHANGE_ME_MANAGEMENT_PASSWORD';
    END IF;
END
$$;

-- 2. Grant Database Connection
GRANT CONNECT ON DATABASE management_db TO management_user;

-- 3. Grant Schema & Table Privileges within management_db
-- Ensure connection context is management_db when executing the statements below:
\c management_db

GRANT USAGE, CREATE ON SCHEMA public TO management_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO management_user;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO management_user;

-- 4. Default Privileges for Future Tables and Sequences
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO management_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO management_user;
