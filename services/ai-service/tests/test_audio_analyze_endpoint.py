"""Unit tests for POST /api/v1/ai/audio/analyze endpoint (OOP-51)."""
from __future__ import annotations

import io
from pathlib import Path
import wave

from fastapi.testclient import TestClient
import numpy as np

from app.main import create_app
from app.runtime.manager import AIRuntimeManager
from swiftletcare_ai.detector import CallableDetector
from swiftletcare_ai.snapshot import SnapshotStore


def _make_wav_bytes(freq_hz: float, duration_s: float = 1.5, sample_rate: int = 16000, amp: float = 0.4) -> bytes:
    t = np.linspace(0.0, duration_s, int(sample_rate * duration_s), endpoint=False)
    samples = amp * np.sin(2.0 * np.pi * freq_hz * t)
    pcm = np.clip(samples * 32767.0, -32768, 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def _make_test_client(tmp_path: Path) -> TestClient:
    manager = AIRuntimeManager(
        detector=CallableDetector(lambda img: [], names={0: "swiftlet"}),
        snapshot_store=SnapshotStore(tmp_path / "snapshots"),
    )
    app = create_app(
        runtime_manager=manager,
        snapshot_dir=tmp_path / "snapshots",
        load_configured_cameras=False,
    )
    return TestClient(app)


def test_audio_analyze_normal_and_anomalies(tmp_path: Path):
    with _make_test_client(tmp_path) as client:
        # 1. Normal swiftlet band (3200 Hz)
        normal_wav = _make_wav_bytes(3200.0, amp=0.4)
        res_ok = client.post(
            "/api/v1/ai/audio/analyze",
            params={"cameraId": "CAM-01", "nodeId": "NODE-01"},
            files={"file": ("normal.wav", normal_wav, "audio/wav")},
        )
        assert res_ok.status_code == 200
        body_ok = res_ok.json()
        assert body_ok["camera_id"] == "CAM-01"
        assert body_ok["node_id"] == "NODE-01"
        assert body_ok["anomalies"] == []

        # 2. Silence -> SPEAKER_SILENCE
        silence_wav = _make_wav_bytes(3200.0, amp=0.0)
        res_sil = client.post(
            "/api/v1/ai/audio/analyze",
            params={"nodeId": "NODE-02"},
            files={"file": ("silence.wav", silence_wav, "audio/wav")},
        )
        assert res_sil.status_code == 200
        body_sil = res_sil.json()
        assert body_sil["camera_id"] == "NODE-02"
        assert len(body_sil["anomalies"]) == 1
        assert body_sil["anomalies"][0]["event_type"] == "SPEAKER_SILENCE"

        # 3. Loud out-of-band noise (400 Hz) -> ABNORMAL_NOISE
        noise_wav = _make_wav_bytes(400.0, amp=0.6)
        res_noise = client.post(
            "/api/v1/ai/audio/analyze",
            params={"cameraId": "CAM-03"},
            files={"file": ("noise.wav", noise_wav, "audio/wav")},
        )
        assert res_noise.status_code == 200
        body_noise = res_noise.json()
        assert len(body_noise["anomalies"]) == 1
        assert body_noise["anomalies"][0]["event_type"] == "ABNORMAL_NOISE"


def test_audio_analyze_validation_errors(tmp_path: Path):
    with _make_test_client(tmp_path) as client:
        wav = _make_wav_bytes(3200.0)

        # Missing cameraId and nodeId -> 400
        r_missing = client.post(
            "/api/v1/ai/audio/analyze",
            files={"file": ("ok.wav", wav, "audio/wav")},
        )
        assert r_missing.status_code == 400

        # Non-WAV payload -> 415
        r_bad_type = client.post(
            "/api/v1/ai/audio/analyze",
            params={"cameraId": "CAM-01"},
            files={"file": ("bad.mp3", b"ID3-not-a-wav-file", "audio/mpeg")},
        )
        assert r_bad_type.status_code == 415
