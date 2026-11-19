"""Integrated E2E verification script for SwiftletCare AI Pipeline (Jira OOP-116).

Verifies the live data flow across:
  AI Service (/start, /analyze, /audio/analyze, /counts, /events, /cameras?farm_id=...)
  -> ai_db persistence
  -> (optional full Docker stack) notification-service & analytics-service.

Outputs both a human-readable console summary table and a JSON report.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional
import wave

import httpx
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SAMPLE_VIDEO = REPO_ROOT / "data" / "samples" / "10s.mp4"
DEFAULT_PREDATOR_DIR = REPO_ROOT / "data" / "samples" / "predators"


@dataclass
class CheckResult:
    step: str
    status: str  # PASS | FAIL | SKIP
    detail: str
    elapsed_ms: float = 0.0
    data: Optional[Dict[str, Any]] = None


def _build_synthetic_silence_wav(duration_sec: float = 1.2, sample_rate: int = 16000) -> bytes:
    n_samples = int(duration_sec * sample_rate)
    pcm = np.zeros(n_samples, dtype=np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def _find_first_predator_image(predator_dir: Path) -> Optional[Path]:
    if not predator_dir.exists() or not predator_dir.is_dir():
        return None
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
        matches = sorted(predator_dir.glob(ext))
        if matches:
            return matches[0]
    return None


def _run_step(name: str, fn) -> CheckResult:
    t0 = time.perf_counter()
    try:
        status, detail, data = fn()
        return CheckResult(
            step=name,
            status=status,
            detail=detail,
            elapsed_ms=round((time.perf_counter() - t0) * 1000.0, 2),
            data=data,
        )
    except Exception as exc:
        return CheckResult(
            step=name,
            status="FAIL",
            detail=f"{exc.__class__.__name__}: {exc}",
            elapsed_ms=round((time.perf_counter() - t0) * 1000.0, 2),
        )


def run_verification(args: argparse.Namespace) -> Dict[str, Any]:
    results: List[CheckResult] = []
    headers: Dict[str, str] = {"Accept": "application/json"}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"

    video_path = Path(args.sample_video)
    predator_dir = Path(args.predator_dir)
    predator_img = _find_first_predator_image(predator_dir)

    # 1. Sample assets check
    def check_samples():
        missing: List[str] = []
        if not video_path.exists():
            missing.append(str(video_path))
        if predator_img is None:
            missing.append(f"{predator_dir} (no .jpg/.png/.webp found)")
        if missing:
            return (
                "FAIL",
                f"Missing required sample assets: {', '.join(missing)}",
                {"video_exists": video_path.exists(), "predator_image": None},
            )
        return (
            "PASS",
            f"Found video ({video_path.name}) and predator image ({predator_img.name})",
            {"video_path": str(video_path), "predator_image": str(predator_img)},
        )

    results.append(_run_step("sample_assets", check_samples))

    with httpx.Client(timeout=args.timeout, headers=headers) as client:
        # 2. Health check
        def check_health():
            resp = client.get(f"{args.ai_url.rstrip('/')}/health")
            if resp.status_code != 200:
                return ("FAIL", f"HTTP {resp.status_code}: {resp.text[:200]}", None)
            return ("PASS", "AI Service /health returned 200", resp.json())

        results.append(_run_step("ai_health", check_health))

        # 3. Start camera with real farmId / zoneId
        def check_start_camera():
            payload: Dict[str, Any] = {
                "farmId": args.farm_id,
                "zoneId": args.zone_id,
                "maxFrames": args.max_frames,
            }
            if video_path.exists():
                payload["source"] = str(video_path)
                payload["sourceType"] = "video"
            resp = client.post(
                f"{args.ai_url.rstrip('/')}/api/v1/ai/cameras/{args.camera_id}/start",
                json=payload,
            )
            if resp.status_code != 200:
                return ("FAIL", f"HTTP {resp.status_code}: {resp.text[:200]}", None)
            body = resp.json()
            return (
                "PASS",
                f"Started {args.camera_id} (status={body.get('status')}, farmId={body.get('farmId')})",
                body,
            )

        results.append(_run_step("camera_start", check_start_camera))

        if args.wait_seconds > 0:
            time.sleep(args.wait_seconds)

        # 4. POST /api/v1/ai/analyze with predator sample
        def check_analyze_image():
            if predator_img is None:
                return ("SKIP", "Skipped: predator sample image missing", None)
            with predator_img.open("rb") as fh:
                resp = client.post(
                    f"{args.ai_url.rstrip('/')}/api/v1/ai/analyze",
                    params={"cameraId": args.camera_id},
                    files={"file": (predator_img.name, fh, "image/jpeg")},
                )
            if resp.status_code != 200:
                return ("FAIL", f"HTTP {resp.status_code}: {resp.text[:200]}", None)
            body = resp.json()
            dets = body.get("detections", [])
            return ("PASS", f"Analyzed {predator_img.name} ({len(dets)} detections)", body)

        results.append(_run_step("image_analyze", check_analyze_image))

        # 5. POST /api/v1/ai/audio/analyze
        def check_analyze_audio():
            if args.audio_wav and Path(args.audio_wav).exists():
                wav_bytes = Path(args.audio_wav).read_bytes()
                fname = Path(args.audio_wav).name
            else:
                wav_bytes = _build_synthetic_silence_wav()
                fname = "synthetic_silence.wav"
            resp = client.post(
                f"{args.ai_url.rstrip('/')}/api/v1/ai/audio/analyze",
                params={"cameraId": args.camera_id},
                files={"file": (fname, wav_bytes, "audio/wav")},
            )
            if resp.status_code != 200:
                return ("FAIL", f"HTTP {resp.status_code}: {resp.text[:200]}", None)
            body = resp.json()
            anomalies = body.get("anomalies", [])
            return (
                "PASS",
                f"Audio analyzed ({fname}, anomalies={len(anomalies)})",
                body,
            )

        results.append(_run_step("audio_analyze", check_analyze_audio))

        # 6. Verify counts & events persisted in ai_db
        def check_counts():
            resp = client.get(
                f"{args.ai_url.rstrip('/')}/api/v1/ai/cameras/{args.camera_id}/counts",
                params={"limit": 10},
            )
            if resp.status_code != 200:
                return ("FAIL", f"HTTP {resp.status_code}: {resp.text[:200]}", None)
            items = resp.json()
            return ("PASS", f"Retrieved {len(items)} count records", {"count": len(items)})

        results.append(_run_step("ai_db_counts", check_counts))

        def check_events():
            resp = client.get(
                f"{args.ai_url.rstrip('/')}/api/v1/ai/events",
                params={"cameraId": args.camera_id, "limit": 20},
            )
            if resp.status_code != 200:
                return ("FAIL", f"HTTP {resp.status_code}: {resp.text[:200]}", None)
            items = resp.json()
            return ("PASS", f"Retrieved {len(items)} AI events", {"count": len(items)})

        results.append(_run_step("ai_db_events", check_events))

        # 7. Verify GET /api/v1/ai/cameras?farm_id=...
        def check_farm_filter():
            resp = client.get(
                f"{args.ai_url.rstrip('/')}/api/v1/ai/cameras",
                params={"farm_id": args.farm_id},
            )
            if resp.status_code != 200:
                return ("FAIL", f"HTTP {resp.status_code}: {resp.text[:200]}", None)
            cams = resp.json()
            mismatched = [c.get("cameraId") for c in cams if c.get("farmId") != args.farm_id]
            if mismatched:
                return ("FAIL", f"Found cameras with mismatched farmId: {mismatched}", None)
            return (
                "PASS",
                f"Filtered {len(cams)} cameras for farm_id={args.farm_id}",
                {"camera_ids": [c.get("cameraId") for c in cams]},
            )

        results.append(_run_step("cameras_farm_filter", check_farm_filter))

        # 8. Optional cross-service Docker stack checks
        if args.check_stack:
            def check_notifications():
                resp = client.get(
                    f"{args.notification_url.rstrip('/')}/api/v1/alerts",
                    params={"farmId": args.farm_id},
                )
                if resp.status_code != 200:
                    return ("FAIL", f"HTTP {resp.status_code}: {resp.text[:200]}", None)
                body = resp.json()
                return ("PASS", "notification-service alerts reachable", {"alerts": body})

            def check_analytics():
                resp = client.get(
                    f"{args.analytics_url.rstrip('/')}/api/v1/analytics/bird-performance",
                    params={"farmId": args.farm_id},
                )
                if resp.status_code != 200:
                    return ("FAIL", f"HTTP {resp.status_code}: {resp.text[:200]}", None)
                body = resp.json()
                return ("PASS", "analytics-service birdPerformance reachable", {"analytics": body})

            results.append(_run_step("notification_alerts", check_notifications))
            results.append(_run_step("analytics_bird_performance", check_analytics))
        else:
            results.append(CheckResult("notification_alerts", "SKIP", "Use --check-stack to enable"))
            results.append(CheckResult("analytics_bird_performance", "SKIP", "Use --check-stack to enable"))

    failed = sum(1 for r in results if r.status == "FAIL")
    passed = sum(1 for r in results if r.status == "PASS")
    skipped = sum(1 for r in results if r.status == "SKIP")
    overall = "PASS" if failed == 0 else "FAIL"

    return {
        "ticket": "OOP-116",
        "executed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "overall_status": overall,
        "summary": {"passed": passed, "failed": failed, "skipped": skipped},
        "results": [asdict(r) for r in results],
    }


def _print_table(report: Dict[str, Any]) -> None:
    print("\n" + "=" * 86)
    print(f"SwiftletCare Integrated E2E Verification ({report['ticket']}) — Overall: {report['overall_status']}")
    print("=" * 86)
    print(f"{'STEP':<28} {'STATUS':<8} {'TIME(ms)':<10} DETAIL")
    print("-" * 86)
    for row in report["results"]:
        print(f"{row['step']:<28} {row['status']:<8} {row['elapsed_ms']:<10.2f} {row['detail']}")
    print("-" * 86)
    s = report["summary"]
    print(f"Summary: passed={s['passed']}, failed={s['failed']}, skipped={s['skipped']}\n")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SwiftletCare Integrated E2E Verification (OOP-116)")
    parser.add_argument("--ai-url", default="http://127.0.0.1:8003")
    parser.add_argument("--notification-url", default="http://127.0.0.1:8004")
    parser.add_argument("--analytics-url", default="http://127.0.0.1:8005")
    parser.add_argument("--camera-id", default="CAM-01")
    parser.add_argument("--farm-id", default="FARM-01")
    parser.add_argument("--zone-id", default="ZONE-01")
    parser.add_argument("--max-frames", type=int, default=30)
    parser.add_argument("--wait-seconds", type=float, default=1.5)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--token", default="")
    parser.add_argument("--sample-video", default=str(DEFAULT_SAMPLE_VIDEO))
    parser.add_argument("--predator-dir", default=str(DEFAULT_PREDATOR_DIR))
    parser.add_argument("--audio-wav", default="")
    parser.add_argument("--check-stack", action="store_true")
    parser.add_argument("--json-out", default="")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    report = run_verification(args)
    _print_table(report)
    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    else:
        print(json.dumps(report, indent=2))
    return 0 if report["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
