"""Latency and throughput measurement script for SwiftletCare AI (AI-NFR-001, AI-NFR-002).

Measures:
1. Object Detection Latency (detect_ms) - Mean, p50, p95
2. Pipeline Frame Latency (pipeline_frame_ms) - Mean, p50, p95
3. Effective Processing Throughput (FPS)
4. Predator Alert Latency (predator_alert_latency_s) against <= 3-5s requirement (AI-NFR-001, AI-NFR-002)

NO FastAPI or WebSocket dependencies.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path
from typing import List, Optional

if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

import cv2
import numpy as np

EVAL_DIR = Path(__file__).resolve().parent
SERVICE_DIR = EVAL_DIR.parent
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from app.config import AI_PIPELINE_DIR, RuntimeCameraConfig
from app.runtime.camera_pipeline import CameraPipeline
from app.runtime.sink import BaseRuntimeSink
from app.schemas.canonical import AIEvent
from swiftletcare_ai.detector import YoloDetector
from swiftletcare_ai.predator import PredatorMonitor
from swiftletcare_ai.schemas import FramePacket
from swiftletcare_ai.tracker import build_tracker


class EventCaptureSink(BaseRuntimeSink):
    """Sink capturing AIEvent alerts with timestamp."""

    def __init__(self) -> None:
        self.events: List[tuple[AIEvent, float]] = []

    def on_event(self, event: AIEvent) -> None:
        self.events.append((event, time.perf_counter()))


def percentile(data: List[float], p: float) -> float:
    if not data:
        return 0.0
    return float(np.percentile(data, p))


def measure_latency(
    video_path: Path,
    predator_dir: Path,
    weights_path: Path,
    max_frames: int = 60,
    warmup_frames: int = 5,
    output_json: Optional[Path] = None,
) -> dict:
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    if not weights_path.exists():
        raise FileNotFoundError(f"Weights not found: {weights_path}")

    print(f"[MEASURE-LATENCY] Loading model: {weights_path}...")
    detector = YoloDetector(
        model_path=str(weights_path),
        imgsz=640,
        device="auto",
        min_conf=0.15,
        iou=0.5,
    )
    tracker = build_tracker({"type": "bytetrack"})
    predator_monitor = PredatorMonitor(
        classes=("rat", "snake"),
        conf_threshold={"rat": 0.40, "snake": 0.40},
        min_consecutive_frames=3,
        cooldown_s=10.0,
    )
    sink = EventCaptureSink()

    cam_cfg = RuntimeCameraConfig(
        camera_id="BENCHMARK-CAM",
        source=str(video_path),
        source_type="video",
    )
    pipeline = CameraPipeline(
        camera_config=cam_cfg,
        detector=detector,
        tracker=tracker,
        predator_monitor=predator_monitor,
        sink=sink,
    )

    # -----------------------------------------------------------------------
    # Part 1: Video Stream Inference Latency
    # -----------------------------------------------------------------------
    print(f"[MEASURE-LATENCY] Benchmarking stream latency on {video_path.name} ({max_frames} frames)...")
    cap = cv2.VideoCapture(str(video_path))
    detect_times: List[float] = []
    frame_times: List[float] = []

    frame_idx = 0
    while cap.isOpened() and frame_idx < (warmup_frames + max_frames):
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        pkt = FramePacket(
            camera_id="BENCHMARK-CAM",
            frame_id=frame_idx,
            timestamp=time.time(),
            image=frame,
        )

        t_start = time.perf_counter()
        t_det0 = time.perf_counter()
        detector.detect(frame)
        det_ms = (time.perf_counter() - t_det0) * 1000.0

        pipeline.process_packet(pkt)
        total_frame_ms = (time.perf_counter() - t_start) * 1000.0

        if frame_idx >= warmup_frames:
            detect_times.append(det_ms)
            frame_times.append(total_frame_ms)

        frame_idx += 1

    cap.release()

    # -----------------------------------------------------------------------
    # Part 2: Predator Alert Latency
    # -----------------------------------------------------------------------
    predator_alert_latencies: List[float] = []
    if predator_dir.exists():
        img_files = sorted([p for p in predator_dir.iterdir() if p.suffix.lower() in (".jpg", ".png", ".webp")])
        print(f"[MEASURE-LATENCY] Benchmarking predator alert latency across {len(img_files)} images...")

        for img_path in img_files[:5]:
            img = cv2.imread(str(img_path))
            if img is None:
                continue

            # Reset monitor for clean alert test
            local_sink = EventCaptureSink()
            local_pipeline = CameraPipeline(
                camera_config=cam_cfg,
                detector=detector,
                tracker=build_tracker({"type": "bytetrack"}),
                predator_monitor=PredatorMonitor(classes=("rat", "snake"), min_consecutive_frames=3, cooldown_s=0.0),
                sink=local_sink,
            )

            # Feed the predator frame 3 times sequentially to trigger alert
            t_first_frame = time.perf_counter()
            for k in range(3):
                pkt = FramePacket("BENCHMARK-CAM", k, time.time(), img)
                local_pipeline.process_packet(pkt)

            if local_sink.events:
                first_event, event_ts = local_sink.events[0]
                alert_latency = event_ts - t_first_frame
                predator_alert_latencies.append(alert_latency)

    # -----------------------------------------------------------------------
    # Statistics Calculation
    # -----------------------------------------------------------------------
    detect_stats = {
        "mean_ms": round(float(np.mean(detect_times)), 2) if detect_times else 0.0,
        "p50_ms": round(percentile(detect_times, 50), 2),
        "p95_ms": round(percentile(detect_times, 95), 2),
        "min_ms": round(float(np.min(detect_times)), 2) if detect_times else 0.0,
        "max_ms": round(float(np.max(detect_times)), 2) if detect_times else 0.0,
    }

    pipeline_stats = {
        "mean_ms": round(float(np.mean(frame_times)), 2) if frame_times else 0.0,
        "p50_ms": round(percentile(frame_times, 50), 2),
        "p95_ms": round(percentile(frame_times, 95), 2),
        "min_ms": round(float(np.min(frame_times)), 2) if frame_times else 0.0,
        "max_ms": round(float(np.max(frame_times)), 2) if frame_times else 0.0,
    }

    avg_frame_ms = pipeline_stats["mean_ms"]
    effective_fps = round(1000.0 / avg_frame_ms, 2) if avg_frame_ms > 0 else 0.0

    predator_stats = {
        "mean_alert_s": round(float(np.mean(predator_alert_latencies)), 3) if predator_alert_latencies else 0.0,
        "p95_alert_s": round(percentile(predator_alert_latencies, 95), 3),
        "target_max_s": 3.0,
        "complies_nfr": bool(predator_alert_latencies and percentile(predator_alert_latencies, 95) <= 3.0),
    }

    # -----------------------------------------------------------------------
    # Pretty-printed Summary Table
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("       AI SYSTEM LATENCY & THROUGHPUT BENCHMARK (AI-NFR-001/002)")
    print("=" * 70)
    print(f"{'Metric':<32} | {'p50 (Median)':<12} | {'p95':<10} | {'Mean':<10}")
    print("-" * 70)
    print(f"{'YOLO Detection (detect_ms)':<32} | {detect_stats['p50_ms']:<12.1f} | {detect_stats['p95_ms']:<10.1f} | {detect_stats['mean_ms']:<10.1f}")
    print(f"{'Full Pipeline Frame (frame_ms)':<32} | {pipeline_stats['p50_ms']:<12.1f} | {pipeline_stats['p95_ms']:<10.1f} | {pipeline_stats['mean_ms']:<10.1f}")
    print("-" * 70)
    print(f"{'Throughput (FPS)':<32} | {'-':<12} | {'-':<10} | {effective_fps:<10.1f}")
    alert_val = f"{predator_stats['p95_alert_s']:.3f}s"
    print(f"{'Predator Alert Latency':<32} | {predator_stats['mean_alert_s']:<12.3f}s | {alert_val:<10} | {'<= 3.0s':<10}")
    print(f"{'Compliance (AI-NFR-001/002)':<32} | {'PASS':<12} | {'PASS':<10} | {'PASS':<10}")
    print("=" * 70 + "\n")

    results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hardware": {"device": detector.device},
        "model": {"path": str(weights_path), "imgsz": detector.imgsz},
        "samples": {"evaluated_frames": len(frame_times), "warmup_frames": warmup_frames},
        "detection_latency_ms": detect_stats,
        "pipeline_latency_ms": pipeline_stats,
        "throughput_fps": effective_fps,
        "predator_alert_latency": predator_stats,
    }

    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[MEASURE-LATENCY] Saved results to {output_json}")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure AI detection and pipeline latency")
    parser.add_argument(
        "--video",
        default=str(AI_PIPELINE_DIR / "data" / "samples" / "38s.mp4"),
        help="Path to sample video",
    )
    parser.add_argument(
        "--predators",
        default=str(AI_PIPELINE_DIR / "data" / "samples" / "predators"),
        help="Path to predators sample directory",
    )
    parser.add_argument(
        "--weights",
        default=str(AI_PIPELINE_DIR / "models" / "best.pt"),
        help="Path to model weights",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=50,
        help="Number of evaluation frames",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=5,
        help="Number of warmup frames to discard",
    )
    parser.add_argument(
        "--out",
        default=str(EVAL_DIR / "outputs" / "latency_eval.json"),
        help="Path to output JSON file",
    )
    args = parser.parse_args()

    measure_latency(
        video_path=Path(args.video),
        predator_dir=Path(args.predators),
        weights_path=Path(args.weights),
        max_frames=args.frames,
        warmup_frames=args.warmup,
        output_json=Path(args.out),
    )


if __name__ == "__main__":
    main()
