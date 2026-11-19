#!/bin/bash
set -e

echo "[INIT] Initializing SwiftletCare isolated PostgreSQL demo databases..."

# Validate required environment variables from Docker Compose
: "${POSTGRES_USER:?POSTGRES_USER must be set}"
: "${POSTGRES_DB:?POSTGRES_DB must be set}"
: "${MANAGEMENT_DB_PASSWORD:?MANAGEMENT_DB_PASSWORD must be set}"
: "${AI_DB_PASSWORD:?AI_DB_PASSWORD must be set}"
: "${NOTIFICATION_DB_PASSWORD:?NOTIFICATION_DB_PASSWORD must be set}"
: "${ANALYTICS_DB_PASSWORD:?ANALYTICS_DB_PASSWORD must be set}"
: "${ANALYTICS_READER_PASSWORD:?ANALYTICS_READER_PASSWORD must be set}"

# 1. Create databases and roles with passwords supplied from environment
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER management_user WITH PASSWORD '$MANAGEMENT_DB_PASSWORD';
    CREATE DATABASE management_db OWNER management_user;

    CREATE USER ai_user WITH PASSWORD '$AI_DB_PASSWORD';
    CREATE DATABASE ai_db OWNER ai_user;

    CREATE USER notification_user WITH PASSWORD '$NOTIFICATION_DB_PASSWORD';
    CREATE DATABASE notification_db OWNER notification_user;

    CREATE USER analytics_user WITH PASSWORD '$ANALYTICS_DB_PASSWORD';
    CREATE DATABASE analytics_db OWNER analytics_user;

    CREATE USER analytics_reader WITH PASSWORD '$ANALYTICS_READER_PASSWORD';
    GRANT CONNECT ON DATABASE management_db TO analytics_reader;
    GRANT CONNECT ON DATABASE ai_db TO analytics_reader;
    GRANT CONNECT ON DATABASE notification_db TO analytics_reader;
EOSQL

echo "[INIT] Applying Management Service schema & seed..."
PGPASSWORD="$MANAGEMENT_DB_PASSWORD" psql -v ON_ERROR_STOP=1 --username management_user --dbname management_db -f /docker-entrypoint-initdb.d/sql/mgmt_schema.sql
PGPASSWORD="$MANAGEMENT_DB_PASSWORD" psql -v ON_ERROR_STOP=1 --username management_user --dbname management_db -f /docker-entrypoint-initdb.d/sql/mgmt_seed.sql

echo "[INIT] Applying AI Service schema..."
PGPASSWORD="$AI_DB_PASSWORD" psql -v ON_ERROR_STOP=1 --username ai_user --dbname ai_db -f /docker-entrypoint-initdb.d/sql/ai_schema.sql

echo "[INIT] Applying Notification Service schema..."
PGPASSWORD="$NOTIFICATION_DB_PASSWORD" psql -v ON_ERROR_STOP=1 --username notification_user --dbname notification_db -f /docker-entrypoint-initdb.d/sql/notif_schema.sql

echo "[INIT] Applying Analytics Service schema..."
PGPASSWORD="$ANALYTICS_DB_PASSWORD" psql -v ON_ERROR_STOP=1 --username analytics_user --dbname analytics_db -f /docker-entrypoint-initdb.d/sql/analytics_schema.sql

echo "[INIT] SwiftletCare isolated PostgreSQL demo databases initialized successfully!"
