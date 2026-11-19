#!/bin/bash
set -e

echo "[INIT] Initializing SwiftletCare isolated PostgreSQL demo databases..."

# 1. Create databases and roles
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER management_user WITH PASSWORD 'mgmt_password_2026';
    CREATE DATABASE management_db OWNER management_user;

    CREATE USER ai_user WITH PASSWORD 'ai_dev_pass_2026';
    CREATE DATABASE ai_db OWNER ai_user;

    CREATE USER notification_user WITH PASSWORD 'notification_dev_pass_2026';
    CREATE DATABASE notification_db OWNER notification_user;

    CREATE USER analytics_user WITH PASSWORD 'analytics_password_2026';
    CREATE DATABASE analytics_db OWNER analytics_user;

    CREATE USER analytics_reader WITH PASSWORD 'analytics_reader_secure_pass_2026';
    GRANT CONNECT ON DATABASE management_db TO analytics_reader;
    GRANT CONNECT ON DATABASE ai_db TO analytics_reader;
    GRANT CONNECT ON DATABASE notification_db TO analytics_reader;
EOSQL

echo "[INIT] Applying Management Service schema & seed..."
psql -v ON_ERROR_STOP=1 --username management_user --dbname management_db -f /docker-entrypoint-initdb.d/sql/mgmt_schema.sql
psql -v ON_ERROR_STOP=1 --username management_user --dbname management_db -f /docker-entrypoint-initdb.d/sql/mgmt_seed.sql

echo "[INIT] Applying AI Service schema..."
psql -v ON_ERROR_STOP=1 --username ai_user --dbname ai_db -f /docker-entrypoint-initdb.d/sql/ai_schema.sql

echo "[INIT] Applying Notification Service schema..."
psql -v ON_ERROR_STOP=1 --username notification_user --dbname notification_db -f /docker-entrypoint-initdb.d/sql/notif_schema.sql

echo "[INIT] Applying Analytics Service schema..."
psql -v ON_ERROR_STOP=1 --username analytics_user --dbname analytics_db -f /docker-entrypoint-initdb.d/sql/analytics_schema.sql

echo "[INIT] SwiftletCare isolated PostgreSQL demo databases initialized successfully!"
