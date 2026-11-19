"""Realtime WebSocket Observer for SwiftletCare AI Service V1 (CP5.4 Terminal 2).

Connects to:
    ws://127.0.0.1:8003/ws/ai

Prints incoming canonical realtime events:
    - camera.status
    - detection.updated
    - count.updated
    - ai.event
with cameraId and concise canonical payload information.

Usage:
    python services/ai-service/demo/ws_observer.py
    python services/ai-service/demo/ws_observer.py --url ws://127.0.0.1:8003/ws/ai --camera-id CAM-01
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import websockets


def format_concise_summary(event_type: str, camera_id: str, data: Dict[str, Any]) -> str:
    """Format a concise one-line human summary for each canonical V1 WebSocket event."""
    if event_type == "camera.status":
        return (
            f"[{event_type}] cameraId={camera_id} | "
            f"status={data.get('status')} processedFrames={data.get('processedFrames')} "
            f"fps={data.get('fps')} size={data.get('width')}x{data.get('height')} "
            f"model={data.get('modelVersion')} tracker={data.get('trackerType')} "
            f"updatedAt={data.get('updatedAt')}"
        )
    if event_type == "detection.updated":
        frame = data.get("frame") or {}
        dets = data.get("detections") or []
        det_summary = ", ".join(
            f"{d.get('class')}({d.get('confidence'):.2f}, trackId={d.get('trackId')})"
            for d in dets[:5]
        ) or "none"
        return (
            f"[{event_type}] cameraId={camera_id} | "
            f"frameId={data.get('frameId')} capturedAt={data.get('capturedAt')} "
            f"frame={frame.get('width')}x{frame.get('height')} "
            f"detections={len(dets)} [{det_summary}]"
        )
    if event_type == "count.updated":
        return (
            f"[{event_type}] cameraId={camera_id} | "
            f"recordedAt={data.get('recordedAt')} "
            f"entryCount={data.get('entryCount')} exitCount={data.get('exitCount')} "
            f"netChange={data.get('netChange')} "
            f"deltaEntry={data.get('deltaEntry')} deltaExit={data.get('deltaExit')}"
        )
    if event_type == "ai.event":
        return (
            f"[{event_type}] cameraId={camera_id} | "
            f"eventId={data.get('eventId')} eventType={data.get('eventType')} "
            f"class={data.get('class')} confidence={data.get('confidence')} "
            f"detectedAt={data.get('detectedAt')} snapshot={data.get('snapshot')}"
        )
    return f"[{event_type}] cameraId={camera_id} | data={json.dumps(data)}"


async def observe_websocket(
    url: str,
    camera_filter: Optional[str] = None,
    max_messages: int = 0,
) -> None:
    target_url = url
    if camera_filter and "cameraId=" not in target_url:
        sep = "&" if "?" in target_url else "?"
        target_url = f"{target_url}{sep}cameraId={camera_filter}"

    print("=" * 78)
    print("SwiftletCare AI Service V1 — Realtime WebSocket Observer")
    print(f"Target URL    : {target_url}")
    if camera_filter:
        print(f"Camera Filter : {camera_filter}")
    print("Press Ctrl+C to stop.")
    print("=" * 78, flush=True)

    received_count = 0
    while True:
        try:
            async with websockets.connect(target_url) as ws:
                now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
                print(
                    f"[{now_str}] [WS CONNECTED] Listening for AI events on {target_url}...\n",
                    flush=True,
                )
                async for raw_message in ws:
                    try:
                        envelope = json.loads(raw_message)
                    except json.JSONDecodeError:
                        print(f"[WS RAW] {raw_message}", flush=True)
                        continue

                    event_type = envelope.get("type", "unknown")
                    camera_id = envelope.get("cameraId", "unknown")
                    data = envelope.get("data") or {}

                    if camera_filter and camera_id != camera_filter:
                        continue

                    print(">>> " + format_concise_summary(event_type, camera_id, data), flush=True)
                    print(json.dumps(envelope, indent=2), flush=True)
                    print("-" * 78, flush=True)

                    received_count += 1
                    if max_messages > 0 and received_count >= max_messages:
                        return
        except asyncio.CancelledError:
            break
        except (OSError, websockets.WebSocketException) as exc:
            now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
            print(
                f"[{now_str}] [WS DISCONNECTED] ({exc}) - retrying in 2s...",
                flush=True,
            )
            await asyncio.sleep(2.0)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SwiftletCare AI Service V1 WebSocket Observer"
    )
    parser.add_argument(
        "--url",
        default="ws://127.0.0.1:8003/ws/ai",
        help="WebSocket endpoint URL (default: ws://127.0.0.1:8003/ws/ai)",
    )
    parser.add_argument(
        "--camera-id",
        default=None,
        help="Optional cameraId filter (e.g. CAM-01)",
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=0,
        help="Exit automatically after receiving N messages (0 = run until Ctrl+C)",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(
            observe_websocket(
                url=args.url,
                camera_filter=args.camera_id,
                max_messages=args.max_messages,
            )
        )
    except KeyboardInterrupt:
        print("\n[WS OBSERVER] Stopped by user.", flush=True)
        sys.exit(0)


if __name__ == "__main__":
    main()
