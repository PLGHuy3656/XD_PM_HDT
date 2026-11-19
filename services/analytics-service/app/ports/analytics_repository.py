"""
Repository Port (Interface) for Analytics Service.

Follows Hexagonal / Ports & Adapters Architecture.
The domain and application services depend ONLY on this abstract interface,
allowing seamless swapping between InMemory (Mock Phase 2) and PostgreSQL (Phase 3).
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from app.domain.enums import AlertSeverity, MetricType, PeriodEnum
from app.domain.models import BirdActivityBucket


class IAnalyticsRepository(ABC):
    """
    Abstract interface for retrieving pre-aggregated and historical telemetry data.
    """

    @abstractmethod
    async def get_farm_metadata(self, farm_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves farm metadata including name and zones.
        Returns None if farm does not exist.
        """
        pass

    @abstractmethod
    async def get_bird_activity_buckets(
        self,
        farm_id: str,
        period: PeriodEnum,
    ) -> Tuple[List[BirdActivityBucket], Optional[int], Dict[str, bool]]:
        """
        Retrieves bird activity buckets for the period.

        Returns:
            - List of BirdActivityBucket
            - previous_entries (int or None if no prior observation baseline)
            - coverage_map (Dict[label, bool] mapping time slot to sensor observation health)
        """
        pass

    @abstractmethod
    async def get_zone_climate_averages(
        self,
        farm_id: str,
        period: PeriodEnum,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves average environmental metrics per zone for the period.

        Returns list of dicts:
            {
                "zone_id": str,
                "zone_name": str,
                "avg_temperature": Optional[float],
                "avg_humidity": Optional[float],
                "avg_co2": Optional[float],
            }
        """
        pass

    @abstractmethod
    async def get_alerts(
        self,
        farm_id: str,
        period: PeriodEnum,
    ) -> List[AlertSeverity]:
        """
        Retrieves raw alert occurrences within the evaluation period.
        """
        pass

    @abstractmethod
    async def get_yield_data(
        self,
        farm_id: str,
        period: PeriodEnum,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves harvest yield metrics for the farm.
        Returns None if farm has no harvest records.
        """
        pass

    @abstractmethod
    async def get_trends_data(
        self,
        farm_id: Optional[str],
        period: PeriodEnum,
        zone_id: Optional[str] = None,
        metric: Optional[MetricType] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves multi-dimensional time series trends.
        """
        pass
