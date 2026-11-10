"""
Farm Analytics Summary Router.
Endpoint: GET /api/v1/analytics/farms/{farm_id}/summary
"""
from typing import Annotated
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_analytics_service
from app.schemas.summary import FarmAnalyticsSummaryResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics Summary"])


@router.get(
    "/farms/{farm_id}/summary",
    response_model=FarmAnalyticsSummaryResponse,
    summary="Get farm analytics summary",
)
async def get_farm_summary(
    farm_id: str,
    period: str = Query("day", description="Evaluation period: hour, day, today, week, month, year"),
    service: Annotated[AnalyticsService, Depends(get_analytics_service)] = None,
) -> FarmAnalyticsSummaryResponse:
    """
    Returns aggregated bird activity, microclimate scores, alert distribution, and yield.
    Missing metrics are serialized to JSON null.
    """
    return await service.get_farm_summary(farm_id=farm_id, period_str=period)
