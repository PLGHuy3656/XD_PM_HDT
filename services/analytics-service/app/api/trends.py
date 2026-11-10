"""
Analytics Trends Router.
Endpoints:
- GET /api/v1/analytics/farms/{farm_id}/trends (Farm-scoped)
- GET /api/v1/analytics/trends (Global / Admin-scoped)
"""
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_analytics_service
from app.schemas.trends import FarmAnalyticsTrendsResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics Trends"])


@router.get(
    "/farms/{farm_id}/trends",
    response_model=FarmAnalyticsTrendsResponse,
    summary="Get farm-scoped analytics trends",
)
async def get_farm_trends(
    farm_id: str,
    period: str = Query("today", description="Evaluation period: hour, day, today, week, month, year"),
    zone_id: Optional[str] = Query(None, description="Filter by zone id"),
    metric: Optional[str] = Query(None, description="Filter by metric type"),
    service: Annotated[AnalyticsService, Depends(get_analytics_service)] = None,
) -> FarmAnalyticsTrendsResponse:
    """
    Returns time-series curves for bird activity, microclimate comparison, alerts, and yield.
    """
    return await service.get_trends(
        farm_id=farm_id,
        period_str=period,
        zone_id=zone_id,
        metric_str=metric,
    )


@router.get(
    "/trends",
    response_model=FarmAnalyticsTrendsResponse,
    summary="Get global analytics trends",
)
async def get_global_trends(
    period: str = Query("today", description="Evaluation period: hour, day, today, week, month, year"),
    metric: Optional[str] = Query(None, description="Filter by metric type"),
    service: Annotated[AnalyticsService, Depends(get_analytics_service)] = None,
) -> FarmAnalyticsTrendsResponse:
    """
    Returns global system trends across all farms.
    """
    return await service.get_trends(
        farm_id=None,
        period_str=period,
        zone_id=None,
        metric_str=metric,
    )
