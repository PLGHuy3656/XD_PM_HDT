"""One-off static image detection analysis endpoint `POST /api/v1/ai/analyze` (AI-FR-001, AI-FR-006, AI-FR-007)."""
from __future__ import annotations

import base64
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile

from app.dependencies import get_runtime_manager
from app.errors import (
    ErrorResponse,
    IMAGE_TOO_LARGE,
    INVALID_IMAGE_PAYLOAD,
    MODEL_NOT_READY,
    UNSUPPORTED_MEDIA_TYPE,
    raise_ai_error,
)
from app.runtime.manager import AIRuntimeManager
from app.schemas.canonical import DetectionResult

router = APIRouter(prefix="/api/v1/ai", tags=["AI Analyze"])

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


def _is_supported_image(raw: bytes) -> bool:
    """Validate image magic bytes for JPEG, PNG, and WebP formats."""
    if len(raw) < 12:
        return False
    if raw.startswith(b"\xff\xd8\xff"):
        return True  # JPEG
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return True  # PNG
    if raw.startswith(b"RIFF") and b"WEBP" in raw[:16]:
        return True  # WebP
    return False


@router.post(
    "/analyze",
    response_model=DetectionResult,
    response_model_by_alias=True,
    responses={
        400: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="Analyze a single image for swiftlets and predators",
)
async def analyze_image(
    request: Request,
    response: Response,
    cameraId: str = Query(default="CAM-01", description="Camera identifier to tag"),
    annotate: bool = Query(default=False, description="Whether to render & save annotated snapshot"),
    runtime_manager: AIRuntimeManager = Depends(get_runtime_manager),
    image: Optional[UploadFile] = File(default=None),
) -> DetectionResult:
    """Analyze a single uploaded image (multipart/form-data, JSON base64, or raw image bytes)."""
    raw_bytes: bytes = b""
    content_type = request.headers.get("content-type", "").lower()

    if image is not None:
        raw_bytes = await image.read()
    elif content_type.startswith("application/json"):
        try:
            data = await request.json()
        except Exception:
            raise_ai_error(400, INVALID_IMAGE_PAYLOAD, "Malformed JSON payload.")
        if not isinstance(data, dict):
            raise_ai_error(400, INVALID_IMAGE_PAYLOAD, "JSON payload must be an object.")
        b64_str = str(data.get("image") or data.get("data") or "").strip()
        if not b64_str:
            raise_ai_error(400, INVALID_IMAGE_PAYLOAD, "Missing 'image' base64 field in JSON payload.")
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        try:
            raw_bytes = base64.b64decode(b64_str)
        except Exception:
            raise_ai_error(400, INVALID_IMAGE_PAYLOAD, "Invalid base64 encoding.")
        if "cameraId" in data:
            cameraId = str(data["cameraId"])
        if "annotate" in data:
            annotate = bool(data["annotate"])
    elif content_type.startswith("multipart/form-data"):
        form = await request.form()
        form_file = form.get("image") or form.get("file")
        if form_file is None or not hasattr(form_file, "read"):
            raise_ai_error(400, INVALID_IMAGE_PAYLOAD, "Missing 'image' file field in multipart upload.")
        raw_bytes = await form_file.read()
    else:
        # Raw bytes request body
        raw_bytes = await request.body()

    if not raw_bytes:
        raise_ai_error(400, INVALID_IMAGE_PAYLOAD, "Image payload is empty.")

    # 1. Size check (<= 10MB)
    if len(raw_bytes) > MAX_IMAGE_BYTES:
        raise_ai_error(
            400,
            IMAGE_TOO_LARGE,
            f"Image size exceeds 10MB limit (provided {len(raw_bytes)} bytes).",
        )

    # 2. Format validation (JPEG, PNG, WebP)
    if not _is_supported_image(raw_bytes):
        raise_ai_error(
            415,
            UNSUPPORTED_MEDIA_TYPE,
            "Unsupported media type. Only image/jpeg, image/png, and image/webp are supported.",
        )

    # 3. Decode OpenCV image
    img = cv2.imdecode(np.frombuffer(raw_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise_ai_error(
            400,
            INVALID_IMAGE_PAYLOAD,
            "Failed to decode image; the image payload is corrupted.",
        )

    # 4. Inference execution
    try:
        result, snapshot_url = runtime_manager.analyze_single_image(
            image=img,
            camera_id=cameraId,
            annotate=annotate,
        )
    except Exception as exc:
        raise_ai_error(
            503,
            MODEL_NOT_READY,
            f"Model inference failed or model is not ready: {exc}",
        )

    if snapshot_url:
        response.headers["X-Snapshot-Url"] = snapshot_url

    return result


__all__ = ["router"]

