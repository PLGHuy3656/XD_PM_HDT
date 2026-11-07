"""Evaluation script for swiftlet counting accuracy (AI-NFR-004).

Evaluates CameraPipeline (YoloDetector + ByteTrackTracker) against ground truth counts.
Generates an ASCII comparison table and outputs results to eval/outputs/counting_eval.json.
NO FastAPI or WebSocket dependencies.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path
from typing import Optional

if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

EVAL_DIR = Path(__file__).resolve().parent
SERVICE_DIR = EVAL_DIR.parent
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from app.config import AI_PIPELINE_DIR, RuntimeCameraConfig
from app.runtime.camera_pipeline import CameraPipeline
from app.runtime.sink import BaseRuntimeSink
from app.schemas.canonical import CountUpdate
from swiftletcare_ai.detector import YoloDetector
from swiftletcare_ai.predator import PredatorMonitor
from swiftletcare_ai.tracker import build_tracker


class CountingCollectorSink(BaseRuntimeSink):
    """Sink that collects latest CountUpdate."""

    def __init__(self) -> None:
        self.latest_count: Optional[CountUpdate] = None
        self.history: list[CountUpdate] = []

    def on_count(self, update: CountUpdate) -> None:
        self.latest_count = update
        self.history.append(update)


def evaluate_counting(
    video_path: Path,
    weights_path: Path,
    gt_entry: int,
    gt_exit: int,
    max_frames: int = 150,
    line: tuple[tuple[float, float], tuple[float, float]] = ((0.10, 0.55), (0.90, 0.55)),
    inside_side: str = "positive",
    output_json: Optional[Path] = None,
) -> dict:
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    if not weights_path.exists():
        raise FileNotFoundError(f"Model weights not found: {weights_path}")

    print(f"[EVAL-COUNTING] Initializing YoloDetector with {weights_path}...")
    detector = YoloDetector(
        model_path=str(weights_path),
        imgsz=640,
        device="auto",
        min_conf=0.15,
        iou=0.5,
    )
    tracker = build_tracker({"type": "bytetrack"})
    predator_monitor = PredatorMonitor(classes=())
    sink = CountingCollectorSink()

    cam_cfg = RuntimeCameraConfig(
        camera_id="EVAL-CAM",
        source=str(video_path),
        source_type="video",
        line=line,
        inside_side=inside_side,
    )

    pipeline = CameraPipeline(
        camera_config=cam_cfg,
        detector=detector,
        tracker=tracker,
        predator_monitor=predator_monitor,
        sink=sink,
        min_track_hits=2,
        count_report_interval_s=1.0,
    )

    print(f"[EVAL-COUNTING] Running counting on {video_path.name} (max_frames={max_frames or 'all'})...")
    t0 = time.perf_counter()
    status = pipeline.run(max_frames=max_frames)
    elapsed_s = time.perf_counter() - t0

    pred_entry = 0
    pred_exit = 0
    if sink.latest_count is not None:
        pred_entry = sink.latest_count.entryCount
        pred_exit = sink.latest_count.exitCount

    entry_err = abs(pred_entry - gt_entry)
    exit_err = abs(pred_exit - gt_exit)
    mae = (entry_err + exit_err) / 2.0

    entry_acc = max(0.0, 1.0 - (entry_err / gt_entry)) * 100.0 if gt_entry > 0 else 100.0
    exit_acc = max(0.0, 1.0 - (exit_err / gt_exit)) * 100.0 if gt_exit > 0 else 100.0
    overall_acc = (entry_acc + exit_acc) / 2.0

    fps = status.processedFrames / elapsed_s if elapsed_s > 0 else 0.0

    print("\n" + "=" * 65)
    print("         SWIFTLET COUNTING EVALUATION REPORT (AI-NFR-004)")
    print("=" * 65)
    print(f"{'Metric':<18} | {'Predicted':<10} | {'Ground Truth':<12} | {'Abs Error':<10} | {'Accuracy %':<10}")
    print("-" * 65)
    print(f"{'Entry (IN)':<18} | {pred_entry:<10} | {gt_entry:<12} | {entry_err:<10} | {entry_acc:.1f}%")
    print(f"{'Exit (OUT)':<18} | {pred_exit:<10} | {gt_exit:<12} | {exit_err:<10} | {exit_acc:.1f}%")
    print("-" * 65)
    print(f"{'Overall (MAE)':<18} | {'-':<10} | {'-':<12} | {mae:<10.1f} | {overall_acc:.1f}%")
    print(f"\nProcessed: {status.processedFrames} frames in {elapsed_s:.2f}s ({fps:.1f} FPS)")
    print("=" * 65 + "\n")

    results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "video": str(video_path),
        "weights": str(weights_path),
        "processed_frames": status.processedFrames,
        "elapsed_seconds": round(elapsed_s, 2),
        "fps": round(fps, 2),
        "predicted": {"entry": pred_entry, "exit": pred_exit, "net": pred_entry - pred_exit},
        "ground_truth": {"entry": gt_entry, "exit": gt_exit, "net": gt_entry - gt_exit},
        "absolute_error": {"entry": entry_err, "exit": exit_err, "mae": round(mae, 2)},
        "accuracy_pct": {
            "entry": round(entry_acc, 2),
            "exit": round(exit_acc, 2),
            "overall": round(overall_acc, 2),
        },
    }

    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[EVAL-COUNTING] Saved results to {output_json}")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate swiftlet counting accuracy")
    parser.add_argument(
        "--video",
        default=str(AI_PIPELINE_DIR / "data" / "samples" / "38s.mp4"),
        help="Path to evaluation video file",
    )
    parser.add_argument(
        "--weights",
        default=str(AI_PIPELINE_DIR / "models" / "best.pt"),
        help="Path to YOLO weights",
    )
    parser.add_argument(
        "--gt-entry",
        type=int,
        default=12,
        help="Ground truth entry count",
    )
    parser.add_argument(
        "--gt-exit",
        type=int,
        default=8,
        help="Ground truth exit count",
    )
    parser.add_argument(
        "--gt",
        default=None,
        help="Optional JSON file with ground truth: {\"entry\": int, \"exit\": int}",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=120,
        help="Max frames to process (0 = all)",
    )
    parser.add_argument(
        "--out",
        default=str(EVAL_DIR / "outputs" / "counting_eval.json"),
        help="Output JSON result file path",
    )
    args = parser.parse_args()

    gt_entry = args.gt_entry
    gt_exit = args.gt_exit
    if args.gt:
        gt_data = json.loads(Path(args.gt).read_text(encoding="utf-8"))
        gt_entry = gt_data.get("entry", gt_entry)
        gt_exit = gt_data.get("exit", gt_exit)

    evaluate_counting(
        video_path=Path(args.video),
        weights_path=Path(args.weights),
        gt_entry=gt_entry,
        gt_exit=gt_exit,
        max_frames=args.max_frames,
        output_json=Path(args.out),
    )


if __name__ == "__main__":
    main()
