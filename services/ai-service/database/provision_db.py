"""Standalone superuser provisioning helper for AI Service database (`ai_db`).

Must be executed explicitly by an operator with `AI_ADMIN_DATABASE_URL` and
`AI_DB_PASSWORD` provided via environment variables. Never mutates existing role
passwords automatically and never logs credentials.
"""
from __future__ import annotations

import os
import psycopg
from psycopg import sql


def provision_ai_database(admin_url: str, ai_password: str) -> None:
    """Provisions least-privilege `ai_user` role and `ai_db` database safely."""
    if not admin_url or not admin_url.strip():
        raise ValueError("AI_ADMIN_DATABASE_URL is required for database provisioning")
    if not ai_password or len(ai_password.strip()) < 12:
        raise ValueError("AI_DB_PASSWORD must be provided and at least 12 characters long")

    with psycopg.connect(admin_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", ("ai_user",))
            if not cur.fetchone():
                cur.execute(
                    sql.SQL(
                        "CREATE ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB "
                        "NOCREATEROLE NOREPLICATION NOINHERIT PASSWORD {}"
                    ).format(sql.Identifier("ai_user"), sql.Literal(ai_password))
                )

            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", ("ai_db",))
            if not cur.fetchone():
                cur.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {}").format(
                        sql.Identifier("ai_db"), sql.Identifier("ai_user")
                    )
                )
            cur.execute("REVOKE ALL ON DATABASE ai_db FROM PUBLIC")
            cur.execute("GRANT CONNECT, TEMPORARY ON DATABASE ai_db TO ai_user")

    ai_admin_url = admin_url.rsplit("/", 1)[0] + "/ai_db"
    with psycopg.connect(ai_admin_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
            cur.execute("GRANT USAGE, CREATE ON SCHEMA public TO ai_user")
            cur.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ai_user")
            cur.execute("GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO ai_user")
            cur.execute(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ai_user"
            )
            cur.execute(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO ai_user"
            )


if __name__ == "__main__":
    provision_ai_database(
        admin_url=os.environ.get("AI_ADMIN_DATABASE_URL", ""),
        ai_password=os.environ.get("AI_DB_PASSWORD", ""),
    )
    print("[INFO] Provisioned ai_user and ai_db successfully.")
