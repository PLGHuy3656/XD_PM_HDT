"""Manual E2E Runtime Feed Runner for SwiftletCare AI Service V1 (CP5.4 Terminal 3).

Triggers and monitors a real-model AI runtime camera pipeline (`YoloDetector` with
`ai-pipeline/models/best.pt` + `ByteTrackTracker` + `LineCounter` + `PredatorMonitor`)
inside the running AI Service (`http://127.0.0.1:8003`), feeding:
  - InMemoryAIRuntimeStateStore (REST API V1)
  - AIWebSocketManager (`/ws/ai` realtime broadcast)

Usage:
    python services/ai-service/demo/runtime_runner.py \
        --camera CAM-01 \
        --source ai-pipeline/data/samples/fixture_swiftlet_positive.avi \
        --service-key-env AI_INTERNAL_SERVICE_KEY \
        --token-env CP13_TOKEN_OWNER_A \
        --repeat 1 --fps 5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import httpx


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run AI Runtime Pipeline on SwiftletCare AI Service (Terminal 3)"
    )
    parser.add_argument(
        "--service-url",
        default="http://127.0.0.1:8003",
        help="Base URL of running AI Service (default: http://127.0.0.1:8003)",
    )
    parser.add_argument(
        "--camera",
        default="CAM-01",
        help="Camera ID or UUID (default: CAM-01)",
    )
    parser.add_argument(
        "--source",
        default="ai-pipeline/data/samples/fixture_swiftlet_positive.avi",
        help="Path to sample video or image in allowlist (default: ai-pipeline/data/samples/fixture_swiftlet_positive.avi)",
    )
    parser.add_argument(
        "--source-type",
        default="auto",
        choices=("auto", "video", "image_dir", "webcam"),
        help="Source type (default: auto)",
    )
    parser.add_argument(
        "--model",
        default="ai-pipeline/models/best.pt",
        help="Path to TV2 YOLO model weights (default: ai-pipeline/models/best.pt)",
    )
    parser.add_argument(
        "--service-key",
        default=None,
        help="Internal service key (if omitted, reads from AI_INTERNAL_SERVICE_KEY env)",
    )
    parser.add_argument(
        "--service-key-env",
        default="AI_INTERNAL_SERVICE_KEY",
        help="Environment variable name for internal service key (default: AI_INTERNAL_SERVICE_KEY)",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Caller JWT bearer token for camera registry verification (optional, prefer --token-env)",
    )
    parser.add_argument(
        "--token-env",
        default=None,
        help="Environment variable containing caller bearer token (e.g. CP13_TOKEN_OWNER_A)",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of times to repeat image/folder frames (default: 1)",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=2.0,
        help="Target playback FPS for observable realtime streaming (default: 2.0)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Optional maximum frames to process (0 = all frames)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    model_path = Path(args.model)
    if not model_path.exists():
        print(f"[ERROR] Model file not found: {model_path.resolve()}", file=sys.stderr)
        return 2

    if args.source.lower().startswith(("rtsp://", "http://", "https://", "udp://", "file://")):
        print(
            f"[ERROR] Network and URI stream sources ({args.source}) are blocked by AI runtime security hardening. "
            "Please use local media files located under ai-pipeline/data/samples/.",
            file=sys.stderr,
        )
        return 2

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"[ERROR] Media source not found: {source_path.resolve()}", file=sys.stderr)
        return 2

    # Resolve service key
    service_key = (args.service_key or os.getenv(args.service_key_env, "")).strip()
    if not service_key:
        print(
            f"[WARNING] No service key provided via --service-key or ${args.service_key_env}. "
            "If AI Service has runtime hardening enabled, request will fail with 401.",
            file=sys.stderr,
        )

    # Resolve token
    token = (args.token or "").strip()
    if not token and args.token_env:
        token = os.getenv(args.token_env, "").strip()
    if not token:
        # Check common fallback environment variables
        for fallback_env in ("AUTH_TOKEN", "CP13_TOKEN_OWNER_A", "CP13_TOKEN_ADMIN"):
            val = os.getenv(fallback_env, "").strip()
            if val:
                token = val
                break

    if not token:
        print(
            "[WARNING] No caller bearer token provided via --token, --token-env, or $AUTH_TOKEN. "
            "If AI Service has camera registry verification enabled, request will fail with 401.",
            file=sys.stderr,
        )

    headers = {}
    if service_key:
        headers["X-Internal-Service-Key"] = service_key
    if token:
        headers["Authorization"] = f"Bearer {token}"

    print("=" * 78)
    print("SwiftletCare AI Service V1 — Real-Model Runtime Runner (Terminal 3)")
    print(f"Service URL : {args.service_url}")
    print(f"Camera ID   : {args.camera}")
    print(f"Model Path  : {args.model}")
    print(f"Media Source: {args.source} (repeat={args.repeat}, fps={args.fps})")
    print(f"Service Key : {'[CONFIGURED]' if service_key else '[NONE]'}")
    print(f"Bearer Token: {'[CONFIGURED]' if token else '[NONE]'}")
    print("=" * 78, flush=True)

    with httpx.Client(base_url=args.service_url, timeout=60.0) as client:
        # 1. Check service health first
        try:
            health_resp = client.get("/health")
            health_resp.raise_for_status()
        except Exception as exc:
            print(
                f"[ERROR] Cannot reach AI Service at {args.service_url}/health ({exc}). "
                "Ensure Terminal 1 is running.",
                file=sys.stderr,
            )
            return 1

        # 2. Trigger background runtime execution inside AI Service
        payload = {
            "cameraId": args.camera,
            "source": args.source,
            "sourceType": args.source_type,
            "modelPath": args.model,
            "repeat": args.repeat,
            "fps": args.fps,
            "maxFrames": args.max_frames,
            "background": True,
        }
        start_resp = client.post("/internal/v1/runtime/run", json=payload, headers=headers)
        if start_resp.status_code != 200:
            print(
                f"[ERROR] Failed to start runtime ({start_resp.status_code}): {start_resp.text}",
                file=sys.stderr,
            )
            return 1

        start_data = start_resp.json()
        resolved_camera = start_data.get("cameraId", args.camera)
        print(f"[RUNTIME STARTED] {json.dumps(start_data)}", flush=True)

        # 3. Poll status until stream completes (status transitions to OFFLINE after processing frames)
        last_frames = -1
        deadline = time.time() + 120.0
        while time.time() < deadline:
            status_resp = client.get(f"/api/v1/ai/cameras/{resolved_camera}/status")
            if status_resp.status_code == 200:
                st = status_resp.json()
                proc = st.get("processedFrames", 0)
                cam_status = st.get("status")
                if proc != last_frames or cam_status == "OFFLINE":
                    print(
                        f"[RUNTIME PROGRESS] cameraId={resolved_camera} status={cam_status} "
                        f"processedFrames={proc} fps={st.get('fps')} "
                        f"model={st.get('modelVersion')} tracker={st.get('trackerType')} "
                        f"size={st.get('width')}x{st.get('height')}",
                        flush=True,
                    )
                    last_frames = proc
                if cam_status == "OFFLINE" and proc > 0:
                    break
            time.sleep(0.35)

        # 4. Print final canonical runtime snapshot
        print("-" * 78)
        status_json = client.get(f"/api/v1/ai/cameras/{resolved_camera}/status").json()
        det_json = client.get(f"/api/v1/ai/cameras/{resolved_camera}/detections/latest").json()
        cnt_json = client.get(f"/api/v1/ai/cameras/{resolved_camera}/counts/latest").json()
        ev_json = client.get("/api/v1/ai/events", params={"cameraId": resolved_camera}).json()

        print(f"[FINAL STATUS]     {json.dumps(status_json)}")
        print(f"[LATEST DETECTION] {json.dumps(det_json)}")
        print(f"[LATEST COUNT]     {json.dumps(cnt_json)}")
        print(f"[AI EVENTS]        count={len(ev_json)} events={json.dumps(ev_json)}")
        print("=" * 78, flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
