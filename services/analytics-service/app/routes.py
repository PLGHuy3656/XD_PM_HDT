import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, status
from fastapi.responses import Response

from app.authorization import (
    get_authorized_farms,
    get_authorized_zones,
    get_current_user_id,
    get_monitorable_devices,
)
from app.config import settings
from app.repository import create_harvest_record, save_ai_count_snapshot
from app.reports import telemetry_csv, telemetry_pdf
from app.schemas import (
    AICountSnapshotRequest,
    AnalyticsAlertResponse,
    AnalyticsPeriod,
    BirdAnalyticsResponse,
    HarvestAnalyticsResponse,
    HarvestPeriod,
    HarvestRecordRequest,
    HarvestRecordResponse,
    TelemetryAnalyticsResponse,
)
from app.services import (
    get_alerts_data,
    get_bird_analytics_data,
    get_harvest_analytics_data,
    get_telemetry_analytics_data,
)


router = APIRouter(
    prefix="/api/analytics",
    tags=["Analytics"],
)
ai_router = APIRouter(prefix="/api/ai", tags=["AI ingestion"])


def _authorized_farm_ids(
    authorization: str,
    farm_id: str | None,
    zone_id: str | None,
) -> list[str]:
    if zone_id is not None and farm_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="farm_id is required when filtering by zone_id",
        )

    farms = get_authorized_farms(authorization)
    farm_ids = [str(farm["farm_id"]) for farm in farms]
    if farm_id is not None:
        if farm_id not in farm_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Farm access forbidden",
            )
        farm_ids = [farm_id]

    if zone_id is not None:
        zones = get_authorized_zones(authorization, farm_id)
        if zone_id not in {str(zone["zone_id"]) for zone in zones}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Zone access forbidden",
            )

    return farm_ids


@router.get(
    "/telemetry",
    response_model=TelemetryAnalyticsResponse,
    summary="Aggregate environmental telemetry for authorized devices",
)
def get_telemetry_analytics(
    period: AnalyticsPeriod = Query(default="24h"),
    farm_id: str | None = Query(default=None),
    zone_id: str | None = Query(default=None),
    authorization: str = Header(...),
):
    devices = get_monitorable_devices(
        authorization,
        farm_id=farm_id,
        zone_id=zone_id,
    )
    return get_telemetry_analytics_data(
        [device["node_id"] for device in devices],
        period,
    )


@router.get(
    "/telemetry/report.csv",
    summary="Download authorized telemetry analytics as CSV",
)
def download_telemetry_csv(
    period: AnalyticsPeriod = Query(default="24h"),
    farm_id: str | None = Query(default=None),
    zone_id: str | None = Query(default=None),
    authorization: str = Header(...),
):
    analytics = _get_telemetry_data(authorization, period, farm_id, zone_id)
    return Response(
        content=telemetry_csv(analytics),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="analytics-{period}.csv"'
            ),
        },
    )


@router.get(
    "/telemetry/report.pdf",
    summary="Download authorized telemetry analytics as PDF",
)
def download_telemetry_pdf(
    period: AnalyticsPeriod = Query(default="24h"),
    farm_id: str | None = Query(default=None),
    zone_id: str | None = Query(default=None),
    authorization: str = Header(...),
):
    analytics = _get_telemetry_data(authorization, period, farm_id, zone_id)
    return Response(
        content=telemetry_pdf(analytics),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="analytics-{period}.pdf"'
            ),
        },
    )


def _get_telemetry_data(
    authorization: str,
    period: AnalyticsPeriod,
    farm_id: str | None,
    zone_id: str | None,
) -> dict:
    devices = get_monitorable_devices(
        authorization,
        farm_id=farm_id,
        zone_id=zone_id,
    )
    return get_telemetry_analytics_data(
        [device["node_id"] for device in devices],
        period,
    )


@router.get(
    "/birds",
    response_model=BirdAnalyticsResponse,
    summary="Aggregate AI bird counts for authorized devices",
)
def get_bird_analytics(
    period: AnalyticsPeriod = Query(default="24h"),
    farm_id: str | None = Query(default=None),
    zone_id: str | None = Query(default=None),
    authorization: str = Header(...),
):
    devices = get_monitorable_devices(
        authorization,
        farm_id=farm_id,
        zone_id=zone_id,
    )
    return get_bird_analytics_data(
        [device["node_id"] for device in devices],
        period,
    )


@router.get(
    "/alerts",
    response_model=list[AnalyticsAlertResponse],
    summary="List environmental alerts for authorized devices",
)
def get_alerts(
    period: AnalyticsPeriod = Query(default="7d"),
    farm_id: str | None = Query(default=None),
    zone_id: str | None = Query(default=None),
    authorization: str = Header(...),
):
    devices = get_monitorable_devices(
        authorization,
        farm_id=farm_id,
        zone_id=zone_id,
    )
    return get_alerts_data(
        [device["node_id"] for device in devices],
        period,
    )


@ai_router.post(
    "/counts",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest cumulative bird counts from the AI pipeline",
)
def ingest_ai_counts(
    payload: AICountSnapshotRequest,
    ingest_token: str | None = Header(
        default=None,
        alias="X-AI-Ingest-Token",
    ),
):
    expected_token = settings.ai_ingest_token
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI ingestion is not configured",
        )
    if not ingest_token or not secrets.compare_digest(
        ingest_token,
        expected_token,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid AI ingestion credentials",
        )

    reported_at = datetime.fromtimestamp(payload.timestamp, tz=timezone.utc)
    if reported_at > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="AI count timestamp cannot be in the future",
        )

    inserted = save_ai_count_snapshot(
        payload.camera_id,
        reported_at,
        payload.entry_count,
        payload.exit_count,
    )
    return {"accepted": inserted, "duplicate": not inserted}


@router.get(
    "/harvest",
    response_model=HarvestAnalyticsResponse,
    summary="Summarize recorded harvests for authorized farms",
)
def get_harvest_analytics(
    period: HarvestPeriod = Query(default="90d"),
    farm_id: str | None = Query(default=None),
    zone_id: str | None = Query(default=None),
    authorization: str = Header(...),
):
    farm_ids = _authorized_farm_ids(authorization, farm_id, zone_id)
    return get_harvest_analytics_data(farm_ids, period, zone_id)


@router.post(
    "/harvest",
    response_model=HarvestRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record an actual harvest",
)
def create_harvest(
    payload: HarvestRecordRequest,
    authorization: str = Header(...),
):
    farm_id = str(payload.farm_id)
    zone_id = str(payload.zone_id) if payload.zone_id else None
    _authorized_farm_ids(authorization, farm_id, zone_id)
    recorded_by = UUID(get_current_user_id(authorization))
    return create_harvest_record(
        farm_id=payload.farm_id,
        zone_id=payload.zone_id,
        harvest_date=payload.harvest_date,
        nest_count=payload.nest_count,
        yield_kg=payload.yield_kg,
        notes=payload.notes,
        recorded_by=recorded_by,
    )
