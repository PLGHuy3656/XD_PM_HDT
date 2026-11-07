"""Tests verifying Step 4: One-off static image detection analysis endpoint POST /api/v1/ai/analyze."""
from __future__ import annotations

import base64
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.runtime.manager import AIRuntimeManager
from swiftletcare_ai.detector import BaseDetector, CallableDetector
from swiftletcare_ai.schemas import Detection as TV2Detection


def _make_dummy_image_bytes(fmt: str = ".jpg", w: int = 200, h: int = 150) -> bytes:
    img = np.ones((h, w, 3), dtype=np.uint8) * 120
    ok, buf = cv2.imencode(fmt, img)
    assert ok
    return buf.tobytes()


@pytest.fixture
def test_app_and_manager(tmp_path: Path):
    def mock_detect(_img):
        # Return 1 dummy swiftlet and 1 dummy rat
        return [
            TV2Detection("swiftlet", 0.85, [10, 10, 50, 50]),
            TV2Detection("rat", 0.90, [60, 60, 120, 120]),
        ]

    snap_dir = tmp_path / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    from swiftletcare_ai.snapshot import SnapshotStore
    snap_store = SnapshotStore(directory=str(snap_dir), public_base_url="/api/v1/ai/snapshots")

    manager = AIRuntimeManager(
        detector=CallableDetector(mock_detect),
        snapshot_store=snap_store,
    )
    app = create_app(runtime_manager=manager, snapshot_dir=snap_dir)
    return app, manager, snap_dir


def test_analyze_multipart_upload_valid_image(test_app_and_manager):
    """Verify multipart/form-data upload returns canonical DetectionResult without snapshot header."""
    app, manager, snap_dir = test_app_and_manager
    client = TestClient(app)

    jpeg_bytes = _make_dummy_image_bytes(".jpg", w=200, h=150)
    files = {"image": ("sample.jpg", jpeg_bytes, "image/jpeg")}

    res = client.post("/api/v1/ai/analyze?cameraId=CAM-01", files=files)
    assert res.status_code == 200
    data = res.json()

    assert data["cameraId"] == "CAM-01"
    assert data["frameId"] == 0
    assert data["frame"] == {"width": 200, "height": 150}
    assert len(data["detections"]) == 2
    # extra="forbid" constraint check
    assert "timestamp" not in data

    # When annotate=False (default), X-Snapshot-Url must not be present
    assert "X-Snapshot-Url" not in res.headers


def test_analyze_with_annotate_true_generates_snapshot(test_app_and_manager):
    """Verify annotate=True returns X-Snapshot-Url header and writes snapshot file to disk."""
    app, manager, snap_dir = test_app_and_manager
    client = TestClient(app)

    png_bytes = _make_dummy_image_bytes(".png", w=300, h=200)
    files = {"image": ("sample.png", png_bytes, "image/png")}

    res = client.post("/api/v1/ai/analyze?cameraId=CAM-ANN&annotate=true", files=files)
    assert res.status_code == 200

    snap_url = res.headers.get("X-Snapshot-Url")
    assert snap_url is not None
    assert snap_url.startswith("/api/v1/ai/snapshots/")

    # Verify that the generated snapshot can be retrieved via the snapshots endpoint
    filename = snap_url.split("/")[-1]
    res_snap = client.get(f"/api/v1/ai/snapshots/{filename}")
    assert res_snap.status_code == 200
    assert len(res_snap.content) > 0


def test_analyze_json_base64_payload(test_app_and_manager):
    """Verify analyzing image supplied as base64 in JSON body."""
    app, manager, _ = test_app_and_manager
    client = TestClient(app)

    jpeg_bytes = _make_dummy_image_bytes(".jpg", w=160, h=120)
    b64_str = base64.b64encode(jpeg_bytes).decode("ascii")

    payload = {
        "image": f"data:image/jpeg;base64,{b64_str}",
        "cameraId": "CAM-JSON-01",
        "annotate": False,
    }

    res = client.post("/api/v1/ai/analyze", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["cameraId"] == "CAM-JSON-01"
    assert data["frame"]["width"] == 160
    assert data["frame"]["height"] == 120


def test_analyze_raw_body_upload(test_app_and_manager):
    """Verify analyzing raw bytes in request body with image/webp header."""
    app, manager, _ = test_app_and_manager
    client = TestClient(app)

    webp_bytes = _make_dummy_image_bytes(".webp", w=180, h=100)
    res = client.post(
        "/api/v1/ai/analyze?cameraId=CAM-RAW",
        content=webp_bytes,
        headers={"Content-Type": "image/webp"},
    )
    assert res.status_code == 200
    assert res.json()["cameraId"] == "CAM-RAW"
    assert res.json()["frame"]["width"] == 180


def test_analyze_unsupported_media_type_415(test_app_and_manager):
    """Verify unsupported media formats (e.g. text/plain, gif, pdf) return 415 UNSUPPORTED_MEDIA_TYPE."""
    app, _, _ = test_app_and_manager
    client = TestClient(app)

    # Text content pretending to be an image
    fake_files = {"image": ("document.txt", b"Hello plain text world", "text/plain")}
    res = client.post("/api/v1/ai/analyze", files=fake_files)
    assert res.status_code == 415
    detail = res.json()["detail"]
    assert detail["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_analyze_corrupted_image_400(test_app_and_manager):
    """Verify valid magic bytes with corrupted image data returns 400 INVALID_IMAGE_PAYLOAD."""
    app, _, _ = test_app_and_manager
    client = TestClient(app)

    # Valid JPEG header followed by junk
    corrupted_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 30
    files = {"image": ("corrupted.jpg", corrupted_bytes, "image/jpeg")}
    res = client.post("/api/v1/ai/analyze", files=files)
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "INVALID_IMAGE_PAYLOAD"


def test_analyze_image_too_large_400(test_app_and_manager):
    """Verify image payloads exceeding 10 MB return 400 IMAGE_TOO_LARGE."""
    app, _, _ = test_app_and_manager
    client = TestClient(app)

    # 10 MB + 64 bytes
    oversized = b"\xff\xd8\xff\xe0" + (b"\x00" * (10 * 1024 * 1024 + 64))
    files = {"image": ("huge.jpg", oversized, "image/jpeg")}
    res = client.post("/api/v1/ai/analyze", files=files)
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "IMAGE_TOO_LARGE"


def test_analyze_model_not_ready_503(tmp_path: Path):
    """Verify model errors during inference return 503 MODEL_NOT_READY."""
    class FailingDetector(BaseDetector):
        def detect(self, _img):
            raise RuntimeError("CUDA device out of memory or model weights missing")

    manager = AIRuntimeManager(detector=FailingDetector())
    app = create_app(runtime_manager=manager, snapshot_dir=tmp_path / "snaps")
    client = TestClient(app)

    jpeg_bytes = _make_dummy_image_bytes(".jpg")
    files = {"image": ("sample.jpg", jpeg_bytes, "image/jpeg")}
    res = client.post("/api/v1/ai/analyze", files=files)
    assert res.status_code == 503
    assert res.json()["detail"]["code"] == "MODEL_NOT_READY"
