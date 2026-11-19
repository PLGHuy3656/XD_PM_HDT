from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.command import (
    AckStatus,
    CommandAction,
    CommandStatus,
    ControlMode,
    DeviceCommand,
    RelayTarget,
)
from app.schemas.presence import DevicePresence
from app.schemas.telemetry import (
    AcceptedTelemetry,
    ActuatorState,
    DeviceRuntimeState,
    TelemetryMetrics,
)


class TelemetryResponse(BaseModel):
    """CamelCase API representation of an accepted telemetry record."""
    model_config = ConfigDict(extra="forbid")

    deviceId: str
    receivedAt: datetime
    metrics: TelemetryMetrics
    actuators: ActuatorState
    state: DeviceRuntimeState

    @classmethod
    def from_domain(cls, telemetry: AcceptedTelemetry) -> "TelemetryResponse":
        return cls(
            deviceId=telemetry.device_id,
            receivedAt=telemetry.received_at,
            metrics=telemetry.metrics,
            actuators=telemetry.actuators,
            state=telemetry.state,
        )


class PresenceResponse(BaseModel):
    """CamelCase API representation of device presence."""
    model_config = ConfigDict(extra="forbid")

    deviceId: str
    status: Literal["ONLINE", "OFFLINE", "STALE"]
    lastSeen: datetime | None = None
    lastHeartbeatAt: datetime | None = None
    lastStatusAt: datetime | None = None
    uptime: int | None = None
    ip: str | None = None
    freeHeap: int | None = None
    mockMode: bool | None = None

    @classmethod
    def from_domain(cls, presence: DevicePresence) -> "PresenceResponse":
        return cls(
            deviceId=presence.device_id,
            status=presence.status,
            lastSeen=presence.last_seen,
            lastHeartbeatAt=presence.last_heartbeat_at,
            lastStatusAt=presence.last_status_at,
            uptime=presence.uptime,
            ip=presence.ip,
            freeHeap=presence.free_heap,
            mockMode=presence.mock_mode,
        )


class RelayCommandRequest(BaseModel):
    """Request body for POST /api/iot/devices/{device_id}/commands/relay.

    Does NOT accept commandId from client (extra="forbid").
    """
    model_config = ConfigDict(extra="forbid", strict=True)

    target: RelayTarget = Field(
        ..., description="Target relay: misting, fan, heater, or alarm"
    )
    state: Literal[0, 1] = Field(..., description="0 = OFF, 1 = ON")


class ConfigCommandRequest(BaseModel):
    """Request body for POST /api/iot/devices/{device_id}/commands/config.

    Does NOT accept commandId from client (extra="forbid").
    """
    model_config = ConfigDict(extra="forbid", strict=True)

    targetTemp: float = Field(
        ...,
        ge=-20.0,
        le=60.0,
        description="Target temperature in Celsius (-20..60)",
    )
    targetHum: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Target relative humidity in % (0..100)",
    )
    isAutoMode: bool = Field(
        ...,
        description="True for local AUTO rule engine, False for MANUAL mode",
    )


class CommandResponse(BaseModel):
    """CamelCase API representation of a device command record."""
    model_config = ConfigDict(extra="forbid")

    commandId: str
    deviceId: str
    action: CommandAction
    payload: dict[str, Any]
    status: CommandStatus
    createdAt: datetime
    publishedAt: datetime | None = None
    acknowledgedAt: datetime | None = None
    ackStatus: AckStatus | None = None
    ackMessage: str | None = None
    ackMode: ControlMode | None = None

    @classmethod
    def from_domain(cls, cmd: DeviceCommand) -> "CommandResponse":
        return cls(
            commandId=cmd.command_id,
            deviceId=cmd.device_id,
            action=cmd.action,
            payload=cmd.payload,
            status=cmd.status,
            createdAt=cmd.created_at,
            publishedAt=cmd.published_at,
            acknowledgedAt=cmd.acknowledged_at,
            ackStatus=cmd.ack_status,
            ackMessage=cmd.ack_message,
            ackMode=cmd.ack_mode,
        )


RealtimeEventType = Literal[
    "telemetry.updated",
    "presence.updated",
    "command.updated",
]


class RealtimeEvent(BaseModel):
    """Canonical WebSocket realtime event envelope."""
    model_config = ConfigDict(extra="forbid")

    type: RealtimeEventType
    deviceId: str
    timestamp: datetime
    data: dict[str, Any]
