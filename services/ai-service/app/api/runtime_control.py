"""Internal runtime execution hook for local E2E manual validation (CP5.4 / CP13).

Mounted with `include_in_schema=False` so public OpenAPI V1 contracts remain unchanged.
Guarded by (CP13 Security & Data Integrity Hardening):
1. Disabled-by-default runtime flag (AI_RUNTIME_INTERNAL_ENABLED=true required).
2. Service key with NO default; must be a provisioned high-entropy secret
   (>= 43 chars, i.e. secrets.token_urlsafe(32)); published/placeholder keys are refused.
3. Caller bearer token is required and forwarded to the authoritative Management
   camera registry (GET /api/cameras/{id}); Management enforces camera type and
   the caller's farm authorization. farmId/zoneId persisted with CountUpdates come
   from the registry, never from the client. Fail-closed when the registry is
   unreachable.
4. Allowlisted source directories (network URLs rejected; allowlist checked before
   existence so the endpoint is not a file-existence oracle).
5. Allowlisted model weights (rejects arbitrary .pt file paths).
"""
from __future__ import annotations

import hmac
import logging
import re
from pathlib import Path
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.config import is_internal_key_acceptable, settings
from app.dependencies import get_camera_registry, get_runtime_manager
from app.ports.camera_registry import (
    CameraNotAuthorized,
    CameraRegistry,
    CameraRegistryUnauthorized,
    CameraRegistryUnavailable,
    RegisteredCamera,
)
from app.runtime.manager import AIRuntimeManager

logger = logging.getLogger("ai-service.runtime_control")

router = APIRouter(include_in_schema=False)
IDENTIFIER_REGEX = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
URL_SCHEME_REGEX = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*://")


class RuntimeRunRequest(BaseModel):
    cameraId: str = Field(..., min_length=1, max_length=100)
    source: str = Field(..., min_length=1)
    sourceType: str = Field(default="auto")
    modelPath: Optional[str] = Field(default="ai-pipeline/models/best.pt")
    repeat: int = Field(default=1, ge=1, le=500)
    fps: float = Field(default=2.0, ge=0.0, le=120.0)
    maxFrames: int = Field(default=0, ge=0)
    # Optional assertion only. If supplied it must match the registry; it is never persisted as-is.
    farmId: Optional[str] = Field(default=None, max_length=100)
    zoneId: Optional[str] = Field(default=None, max_length=100)
    line: Tuple[Tuple[float, float], Tuple[float, float]] = Field(
        default=((0.10, 0.55), (0.90, 0.55))
    )
    insideSide: str = Field(default="positive")
    background: bool = Field(default=True)


def _resolve_candidate(clean: str) -> Path:
    from app.config import AI_PIPELINE_DIR, REPO_ROOT

    candidate = Path(clean)
    if not candidate.is_absolute():
        if (REPO_ROOT / clean).exists():
            candidate = REPO_ROOT / clean
        elif (AI_PIPELINE_DIR / clean).exists():
            candidate = AI_PIPELINE_DIR / clean
        else:
            candidate = REPO_ROOT / clean
    return candidate.resolve()


def _validate_source_path(source_str: str) -> str:
    """Reject network streams; require the resolved file to sit inside an allowlisted directory."""
    clean = source_str.strip()
    if URL_SCHEME_REGEX.match(clean):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Network stream URLs are not permitted in internal runtime trigger",
        )

    try:
        source_path = _resolve_candidate(clean)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid video source path format",
        ) from exc

    allowed = False
    for allowed_dir_str in settings.ai_allowed_source_dirs:
        try:
            allowed_dir = Path(allowed_dir_str).resolve()
            if allowed_dir in source_path.parents:
                allowed = True
                break
        except Exception:
            continue

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to the specified video source path is forbidden (not in allowlist)",
        )

    if not source_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video source file does not exist: '{source_path.name}'",
        )

    return str(source_path)


def _validate_model_path(model_path_str: Optional[str]) -> str:
    """Verify that modelPath resolves to an approved local weights file."""
    from app.config import REPO_ROOT

    approved_default = (REPO_ROOT / "ai-pipeline" / "models" / "best.pt").resolve()
    if not model_path_str or not model_path_str.strip():
        return str(approved_default)

    clean = model_path_str.strip()
    try:
        mp = _resolve_candidate(clean)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid model path format",
        ) from exc

    allowed_resolved = {_resolve_candidate(p) for p in settings.ai_allowed_model_paths}
    allowed_resolved.add(approved_default)
    if mp not in allowed_resolved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Custom model weights path is not permitted (must use allowlisted model)",
        )

    if not mp.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model weights file does not exist: '{mp.name}'",
        )

    return str(mp)


def _require_service_key(x_internal_service_key: Optional[str]) -> None:
    expected_key = (settings.ai_internal_service_key or "").strip()
    if not is_internal_key_acceptable(expected_key):
        # Do not reveal why; never log the key.
        logger.error("Internal runtime refused: AI_INTERNAL_SERVICE_KEY missing or not acceptable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service Unavailable: internal runtime is not configured",
        )
    if not x_internal_service_key or not hmac.compare_digest(
        x_internal_service_key.strip().encode("utf-8"), expected_key.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing or invalid X-Internal-Service-Key",
        )


def _extract_bearer(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: caller bearer token is required for camera registry verification",
        )
    scheme, _, token = authorization.strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: caller bearer token is required for camera registry verification",
        )
    return token.strip()


def _resolve_registered_camera(
    camera_id: str, token: str, registry: CameraRegistry
) -> RegisteredCamera:
    try:
        return registry.resolve_camera(camera_id, token)
    except CameraRegistryUnauthorized as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: caller token rejected by camera registry",
        ) from exc
    except CameraNotAuthorized as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: camera is not registered or not authorized for caller",
        ) from exc
    except CameraRegistryUnavailable as exc:
        logger.warning("Camera registry unavailable (fail closed): %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service Unavailable: camera registry cannot be verified",
        ) from exc


@router.post("/internal/v1/runtime/run")
def run_camera_runtime(
    payload: RuntimeRunRequest,
    request: Request,
    x_internal_service_key: Optional[str] = Header(None, alias="X-Internal-Service-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    runtime_manager: AIRuntimeManager = Depends(get_runtime_manager),
    camera_registry: CameraRegistry = Depends(get_camera_registry),
):
    # 1. Feature flag guard (disabled by default)
    if not settings.ai_runtime_internal_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: AI internal runtime execution is disabled by configuration",
        )

    # 2. Service-to-service authentication (no default key)
    _require_service_key(x_internal_service_key)

    # 3. Caller identity for authoritative registry lookup
    token = _extract_bearer(authorization)

    # 4. Identifier format validation
    camera_id = payload.cameraId.strip()
    if not IDENTIFIER_REGEX.match(camera_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cameraId format")
    for label, value in (("farmId", payload.farmId), ("zoneId", payload.zoneId)):
        if value and not IDENTIFIER_REGEX.match(value.strip()):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid {label} format")

    # 5. Authoritative camera ownership (Management registry). Fail closed.
    registered = _resolve_registered_camera(camera_id, token, camera_registry)
    if payload.farmId and payload.farmId.strip().lower() != registered.farm_id.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: farmId does not match the camera registry",
        )
    if payload.zoneId and (registered.zone_id or "").lower() != payload.zoneId.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: zoneId does not match the camera registry",
        )

    # 6. Source & model allowlists
    validated_source = _validate_source_path(payload.source)
    validated_model = _validate_model_path(payload.modelPath)

    run_kwargs = dict(
        camera_id=registered.node_id,
        source=validated_source,
        source_type=payload.sourceType,
        model_path=validated_model,
        repeat=payload.repeat,
        fps=payload.fps,
        max_frames=payload.maxFrames,
        farm_id=registered.farm_id,
        zone_id=registered.zone_id,
        line=payload.line,
        inside_side=payload.insideSide,
    )

    if payload.background:
        runtime_manager.start_source_in_background(**run_kwargs)
        return {
            "started": True,
            "mode": "background",
            "cameraId": registered.node_id,
            "farmId": registered.farm_id,
            "source": Path(validated_source).name,
            "modelPath": Path(validated_model).name,
            "repeat": payload.repeat,
            "fps": payload.fps,
        }

    status_obj = runtime_manager.run_source(**run_kwargs)
    ws_manager = getattr(request.app.state, "ws_manager", None)
    if ws_manager is not None:
        ws_manager.flush_sync(timeout=2.0)
    return {
        "started": True,
        "mode": "sync",
        "cameraId": registered.node_id,
        "farmId": registered.farm_id,
        "status": status_obj.model_dump(by_alias=True),
    }
