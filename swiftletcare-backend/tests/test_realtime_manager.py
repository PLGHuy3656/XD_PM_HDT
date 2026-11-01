import asyncio

from app.realtime.manager import RealtimeManager


class FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def send_json(self, data):
        self.messages.append(data)


def test_broadcast_sends_telemetry_only_to_authorized_devices():
    async def run_test():
        manager = RealtimeManager()
        authorized_socket = FakeWebSocket()
        other_socket = FakeWebSocket()

        await manager.register(authorized_socket, {"node-01"})
        await manager.register(other_socket, {"node-02"})
        await manager.broadcast({"type": "telemetry", "nodeId": "node-01"})

        assert authorized_socket.messages == [
            {"type": "telemetry", "nodeId": "node-01"},
        ]
        assert other_socket.messages == []

    asyncio.run(run_test())
