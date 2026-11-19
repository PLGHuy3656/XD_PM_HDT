"""Unit tests for swiftletcare_ai.audio_monitor (OOP-51)."""
from __future__ import annotations

import ast
import io
from pathlib import Path
import wave

import numpy as np
import pytest

from swiftletcare_ai.audio_monitor import (
    ABNORMAL_NOISE,
    AudioAnalysisConfig,
    SPEAKER_SILENCE,
    SwiftletAudioAnalyzer,
)


def _sine_wave(freq_hz: float, duration_s: float = 1.5, sample_rate: int = 16000, amp: float = 0.5) -> np.ndarray:
    t = np.linspace(0.0, duration_s, int(sample_rate * duration_s), endpoint=False)
    return amp * np.sin(2.0 * np.pi * freq_hz * t)


def _to_wav_bytes(samples: np.ndarray, sample_rate: int = 16000, channels: int = 1) -> bytes:
    pcm = np.clip(samples * 32767.0, -32768, 32767).astype("<i2")
    if channels == 2:
        pcm = np.column_stack([pcm, pcm]).ravel()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def test_normal_swiftlet_band_has_no_anomalies():
    analyzer = SwiftletAudioAnalyzer()
    samples = _sine_wave(3200.0, duration_s=1.5, amp=0.4)
    res = analyzer.analyze(samples, sample_rate=16000, camera_id="CAM-01", node_id="NODE-01")

    assert res.camera_id == "CAM-01"
    assert res.node_id == "NODE-01"
    assert res.target_band_energy_ratio > 0.85
    assert 3100.0 <= res.dominant_freq_hz <= 3300.0
    assert res.anomalies == []


def test_speaker_silence_triggers_anomaly():
    cfg = AudioAnalysisConfig(silence_rms_db_threshold=-45.0, silence_min_consecutive_windows=3)
    analyzer = SwiftletAudioAnalyzer(config=cfg)
    silent = np.zeros(16000 * 2, dtype=np.float64)
    res = analyzer.analyze(silent, sample_rate=16000, camera_id="CAM-01")

    assert len(res.anomalies) == 1
    ev = res.anomalies[0]
    assert ev.event_type == SPEAKER_SILENCE
    assert ev.camera_id == "CAM-01"
    assert ev.detected_at.endswith("Z")
    assert ev.rms_db < -45.0
    assert 0.0 < ev.confidence <= 1.0
    assert ev.severity in {"MEDIUM", "HIGH"}


def test_abnormal_out_of_band_noise_triggers_anomaly():
    cfg = AudioAnalysisConfig(
        abnormal_noise_rms_db_threshold=-25.0,
        abnormal_out_of_band_ratio_threshold=0.65,
        abnormal_min_consecutive_windows=2,
    )
    analyzer = SwiftletAudioAnalyzer(config=cfg)
    loud_low_freq = _sine_wave(450.0, duration_s=1.5, amp=0.6)
    res = analyzer.analyze(loud_low_freq, sample_rate=16000, camera_id="CAM-02")

    assert len(res.anomalies) == 1
    ev = res.anomalies[0]
    assert ev.event_type == ABNORMAL_NOISE
    assert ev.camera_id == "CAM-02"
    assert 400.0 <= ev.dominant_freq_hz <= 500.0
    assert res.target_band_energy_ratio < 0.1


def test_analyze_stereo_wav_bytes_and_invalid_wav():
    analyzer = SwiftletAudioAnalyzer()
    wav_bytes = _to_wav_bytes(_sine_wave(3500.0, duration_s=1.2, amp=0.35), channels=2)
    res = analyzer.analyze_wav_bytes(wav_bytes, camera_id="CAM-03")
    assert res.anomalies == []
    assert res.sample_rate == 16000

    with pytest.raises(ValueError):
        analyzer.analyze_wav_bytes(b"not-a-wav", camera_id="CAM-03")


def test_clean_architecture_imports():
    mod_path = Path(__file__).resolve().parents[1] / "src" / "swiftletcare_ai" / "audio_monitor.py"
    tree = ast.parse(mod_path.read_text(encoding="utf-8"))
    forbidden = {"fastapi", "starlette", "psycopg", "redis", "aio_pika"}
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported.isdisjoint(forbidden)
