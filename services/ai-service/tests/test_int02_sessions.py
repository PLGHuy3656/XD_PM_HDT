"""INT02: interactive DEMO_VIDEO / LOCAL_CAMERA sessions on the real AI pipeline."""
from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.runtime.session_sources import LoopingVideoSource, PushFrameSource
import app.api.sessions as sessions_mod

KEY = "A9xK2mP7qR4vW8zB3nL6tY1cF5hJ0dE2sU9wG4kM7pQ"
H = {"X-Internal-Service-Key": KEY}
FIXTURE = Path(settings.ai_demo_video_path)


def _jpeg(w=320, h=240) -> bytes:
    ok, buf = cv2.imencode(".jpg", np.full((h, w, 3), 128, np.uint8))
    assert ok
    return buf.tobytes()


@pytest.fixture
def secured(monkeypatch):
    monkeypatch.setattr(settings, "ai_camera_control_require_auth", True)
    monkeypatch.setattr(settings, "ai_internal_service_key", KEY)
    monkeypatch.setattr(settings, "ai_local_frame_min_interval_s", 0.0)
    sessions_mod._last_frame_at.clear()
    with TestClient(app) as client:
        yield client
        for cam in ("INT02-T1", "INT02-T2", "INT02-T3"):
            client.post(f"/api/v1/ai/cameras/{cam}/stop", headers=H)


def test_session_requires_internal_key(secured):
    r = secured.post("/api/v1/ai/cameras/INT02-T1/sessions", json={"mode": "LOCAL_CAMERA"})
    assert r.status_code == 403
    r = secured.post("/api/v1/ai/cameras/INT02-T1/frames", content=_jpeg(), headers={"Content-Type": "image/jpeg"})
    assert r.status_code == 403


def test_session_rejects_source_injection_and_bad_mode(secured):
    url = "/api/v1/ai/cameras/INT02-T1/sessions"
    for body in (
        {"mode": "LOCAL_CAMERA", "source": "http://169.254.169.254/"},
        {"mode": "DEMO_VIDEO", "sourcePath": "/etc/passwd"},
        {"mode": "LAN_CAMERA"},
        {},
    ):
        assert secured.post(url, json=body, headers=H).status_code == 422, body
    assert secured.post("/api/v1/ai/cameras/bad%2Fid/sessions", json={"mode": "LOCAL_CAMERA"}, headers=H).status_code in (404, 422)


def test_frames_validation(secured):
    url = "/api/v1/ai/cameras/INT02-T2/frames"
    assert secured.post(url, content=_jpeg(), headers={**H, "Content-Type": "image/jpeg"}).status_code == 409
    assert secured.post("/api/v1/ai/cameras/INT02-T2/sessions", json={"mode": "LOCAL_CAMERA"}, headers=H).status_code == 200
    assert secured.post(url, content=b"x", headers={**H, "Content-Type": "text/plain"}).status_code == 415
    assert secured.post(url, content=b"\x00" * (settings.ai_local_frame_max_bytes + 1), headers={**H, "Content-Type": "image/jpeg"}).status_code == 413
    assert secured.post(url, content=b"notajpeg", headers={**H, "Content-Type": "image/jpeg"}).status_code == 400
    assert secured.post(url, content=_jpeg(2000, 1200), headers={**H, "Content-Type": "image/jpeg"}).status_code == 400
    r = secured.post(url, content=_jpeg(), headers={**H, "Content-Type": "image/jpeg"})
    assert r.status_code == 202 and r.json()["accepted"] is True


def test_frame_rate_limit(secured, monkeypatch):
    monkeypatch.setattr(settings, "ai_local_frame_min_interval_s", 5.0)
    secured.post("/api/v1/ai/cameras/INT02-T2/sessions", json={"mode": "LOCAL_CAMERA"}, headers=H)
    url = "/api/v1/ai/cameras/INT02-T2/frames"
    assert secured.post(url, content=_jpeg(), headers={**H, "Content-Type": "image/jpeg"}).status_code == 202
    r = secured.post(url, content=_jpeg(), headers={**H, "Content-Type": "image/jpeg"})
    assert r.status_code == 429


def test_push_source_latest_wins_and_idle_timeout():
    src = PushFrameSource("X", max_queue=2, idle_timeout_s=0.3)
    for _ in range(5):
        assert src.push_jpeg(_jpeg()) is True
    assert src.push_jpeg(b"garbage") is False
    frames = list(iter(src))  # ends after idle timeout
    assert 1 <= len(frames) <= 2
    assert frames[0].image.shape == (240, 320, 3)


@pytest.mark.skipif(not FIXTURE.is_file(), reason="demo fixture not generated")
def test_looping_video_source_reads_fixture():
    src = LoopingVideoSource("X", str(FIXTURE), fps=1000)
    it = iter(src)
    pkt = next(it)
    assert pkt.image is not None and pkt.camera_id == "X"
    src.close()
    with pytest.raises(FileNotFoundError):
        LoopingVideoSource("X", "/nonexistent.avi")


@pytest.mark.skipif(not FIXTURE.is_file(), reason="demo fixture not generated")
def test_demo_video_real_inference_counts(secured):
    r = secured.post("/api/v1/ai/cameras/INT02-T3/sessions", json={"mode": "DEMO_VIDEO", "farmId": "F1", "zoneId": "Z1"}, headers=H)
    assert r.status_code == 200, r.text
    assert r.json()["sourceMode"] == "DEMO_VIDEO"
    deadline = time.time() + 90
    counts = None
    while time.time() < deadline:
        c = secured.get("/api/v1/ai/cameras/INT02-T3/counts/latest")
        if c.status_code == 200 and c.json().get("entryCount", 0) >= 1 and c.json().get("exitCount", 0) >= 1:
            counts = c.json()
            break
        time.sleep(1)
    status = secured.get("/api/v1/ai/cameras/INT02-T3/status").json()
    print("INT02_DEMO_STATUS", {k: status.get(k) for k in ("status", "sourceMode", "processedFrames", "modelName")})
    print("INT02_DEMO_COUNTS", counts)
    assert counts is not None, "real model produced no entry/exit on the bidirectional fixture"
    assert status["sourceMode"] == "DEMO_VIDEO"


# ---------------------------------------------------------------- INT02-F02 uploaded video
import os  # noqa: E402


def _mp4_from_fixture(tmp_path, max_frames=None) -> bytes:
    cap = cv2.VideoCapture(str(FIXTURE))
    fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    out_path = tmp_path / "upload.mp4"
    writer = None
    n = 0
    while True:
        ok, frame = cap.read()
        if not ok or (max_frames and n >= max_frames):
            break
        if writer is None:
            h, w = frame.shape[:2]
            writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
        writer.write(frame)
        n += 1
    cap.release()
    writer.release()
    data = out_path.read_bytes()
    assert data[4:8] == b"ftyp"
    return data


@pytest.fixture
def upload_env(secured, monkeypatch, tmp_path):
    updir = tmp_path / "uploads"
    monkeypatch.setattr(settings, "ai_upload_dir", str(updir))
    monkeypatch.setattr(settings, "ai_upload_max_fps", 50.0)
    return secured, updir


def _post_upload(client, cam, data, ctype="video/mp4", farm="F1"):
    return client.post(f"/api/v1/ai/cameras/{cam}/uploads?farmId={farm}&zoneId=Z1", content=data, headers={**H, "Content-Type": ctype})


def test_upload_requires_internal_key(upload_env):
    client, _ = upload_env
    r = client.post("/api/v1/ai/cameras/INT02-T1/uploads", content=b"x", headers={"Content-Type": "video/mp4"})
    assert r.status_code == 403


def test_upload_rejects_wrong_type_fake_and_oversize(upload_env, monkeypatch):
    client, updir = upload_env
    assert _post_upload(client, "INT02-T1", b"0" * 100, ctype="video/x-msvideo").status_code == 415
    r = _post_upload(client, "INT02-T1", b"RIFF" + b"\x00" * 200)
    assert r.status_code == 415 and r.json()["detail"]["code"] == "UNSUPPORTED_VIDEO_TYPE"
    monkeypatch.setattr(settings, "ai_upload_max_bytes", 1000)
    r = _post_upload(client, "INT02-T1", b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 2000)
    assert r.status_code == 413
    assert not updir.exists() or os.listdir(updir) == []


def test_upload_rejects_corrupt_mp4(upload_env):
    client, updir = upload_env
    r = _post_upload(client, "INT02-T1", b"\x00\x00\x00\x18ftypmp42" + os.urandom(4096))
    assert r.status_code == 400 and r.json()["detail"]["code"] == "VIDEO_UNREADABLE"
    assert os.listdir(updir) == []


@pytest.mark.skipif(not FIXTURE.is_file(), reason="demo fixture not generated")
def test_upload_real_inference_completes_and_cleans_up(upload_env):
    client, updir = upload_env
    data = _mp4_from_fixture(updir.parent)
    r = _post_upload(client, "INT02-T3", data)
    assert r.status_code == 200, r.text
    assert r.json()["sourceMode"] == "UPLOADED_VIDEO"
    assert len(os.listdir(updir)) == 1
    deadline = time.time() + 120
    status = None
    while time.time() < deadline:
        status = client.get("/api/v1/ai/cameras/INT02-T3/status").json()
        if status.get("status") == "OFFLINE" and status.get("sessionEnded") == "COMPLETED":
            break
        time.sleep(1)
    counts = client.get("/api/v1/ai/cameras/INT02-T3/counts/latest")
    print("INT02_UPLOAD_STATUS", {k: status.get(k) for k in ("status", "sourceMode", "sessionEnded", "processedFrames", "modelVersion")})
    print("INT02_UPLOAD_COUNTS", counts.json() if counts.status_code == 200 else counts.status_code)
    assert status["sessionEnded"] == "COMPLETED" and status["sourceMode"] == "UPLOADED_VIDEO"
    assert status["processedFrames"] > 0 and status["modelVersion"] == "best"
    assert counts.status_code == 200 and counts.json()["entryCount"] >= 1 and counts.json()["exitCount"] >= 1
    assert counts.json()["farmId"] == "F1"
    assert os.listdir(updir) == []  # temp file deleted after processing


@pytest.mark.skipif(not FIXTURE.is_file(), reason="demo fixture not generated")
def test_upload_stop_deletes_file_and_new_session_hides_old_counts(upload_env, monkeypatch):
    client, updir = upload_env
    monkeypatch.setattr(settings, "ai_upload_max_fps", 2.0)  # slow so we can stop mid-way
    r = _post_upload(client, "INT02-T2", _mp4_from_fixture(updir.parent))
    assert r.status_code == 200
    time.sleep(1.5)
    assert client.post("/api/v1/ai/cameras/INT02-T2/stop", headers=H).status_code == 200
    time.sleep(0.5)
    assert os.listdir(updir) == []
    st = client.get("/api/v1/ai/cameras/INT02-T2/status").json()
    assert st.get("sessionEnded") is None  # stopped, not completed
    # New (webcam) session on the same camera: no result of the previous session is "latest"
    assert client.post("/api/v1/ai/cameras/INT02-T2/sessions", json={"mode": "LOCAL_CAMERA"}, headers=H).status_code == 200
    assert client.get("/api/v1/ai/cameras/INT02-T2/counts/latest").status_code == 404
    assert client.get("/api/v1/ai/cameras/INT02-T2/detections/latest").status_code == 404


@pytest.mark.skipif(not FIXTURE.is_file(), reason="demo fixture not generated")
def test_upload_concurrency_limit(upload_env, monkeypatch):
    client, updir = upload_env
    monkeypatch.setattr(settings, "ai_upload_max_sessions", 1)
    monkeypatch.setattr(settings, "ai_upload_max_fps", 1.0)
    data = _mp4_from_fixture(updir.parent)
    assert _post_upload(client, "INT02-T1", data).status_code == 200
    r = _post_upload(client, "INT02-T2", data)
    assert r.status_code == 429 and r.json()["detail"]["code"] == "UPLOAD_CONCURRENCY_LIMIT"
    client.post("/api/v1/ai/cameras/INT02-T1/stop", headers=H)
