"""Standalone OOP audio anomaly detection module for SwiftletCare (OOP-51).

Clean Architecture boundary: uses only Python standard library (`abc`, `dataclasses`,
`datetime`, `io`, `pathlib`, `typing`, `uuid`, `wave`) and `numpy`. Never imports
FastAPI, Starlette, psycopg, redis, or aio-pika.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
import io
from pathlib import Path
from typing import List, Optional, Tuple
import uuid
import wave

import numpy as np

SPEAKER_SILENCE = "SPEAKER_SILENCE"
ABNORMAL_NOISE = "ABNORMAL_NOISE"


def _utc_now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class AudioAnalysisConfig:
    """Configurable thresholds and framing parameters for swiftlet audio analysis."""

    target_band_hz: Tuple[float, float] = (2500.0, 4500.0)
    window_seconds: float = 0.5
    hop_seconds: float = 0.25
    silence_rms_db_threshold: float = -45.0
    silence_min_consecutive_windows: int = 3
    abnormal_noise_rms_db_threshold: float = -25.0
    abnormal_out_of_band_ratio_threshold: float = 0.65
    abnormal_min_consecutive_windows: int = 2


@dataclass(frozen=True)
class AudioAnomalyEvent:
    """Canonical audio anomaly event produced by BaseAudioAnalyzer."""

    event_id: str
    event_type: str
    camera_id: str
    node_id: Optional[str]
    detected_at: str
    rms_db: float
    dominant_freq_hz: float
    confidence: float
    severity: str


@dataclass(frozen=True)
class AudioAnalysisResult:
    """Summary metrics and detected anomalies for an analyzed audio clip."""

    camera_id: str
    node_id: Optional[str]
    sample_rate: int
    duration_seconds: float
    rms_db: float
    target_band_energy_ratio: float
    dominant_freq_hz: float
    anomalies: List[AudioAnomalyEvent] = field(default_factory=list)


def decode_wav_bytes(wav_bytes: bytes) -> Tuple[np.ndarray, int]:
    """Decode WAV bytes into a normalized mono float64 array in [-1.0, 1.0] and sample rate."""
    if not wav_bytes:
        raise ValueError("Empty WAV payload")

    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            raw_frames = wf.readframes(n_frames)
    except wave.Error as exc:
        raise ValueError(f"Invalid WAV file: {exc}") from exc

    if sample_rate <= 0 or n_channels <= 0:
        raise ValueError("WAV file has invalid sample rate or channel count")
    if n_frames == 0 or not raw_frames:
        raise ValueError("WAV file contains no audio frames")

    if sampwidth == 1:
        # 8-bit PCM WAV is unsigned [0, 255]
        data = (np.frombuffer(raw_frames, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    elif sampwidth == 2:
        data = np.frombuffer(raw_frames, dtype="<i2").astype(np.float64) / 32768.0
    elif sampwidth == 3:
        raw_u8 = np.frombuffer(raw_frames, dtype=np.uint8).reshape(-1, 3)
        signed = (
            raw_u8[:, 0].astype(np.int32)
            | (raw_u8[:, 1].astype(np.int32) << 8)
            | (raw_u8[:, 2].astype(np.int32) << 16)
        )
        signed = np.where(signed & 0x800000, signed - 0x1000000, signed)
        data = signed.astype(np.float64) / 8388608.0
    elif sampwidth == 4:
        data = np.frombuffer(raw_frames, dtype="<i4").astype(np.float64) / 2147483648.0
    else:
        raise ValueError(f"Unsupported WAV sample width: {sampwidth} bytes")

    if n_channels > 1:
        usable = (len(data) // n_channels) * n_channels
        data = data[:usable].reshape(-1, n_channels).mean(axis=1)

    return np.clip(data, -1.0, 1.0), int(sample_rate)


class BaseAudioAnalyzer(ABC):
    """Strategy interface for audio anomaly analysis."""

    @abstractmethod
    def analyze(
        self,
        samples: np.ndarray,
        sample_rate: int,
        camera_id: str,
        node_id: Optional[str] = None,
    ) -> AudioAnalysisResult:
        """Analyze normalized mono audio samples and return metrics + detected anomalies."""
        raise NotImplementedError

    def analyze_wav_bytes(
        self,
        wav_bytes: bytes,
        camera_id: str,
        node_id: Optional[str] = None,
    ) -> AudioAnalysisResult:
        samples, sample_rate = decode_wav_bytes(wav_bytes)
        return self.analyze(samples, sample_rate, camera_id=camera_id, node_id=node_id)

    def analyze_wav_file(
        self,
        wav_path: str | Path,
        camera_id: str,
        node_id: Optional[str] = None,
    ) -> AudioAnalysisResult:
        data = Path(wav_path).read_bytes()
        return self.analyze_wav_bytes(data, camera_id=camera_id, node_id=node_id)


class SwiftletAudioAnalyzer(BaseAudioAnalyzer):
    """Audio analyzer tuned for swiftlet lure-speaker silence and out-of-band noise."""

    def __init__(self, config: Optional[AudioAnalysisConfig] = None) -> None:
        self.config = config or AudioAnalysisConfig()

    @staticmethod
    def _preprocess(samples: np.ndarray) -> np.ndarray:
        arr = np.asarray(samples, dtype=np.float64)
        if arr.ndim > 1:
            arr = arr.mean(axis=1)
        if arr.size == 0:
            raise ValueError("Audio samples must not be empty")
        arr = np.nan_to_num(arr, nan=0.0, posinf=1.0, neginf=-1.0)
        peak = float(np.max(np.abs(arr)))
        if peak > 1.0:
            arr = arr / peak
        # Remove DC offset so silence/noise energy is measured accurately
        return arr - float(np.mean(arr))

    def _window_frames(self, signal: np.ndarray, sample_rate: int) -> List[np.ndarray]:
        win_len = max(1, int(round(self.config.window_seconds * sample_rate)))
        hop_len = max(1, int(round(self.config.hop_seconds * sample_rate)))
        if len(signal) <= win_len:
            return [signal]
        frames: List[np.ndarray] = []
        for start in range(0, len(signal) - win_len + 1, hop_len):
            frames.append(signal[start : start + win_len])
        if not frames:
            frames.append(signal)
        return frames

    def _compute_frame_metrics(self, frame: np.ndarray, sample_rate: int) -> Tuple[float, float, float]:
        rms = float(np.sqrt(np.mean(np.square(frame))))
        rms_db = float(20.0 * np.log10(max(rms, 1e-10)))

        if len(frame) < 2:
            return rms_db, 0.0, 0.0

        windowed = frame * np.hanning(len(frame))
        spectrum = np.fft.rfft(windowed)
        power = np.square(np.abs(spectrum))
        freqs = np.fft.rfftfreq(len(frame), d=1.0 / float(sample_rate))

        total_power = float(np.sum(power))
        if total_power <= 1e-20:
            return rms_db, 0.0, 0.0

        low_hz, high_hz = self.config.target_band_hz
        band_mask = (freqs >= low_hz) & (freqs <= high_hz)
        band_power = float(np.sum(power[band_mask]))
        band_ratio = band_power / total_power

        # Ignore DC bin (index 0) when finding dominant frequency
        if len(power) > 1:
            dom_idx = int(np.argmax(power[1:])) + 1
            dominant_freq = float(freqs[dom_idx])
        else:
            dominant_freq = 0.0

        return rms_db, band_ratio, dominant_freq

    def analyze(
        self,
        samples: np.ndarray,
        sample_rate: int,
        camera_id: str,
        node_id: Optional[str] = None,
    ) -> AudioAnalysisResult:
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        cam_id = (camera_id or "").strip()
        if not cam_id:
            raise ValueError("camera_id must not be empty")
        norm_node_id = (node_id or "").strip() or None

        signal = self._preprocess(samples)
        duration_seconds = round(float(len(signal)) / float(sample_rate), 4)
        overall_rms_db, overall_band_ratio, overall_dom_freq = self._compute_frame_metrics(
            signal, sample_rate
        )

        frames = self._window_frames(signal, sample_rate)
        silence_run: List[Tuple[float, float]] = []
        noise_run: List[Tuple[float, float, float]] = []
        silence_detected = False
        noise_detected = False
        anomalies: List[AudioAnomalyEvent] = []

        for frame in frames:
            rms_db, band_ratio, dom_freq = self._compute_frame_metrics(frame, sample_rate)
            out_of_band_ratio = 1.0 - band_ratio

            if rms_db < self.config.silence_rms_db_threshold:
                silence_run.append((rms_db, dom_freq))
                if (
                    not silence_detected
                    and len(silence_run) >= self.config.silence_min_consecutive_windows
                ):
                    silence_detected = True
                    avg_rms_db = float(np.mean([x[0] for x in silence_run]))
                    margin = max(0.0, self.config.silence_rms_db_threshold - avg_rms_db)
                    conf = round(min(0.99, max(0.55, 0.65 + margin / 40.0)), 4)
                    severity = "HIGH" if avg_rms_db < (self.config.silence_rms_db_threshold - 15.0) else "MEDIUM"
                    anomalies.append(
                        AudioAnomalyEvent(
                            event_id=f"aud-{uuid.uuid4().hex[:12]}",
                            event_type=SPEAKER_SILENCE,
                            camera_id=cam_id,
                            node_id=norm_node_id,
                            detected_at=_utc_now_iso8601(),
                            rms_db=round(avg_rms_db, 2),
                            dominant_freq_hz=round(float(np.mean([x[1] for x in silence_run])), 2),
                            confidence=conf,
                            severity=severity,
                        )
                    )
            else:
                silence_run.clear()

            if (
                rms_db >= self.config.abnormal_noise_rms_db_threshold
                and out_of_band_ratio >= self.config.abnormal_out_of_band_ratio_threshold
            ):
                noise_run.append((rms_db, dom_freq, out_of_band_ratio))
                if (
                    not noise_detected
                    and len(noise_run) >= self.config.abnormal_min_consecutive_windows
                ):
                    noise_detected = True
                    avg_rms_db = float(np.mean([x[0] for x in noise_run]))
                    avg_oob = float(np.mean([x[2] for x in noise_run]))
                    conf = round(min(0.99, max(0.55, 0.5 + avg_oob * 0.48)), 4)
                    severity = "HIGH" if avg_rms_db >= -12.0 else "MEDIUM"
                    anomalies.append(
                        AudioAnomalyEvent(
                            event_id=f"aud-{uuid.uuid4().hex[:12]}",
                            event_type=ABNORMAL_NOISE,
                            camera_id=cam_id,
                            node_id=norm_node_id,
                            detected_at=_utc_now_iso8601(),
                            rms_db=round(avg_rms_db, 2),
                            dominant_freq_hz=round(float(np.mean([x[1] for x in noise_run])), 2),
                            confidence=conf,
                            severity=severity,
                        )
                    )
            else:
                noise_run.clear()

        return AudioAnalysisResult(
            camera_id=cam_id,
            node_id=norm_node_id,
            sample_rate=int(sample_rate),
            duration_seconds=duration_seconds,
            rms_db=round(overall_rms_db, 2),
            target_band_energy_ratio=round(overall_band_ratio, 4),
            dominant_freq_hz=round(overall_dom_freq, 2),
            anomalies=anomalies,
        )


__all__ = [
    "ABNORMAL_NOISE",
    "AudioAnalysisConfig",
    "AudioAnalysisResult",
    "AudioAnomalyEvent",
    "BaseAudioAnalyzer",
    "SPEAKER_SILENCE",
    "SwiftletAudioAnalyzer",
    "decode_wav_bytes",
]
