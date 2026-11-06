"""Minimal WebSocket Realtime Observer for SwiftletCare IoT Service.

Connects to:
    ws://localhost:8002/ws/iot

Prints incoming realtime events in human-readable JSON format:
    - telemetry.updated
    - presence.updated
    - command.updated

Usage:
    python demo/ws_observer.py
    python demo/ws_observer.py --url ws://localhost:8002/ws/iot --device-id SWC-NODE-001
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone

import websockets


async def observe_websocket(url: str, device_filter: str | None = None) -> None:
    print("=" * 72)
    print("SwiftletCare IoT Realtime WebSocket Observer")
    print(f"Target URL    : {url}")
    if device_filter:
        print(f"Device Filter : {device_filter}")
    print("Press Ctrl+C to stop.")
    print("=" * 72)

    while True:
        try:
            async with websockets.connect(url) as ws:
                now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
                print(f"[{now_str}] [WS CONNECTED] Listening for realtime events on {url}...\n")
                async for raw_message in ws:
                    try:
                        event = json.loads(raw_message)
                    except json.JSONDecodeError:
                        print(f"[WS RAW] {raw_message}")
                        continue

                    device_id = event.get("deviceId")
                    if device_filter and device_id != device_filter:
                        continue

                    event_type = event.get("type", "unknown")
                    timestamp = event.get("timestamp", "")

                    print(f">>> [{event_type}] deviceId={device_id} timestamp={timestamp}")
                    print(json.dumps(event, indent=2))
                    print("-" * 72)
        except asyncio.CancelledError:
            break
        except (OSError, websockets.WebSocketException) as exc:
            now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
            print(f"[{now_str}] [WS DISCONNECTED] ({exc}) - retrying in 2s...")
            await asyncio.sleep(2.0)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SwiftletCare IoT WebSocket Observer"
    )
    parser.add_argument(
        "--url",
        default="ws://localhost:8002/ws/iot",
        help="WebSocket endpoint URL (default: ws://localhost:8002/ws/iot)",
    )
    parser.add_argument(
        "--device-id",
        default=None,
        help="Optional deviceId filter (e.g. SWC-NODE-001)",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(observe_websocket(args.url, args.device_id))
    except KeyboardInterrupt:
        print("\n[WS OBSERVER] Stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
