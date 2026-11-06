
import psycopg

from app.config import settings


def get_connection():
    if not settings.database_url:
        raise RuntimeError(
            "DATABASE_URL is missing in the .env file"
        )

    return psycopg.connect(
        settings.database_url,
        connect_timeout=8,
    )
