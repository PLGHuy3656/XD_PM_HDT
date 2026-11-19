-- ==============================================================================
-- SwiftletCare Isolated PostgreSQL Demo Database Initialization Reference
-- NOTE: Automated Docker init uses infrastructure/postgres/01_init_all.sh
--       with environment-supplied passwords. Supply psql -v variables below
--       if executing manually; never hardcode literal passwords here.
-- ==============================================================================

-- 1. Create Roles & Databases (requires psql -v *_db_password=...)
CREATE USER management_user WITH PASSWORD :'management_db_password';
CREATE DATABASE management_db OWNER management_user;

CREATE USER ai_user WITH PASSWORD :'ai_db_password';
CREATE DATABASE ai_db OWNER ai_user;

CREATE USER notification_user WITH PASSWORD :'notification_db_password';
CREATE DATABASE notification_db OWNER notification_user;

CREATE USER analytics_user WITH PASSWORD :'analytics_db_password';
CREATE DATABASE analytics_db OWNER analytics_user;

CREATE USER analytics_reader WITH PASSWORD :'analytics_reader_password';

-- Grant connection rights
GRANT CONNECT ON DATABASE management_db TO analytics_reader;
GRANT CONNECT ON DATABASE ai_db TO analytics_reader;
GRANT CONNECT ON DATABASE notification_db TO analytics_reader;
