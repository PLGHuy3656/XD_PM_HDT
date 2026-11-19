"""Safe read-only snapshot serving route `/api/v1/ai/snapshots/{filename}` (CP5.3 Task 8)."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.dependencies import get_snapshot_dir
from app.errors import (
     ErrorResponse,
    INVALID_SNAPSHOT_PATH,
    SNAPSHOT_NOT_FOUND,
    raise_ai_error,
)

router = APIRouter(prefix="/api/v1/ai/snapshots", tags=["AI Snapshots"])

_ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
_SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


def _resolve_safe_snapshot_path(raw_filename: str, snapshot_dir: Path) -> Path:
    """Validate and resolve a snapshot filename strictly inside `snapshot_dir`."""
    decoded = unquote(raw_filename or "").strip()
    if (
        not decoded
        or ".." in decoded
        or "/" in decoded
        or "\\" in decoded
        or ":" in decoded
        or "\x00" in decoded
        or not _SAFE_FILENAME_RE.match(decoded)
    ):
        raise_ai_error(
            400,
            INVALID_SNAPSHOT_PATH,
            "Invalid snapshot filename; path traversal or directory separators are not allowed.",
        )

    base_dir = snapshot_dir.resolve()
    candidate = (base_dir / decoded).resolve()

    try:
        candidate.relative_to(base_dir)
    except ValueError:
        raise_ai_error(
            400,
            INVALID_SNAPSHOT_PATH,
            "Snapshot path escapes configured snapshot directory.",
        )

    if candidate.parent != base_dir:
        raise_ai_error(
            400,
            INVALID_SNAPSHOT_PATH,
            "Snapshot must reside directly in configured snapshot directory.",
        )

    if candidate.suffix.lower() not in _ALLOWED_SUFFIXES or not candidate.is_file():
        raise_ai_error(
            404,
            SNAPSHOT_NOT_FOUND,
            f"Snapshot '{decoded}' was not found.",
        )

    return candidate


@router.get(
    "/{filename:path}",
    responses={
        200: {"content": {"image/jpeg": {}}},
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Serve an annotated predator snapshot image safely",
)
def get_snapshot_file(
    filename: str,
    snapshot_dir: Path = Depends(get_snapshot_dir),
) -> FileResponse:
    safe_path = _resolve_safe_snapshot_path(filename, snapshot_dir)
    media_type = "image/png" if safe_path.suffix.lower() == ".png" else "image/jpeg"
    return FileResponse(path=str(safe_path), media_type=media_type, filename=safe_path.name)
