# SwiftletCare IoT Service

The **IoT Service** is a dedicated business microservice in the SwiftletCare Microservice Architecture responsible for IoT communications, device telemetry, device runtime presence, actuator control, and realtime streams.

## Bounded Context Ownership

- **MQTT Lifecycle**: Client connection, keep-alive, subscriptions, and publication.
- **Telemetry Processing**: Ingestion, validation, and historical persistence into `iot_db`.
- **Heartbeat & Presence**: Device online/offline state detection, LWT, and Redis runtime cache.
- **Device Commands**: Actuator control commands and acknowledgement tracking (`swiftlet/command/`, `swiftlet/ack/`).
- **Control Modes**: AUTO and MANUAL control configurations and runtime state integration.
- **Realtime Delivery**: WebSocket streaming of live device states to clients.

## MQTT Topic Taxonomy

- `swiftlet/telemetry/{device_code}`: Periodic environmental telemetry data.
- `swiftlet/heartbeat/{device_code}`: Lightweight device heartbeats and network diagnostics.
- `swiftlet/status/{device_code}`: Presence, connection lifecycle, and LWT notifications.
- `swiftlet/command/{device_code}`: Downlink control directives sent to field nodes.
- `swiftlet/ack/{device_code}`: Command receipt and execution acknowledgements.

## Getting Started

### Configuration

Copy `.env.example` to `.env` and set environment variables:

```bash
cp .env.example .env
```

### Running Locally

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload
```

### Testing

```bash
pytest tests/ -v
```
