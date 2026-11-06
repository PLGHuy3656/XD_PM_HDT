"""
Debug script for testing WebSocket telemetry stream.
Usage:
    python scripts/test_websocket.py
"""

import asyncio
import json
import websockets


async def main():
    uri = "ws://127.0.0.1:8000/ws/telemetry"

    print(f"Connecting to {uri}...")
    async with websockets.connect(uri) as websocket:
        print("WebSocket connected!")
        print("Waiting for telemetry data...")

        message = await asyncio.wait_for(
            websocket.recv(),
            timeout=30,
        )

        print("Received telemetry:")
        print(json.dumps(json.loads(message), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
