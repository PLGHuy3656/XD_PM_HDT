#!/bin/sh
# INT03: isolated notification_db inside the INT03 Postgres (no cross-service FKs).
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -c "CREATE DATABASE notification_db;"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname notification_db -f /docker-entrypoint-initdb.d/notification_schema.sql.in
