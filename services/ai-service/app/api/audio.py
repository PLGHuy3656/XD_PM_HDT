"""Opt-in audio anomaly analysis endpoint `POST /api/v1/ai/audio/analyze` (OOP-51)."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from app.errors import ErrorResponse, UNSUPPORTED_MEDIA_TYPE, raise_ai_error
from swiftletcare_ai.audio_monitor import AudioAnalysisResult, SwiftletAudioAnalyzer

router = APIRouter(prefix="/api/v1/ai/audio", tags=["AI Audio"])

MAX_AUDIO_BYTES = 20 * 1024 * 1024  # 20 MB


class AudioAnomalyEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: str
    camera_id: str
    node_id: Optional[str] = None
    detected_at: str
    rms_db: float
    dominant_freq_hz: float
    confidence: float
    severity: str


class AudioAnalyzeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    camera_id: str
    node_id: Optional[str] = None
    sample_rate: int
    duration_seconds: float
    rms_db: float
    target_band_energy_ratio: float
    dominant_freq_hz: float
    anomalies: List[AudioAnomalyEventResponse] = Field(default_factory=list)


def _is_wav_payload(raw: bytes) -> bool:
    return len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WAVE"


def _to_response(result: AudioAnalysisResult) -> AudioAnalyzeResponse:
    return AudioAnalyzeResponse(
        camera_id=result.camera_id,
        node_id=result.node_id,
        sample_rate=result.sample_rate,
        duration_seconds=result.duration_seconds,
        rms_db=result.rms_db,
        target_band_energy_ratio=result.target_band_energy_ratio,
        dominant_freq_hz=result.dominant_freq_hz,
        anomalies=[
            AudioAnomalyEventResponse(
                event_id=a.event_id,
                event_type=a.event_type,
                camera_id=a.camera_id,
                node_id=a.node_id,
                detected_at=a.detected_at,
                rms_db=a.rms_db,
                dominant_freq_hz=a.dominant_freq_hz,
                confidence=a.confidence,
                severity=a.severity,
            )
            for a in result.anomalies
        ],
    )


@router.post(
    "/analyze",
    response_model=AudioAnalyzeResponse,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
    },
    summary="Analyze a .wav audio clip for swiftlet speaker silence or abnormal noise",
)
async def analyze_audio(
    file: UploadFile = File(..., description="WAV audio file (.wav)"),
    cameraId: Optional[str] = Query(default=None, description="Canonical camera identifier"),
    nodeId: Optional[str] = Query(default=None, description="Optional edge audio node identifier"),
    cameraId_form: Optional[str] = Form(default=None, alias="cameraId"),
    nodeId_form: Optional[str] = Form(default=None, alias="nodeId"),
) -> AudioAnalyzeResponse:
    effective_camera_id = (cameraId or cameraId_form or "").strip()
    effective_node_id = (nodeId or nodeId_form or "").strip() or None
    target_id = effective_camera_id or effective_node_id or ""
    if not target_id:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_AUDIO_REQUEST", "message": "Either cameraId or nodeId is required."},
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_AUDIO_PAYLOAD", "message": "Uploaded WAV file is empty."},
        )
    if len(raw) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"code": "AUDIO_TOO_LARGE", "message": f"Audio exceeds max size of {MAX_AUDIO_BYTES} bytes."},
        )
    if not _is_wav_payload(raw):
        raise_ai_error(415, UNSUPPORTED_MEDIA_TYPE, "Only RIFF/WAVE (.wav) audio files are supported.")

    analyzer = SwiftletAudioAnalyzer()
    try:
        result = analyzer.analyze_wav_bytes(
            raw,
            camera_id=target_id,
            node_id=effective_node_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_AUDIO_PAYLOAD", "message": str(exc)},
        ) from exc

    return _to_response(result)
