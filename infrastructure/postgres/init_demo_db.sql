-- ==============================================================================
-- SwiftletCare Isolated PostgreSQL Demo Database Initialization (CP14-B)
-- ==============================================================================

-- 1. Create Roles & Databases
CREATE USER management_user WITH PASSWORD 'mgmt_password_2026';
CREATE DATABASE management_db OWNER management_user;

CREATE USER ai_user WITH PASSWORD 'ai_dev_pass_2026';
CREATE DATABASE ai_db OWNER ai_user;

CREATE USER notification_user WITH PASSWORD 'notification_dev_pass_2026';
CREATE DATABASE notification_db OWNER notification_user;

CREATE USER analytics_user WITH PASSWORD 'analytics_password_2026';
CREATE DATABASE analytics_db OWNER analytics_user;

CREATE USER analytics_reader WITH PASSWORD 'analytics_reader_secure_pass_2026';

-- Grant connection rights
GRANT CONNECT ON DATABASE management_db TO analytics_reader;
GRANT CONNECT ON DATABASE ai_db TO analytics_reader;
GRANT CONNECT ON DATABASE notification_db TO analytics_reader;
