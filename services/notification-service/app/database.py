"""PostgreSQL database connection helper and settings for Notification Service (CP8.3).

Notification Service connects exclusively to its own dedicated `notification_db`.
It MUST NOT connect to `management_db`, `iot_db`, `ai_db`, `analytics_db`, or
any legacy shared database.
"""
from __future__ import annotations

import itertools
import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterator, Optional

import psycopg
from pydantic import BaseModel, ConfigDict, Field


def _load_dotenv_database_url() -> Optional[str]:
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            if key.strip() == "NOTIFICATION_DATABASE_URL":
                return val.strip().strip('"').strip("'")
    return None


class NotificationDatabaseSettings(BaseModel):
    """Database configuration for Notification Service."""

    model_config = ConfigDict(extra="ignore")

    database_url: str = Field(
        default="",
        description="Dedicated PostgreSQL DSN for notification_db",
    )
    connect_timeout: int = Field(default=5, ge=1)

    @classmethod
    def from_env(cls) -> "NotificationDatabaseSettings":
        url = (
            os.getenv("NOTIFICATION_DATABASE_URL")
            or _load_dotenv_database_url()
            or ""
        ).strip()
        return cls(database_url=url)


logger = logging.getLogger("notification_service.database")


class TransactionScope:
    """A single PostgreSQL transaction shared by every repository call made inside it (CP8.5).

    Opened by `transaction_scope()`. While active (per asyncio task / thread via
    ContextVar), `get_connection()` for the same database returns a `_ScopedConnection`
    bound to this transaction instead of a new connection, so all repository writes
    and the inbox marker commit or roll back together.
    """

    def __init__(self, connection: psycopg.Connection, database_url: str) -> None:
        self.connection = connection
        self.database_url = database_url
        self._sp_counter = itertools.count(1)

    def next_savepoint(self) -> str:
        return f"repo_sp_{next(self._sp_counter)}"


_active_scope: ContextVar[Optional[TransactionScope]] = ContextVar("notification_tx_scope", default=None)


class _ScopedConnection:
    """Connection proxy handed to repositories inside a TransactionScope.

    Repository code keeps its `with get_connection() as conn: ... conn.commit()` style:
    - entering the block opens a SAVEPOINT; leaving it normally releases the savepoint,
      leaving it with an exception rolls back to the savepoint (the outer scope then
      rolls back the whole transaction when the exception propagates);
    - `commit()` only releases the savepoint; the scope performs the single real COMMIT;
    - `rollback()` rolls back to the savepoint, so repository-level recovery such as the
      UniqueViolation merge in PostgreSQLAlertRepository.save keeps working;
    - the underlying connection is never closed by the repository.
    """

    def __init__(self, scope: TransactionScope) -> None:
        self._scope = scope
        self._conn = scope.connection
        self._sp: Optional[str] = None

    def __enter__(self) -> "_ScopedConnection":
        self._sp = self._scope.next_savepoint()
        self._conn.execute(f"SAVEPOINT {self._sp}")
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self._sp is not None and not self._conn.closed:
            if exc_type is not None:
                try:
                    self._conn.execute(f"ROLLBACK TO SAVEPOINT {self._sp}")
                except Exception:  # transaction already unusable; outer scope rolls back
                    pass
            else:
                self._conn.execute(f"RELEASE SAVEPOINT {self._sp}")
        self._sp = None
        return False

    def commit(self) -> None:
        if self._sp is not None:
            self._conn.execute(f"RELEASE SAVEPOINT {self._sp}")
            self._sp = None

    def rollback(self) -> None:
        if self._sp is not None:
            self._conn.execute(f"ROLLBACK TO SAVEPOINT {self._sp}")

    def close(self) -> None:  # owned by the scope
        return None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


def _resolve_url(database_url: Optional[str]) -> str:
    return database_url or NotificationDatabaseSettings.from_env().database_url


def get_connection(
    database_url: Optional[str] = None,
    *,
    autocommit: bool = False,
    connect_timeout: int = 5,
) -> psycopg.Connection:
    """Open a PostgreSQL connection to `notification_db`.

    Inside an active `transaction_scope()` for the same database, returns a proxy bound
    to the scope's transaction instead of a new connection.
    """
    url = _resolve_url(database_url)
    scope = _active_scope.get()
    if scope is not None and not autocommit:
        if scope.database_url == url:
            return _ScopedConnection(scope)  # type: ignore[return-value]
        logger.warning("[DB SCOPE] Connection requested for a different DSN inside a transaction scope; not joined.")
    return psycopg.connect(url, autocommit=autocommit, connect_timeout=connect_timeout)


@contextmanager
def transaction_scope(
    database_url: Optional[str] = None,
    *,
    lock_timeout_ms: Optional[int] = None,
    connect_timeout: int = 5,
) -> Iterator[TransactionScope]:
    """Run a block in one PostgreSQL transaction joined by all repository calls (CP8.5).

    Commits once when the block exits normally, rolls back on any exception.
    Nested scopes are not supported.
    """
    if _active_scope.get() is not None:
        raise RuntimeError("Nested transaction_scope() is not supported")
    url = _resolve_url(database_url)
    conn = psycopg.connect(url, autocommit=False, connect_timeout=connect_timeout)
    scope = TransactionScope(conn, url)
    token = _active_scope.set(scope)
    try:
        if lock_timeout_ms:
            conn.execute(f"SET LOCAL lock_timeout = '{int(lock_timeout_ms)}ms'")
        yield scope
        conn.commit()
    except BaseException:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        _active_scope.reset(token)
        conn.close()


def in_transaction_scope() -> bool:
    return _active_scope.get() is not None


def check_database_health(database_url: Optional[str] = None) -> bool:
    """Return True if `notification_db` is reachable and responds to `SELECT 1`."""
    try:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                row = cur.fetchone()
                return bool(row and row[0] == 1)
    except Exception:
        return False


__all__ = [
    "NotificationDatabaseSettings",
    "TransactionScope",
    "get_connection",
    "in_transaction_scope",
    "transaction_scope",
    "check_database_health",
]
