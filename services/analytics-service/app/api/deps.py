"""
Dependency injection provider for Analytics Service.
Supports dynamic switching between InMemory and PostgreSQL repositories via configuration.
"""
import os
from typing import Annotated, Optional
from fastapi import Depends

from app.ports.analytics_repository import IAnalyticsRepository
from app.repositories.in_memory_repository import InMemoryAnalyticsRepository
from app.repositories.postgresql_repository import PostgreSQLAnalyticsRepository
from app.services.analytics_service import AnalyticsService

_in_memory_instance: Optional[IAnalyticsRepository] = None
_postgres_instance: Optional[IAnalyticsRepository] = None


def reset_repository_instances() -> None:
    """Resets cached repository instances (used for test isolation)."""
    global _in_memory_instance, _postgres_instance
    _in_memory_instance = None
    _postgres_instance = None


def get_analytics_repository() -> IAnalyticsRepository:
    """
    Provides repository instance:
    - If ANALYTICS_REPOSITORY_TYPE == 'postgres': strictly instantiates PostgreSQLAnalyticsRepository.
      Zero silent fallback to InMemory.
    - If ANALYTICS_DATABASE_URL is set and ANALYTICS_REPOSITORY_TYPE != 'memory': uses PostgreSQL.
    - Otherwise (default / 'memory'): uses InMemoryAnalyticsRepository.
    """
    global _in_memory_instance, _postgres_instance

    repo_type = os.getenv("ANALYTICS_REPOSITORY_TYPE", "").lower().strip()
    db_url = os.getenv("ANALYTICS_DATABASE_URL")

    if repo_type == "postgres":
        if _postgres_instance is None:
            _postgres_instance = PostgreSQLAnalyticsRepository(database_url=db_url)
        return _postgres_instance

    if repo_type != "memory" and db_url:
        if _postgres_instance is None:
            _postgres_instance = PostgreSQLAnalyticsRepository(database_url=db_url)
        return _postgres_instance

    if _in_memory_instance is None:
        _in_memory_instance = InMemoryAnalyticsRepository()
    return _in_memory_instance


def get_analytics_service(
    repo: Annotated[IAnalyticsRepository, Depends(get_analytics_repository)],
) -> AnalyticsService:
    """Provides application service instance."""
    return AnalyticsService(repository=repo)
