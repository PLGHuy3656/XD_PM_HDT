import secrets
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response

from app.ai_events import (
    ensure_event_timestamp_is_not_future,
    get_ai_event_detail_data,
    get_ai_events_data,
    store_ai_event,
)
from app.authorization import (
    get_authorized_farms,
    get_authorized_zones,
    get_analytics_device_context,
    get_current_user_id,
    get_monitorable_devices,
)
from app.config import settings
from app.repository import (
    create_harvest_record,
    save_ai_count_snapshot,
    save_bird_track_points,
)
from app.reports import telemetry_csv, telemetry_pdf
from app.schemas import (
    AIAudioEventRequest,
    AICountSnapshotRequest,
    AIDetectionBatchRequest,
    AIDetectionIngestResponse,
    AIEventIngestResponse,
    AIEventResponse,
    AIVisionEventRequest,
    AIEventSource,
    AnalyticsAlertResponse,
    AnalyticsPeriod,
    BirdAnalyticsResponse,
    BirdMovementHistoryResponse,
    HarvestAnalyticsResponse,
    HarvestPeriod,
    HarvestRecordRequest,
    HarvestRecordResponse,
    TelemetryAnalyticsResponse,
)
from app.services import (
    get_alerts_data,
    get_bird_analytics_data,
    get_bird_movement_history_data,
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


def _authenticate_ai_sender(ingest_token: str | None) -> None:
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


def _ingest_ai_event(
    source_type: Literal["vision", "audio"],
    payload: AIVisionEventRequest | AIAudioEventRequest,
    ingest_token: str | None,
) -> JSONResponse:
    _authenticate_ai_sender(ingest_token)
    ensure_event_timestamp_is_not_future(payload.timestamp)
    context = get_analytics_device_context(payload.camera_id)
    event_id = store_ai_event(source_type, payload, context)
    result = AIEventIngestResponse(
        event_id=event_id,
        accepted=event_id is not None,
        duplicate=event_id is None,
    )
    return JSONResponse(
        status_code=(
            status.HTTP_202_ACCEPTED
            if event_id is not None
            else status.HTTP_200_OK
        ),
        content=result.model_dump(mode="json"),
    )


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
    camera_id: str | None = Query(default=None, min_length=1, max_length=100),
    authorization: str = Header(...),
):
    devices = get_monitorable_devices(
        authorization,
        farm_id=farm_id,
        zone_id=zone_id,
    )
    node_ids = [device["node_id"] for device in devices]
    if camera_id is not None and camera_id not in node_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Camera access forbidden",
        )
    return get_bird_analytics_data(
        node_ids,
        period,
        camera_id=camera_id,
    )


@router.get(
    "/bird-movements",
    response_model=BirdMovementHistoryResponse,
    summary="List tracked bird positions for an authorized camera",
)
def list_bird_movements(
    camera_id: str = Query(min_length=1, max_length=100),
    period: AnalyticsPeriod = Query(default="24h"),
    track_id: int | None = Query(default=None, ge=0),
    limit: int = Query(default=500, ge=1, le=2000),
    farm_id: str | None = Query(default=None),
    zone_id: str | None = Query(default=None),
    authorization: str = Header(...),
):
    devices = get_monitorable_devices(
        authorization,
        farm_id=farm_id,
        zone_id=zone_id,
    )
    if camera_id not in {device["node_id"] for device in devices}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Camera access forbidden",
        )
    return get_bird_movement_history_data(
        camera_id,
        period,
        track_id=track_id,
        limit=limit,
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


@router.get(
    "/ai-events",
    response_model=list[AIEventResponse],
    summary="List vision and audio events for authorized devices",
)
def list_ai_events(
    period: AnalyticsPeriod = Query(default="7d"),
    source_type: AIEventSource | None = Query(default=None),
    event_type: Literal[
        "PREDATOR_DETECTED",
        "FLOCK_ANOMALY",
        "AUDIO_ANOMALY",
    ]
    | None = Query(default=None),
    camera_id: str | None = Query(default=None, min_length=1, max_length=100),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    farm_id: str | None = Query(default=None),
    zone_id: str | None = Query(default=None),
    authorization: str = Header(...),
):
    if (start is None) != (end is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start and end must be provided together",
        )
    if start is not None and end is not None:
        if start.utcoffset() is None or end.utcoffset() is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="start and end must include a timezone",
            )
        if start >= end:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="start must be earlier than end",
            )

    devices = get_monitorable_devices(
        authorization,
        farm_id=farm_id,
        zone_id=zone_id,
    )
    node_ids = [device["node_id"] for device in devices]
    if camera_id is not None and camera_id not in node_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Camera access forbidden",
        )
    return get_ai_events_data(
        node_ids,
        period,
        source_type,
        event_type=event_type,
        camera_id=camera_id,
        start=start,
        end=end,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/ai-events/{event_id}",
    response_model=AIEventResponse,
    summary="Get an AI event for an authorized device",
)
def get_ai_event_detail(
    event_id: UUID,
    farm_id: str | None = Query(default=None),
    zone_id: str | None = Query(default=None),
    authorization: str = Header(...),
):
    devices = get_monitorable_devices(
        authorization,
        farm_id=farm_id,
        zone_id=zone_id,
    )
    event = get_ai_event_detail_data(
        [device["node_id"] for device in devices],
        event_id,
    )
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI event not found",
        )
    return event


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
    _authenticate_ai_sender(ingest_token)
    ensure_event_timestamp_is_not_future(payload.timestamp)
    get_analytics_device_context(payload.camera_id)
    reported_at = datetime.fromtimestamp(payload.timestamp, tz=timezone.utc)

    inserted = save_ai_count_snapshot(
        payload.camera_id,
        reported_at,
        payload.entry_count,
        payload.exit_count,
    )
    return {"accepted": inserted, "duplicate": not inserted}


@ai_router.post(
    "/detections",
    response_model=AIDetectionIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Store tracked swiftlet detections for movement history",
)
def ingest_ai_detections(
    payload: AIDetectionBatchRequest,
    ingest_token: str | None = Header(
        default=None,
        alias="X-AI-Ingest-Token",
    ),
):
    _authenticate_ai_sender(ingest_token)
    ensure_event_timestamp_is_not_future(payload.timestamp)
    context = get_analytics_device_context(payload.camera_id)
    accepted, duplicates = save_bird_track_points(
        camera_id=payload.camera_id,
        observed_at=datetime.fromtimestamp(
            payload.timestamp,
            tz=timezone.utc,
        ),
        detections=[
            detection.model_dump()
            for detection in payload.detections
        ],
        context=context,
    )
    return AIDetectionIngestResponse(
        accepted=accepted,
        duplicate=duplicates,
        ignored=len(payload.detections) - accepted - duplicates,
    )


@ai_router.post(
    "/events",
    response_model=AIEventIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Validate, map, store, and publish a vision event",
)
def ingest_vision_event(
    payload: AIVisionEventRequest,
    ingest_token: str | None = Header(
        default=None,
        alias="X-AI-Ingest-Token",
    ),
):
    return _ingest_ai_event("vision", payload, ingest_token)


@ai_router.post(
    "/audio/events",
    response_model=AIEventIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Validate, map, store, and publish an audio anomaly event",
)
def ingest_audio_event(
    payload: AIAudioEventRequest,
    ingest_token: str | None = Header(
        default=None,
        alias="X-AI-Ingest-Token",
    ),
):
    return _ingest_ai_event("audio", payload, ingest_token)


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
