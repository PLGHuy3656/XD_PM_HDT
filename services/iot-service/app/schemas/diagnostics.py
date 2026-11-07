"""Schemas for Device Diagnostics, Health Telemetry, and Admin/Technician Provisioning."""

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class ConnectivityInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mqtt: Literal["CONNECTED", "UNSTABLE", "DISCONNECTED"]
    wifi: Literal["CONNECTED", "WEAK", "DISCONNECTED"]
    rssi: int | None = None
    ip: str | None = None


class SensorHealthItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    status: Literal["HEALTHY", "WARNING", "UNAVAILABLE"]
    value: str


class ActuatorHealthItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    status: Literal["HEALTHY", "WARNING"]


class DeviceDiagnosticDetail(BaseModel):
    """Detailed diagnostic view matching Technician Diagnostics UI contract."""
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    type: str
    farm: str
    zone: str
    status: Literal["HEALTHY", "WARNING", "OFFLINE"]
    lastSeen: str
    connectivity: ConnectivityInfo
    sensors: list[SensorHealthItem]
    actuators: list[ActuatorHealthItem]
    issues: list[str]


class DiagnosticSummary(BaseModel):
    """System-wide diagnostic counts for Technician Dashboard."""
    model_config = ConfigDict(extra="forbid")

    totalNodes: int
    healthyNodes: int
    warningNodes: int
    offlineNodes: int


class DeviceHealthMetadata(BaseModel):
    """Lightweight health metadata for Administrator Device Overview."""
    model_config = ConfigDict(extra="forbid")

    uptime: int | None = None
    ip: str | None = None
    freeHeap: int | None = None
    networkRssi: int | None = None
    mockMode: bool | None = None
    lastSeen: str | None = None


class AdminDeviceRegistryItem(BaseModel):
    """Administrator Device Registry item with provisioning status & health metadata."""
    model_config = ConfigDict(extra="forbid")

    deviceId: str
    name: str
    type: str
    farmId: str
    farmName: str
    zoneId: str
    zoneName: str
    provisioningStatus: Literal["PROVISIONED", "ATTENTION", "DISCONNECTED", "PENDING_ACTIVATION"]
    status: Literal["ONLINE", "WARNING", "OFFLINE"]
    health: DeviceHealthMetadata
    firmwareVersion: str
    isActive: bool


class InstallationVerificationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passed: bool
    label: str
    description: str
    details: dict[str, Any] = Field(default_factory=dict)


class InstallationChecklistResponse(BaseModel):
    """Technician Installation verification checklist response."""
    model_config = ConfigDict(extra="forbid")

    deviceId: str
    power: InstallationVerificationCheck
    network: InstallationVerificationCheck
    mqtt: InstallationVerificationCheck
    sensor: InstallationVerificationCheck
    actuator: InstallationVerificationCheck
    allPassed: bool
    activationReady: bool


class ProvisionDeviceRequest(BaseModel):
    """Provisioning setup payload sent by Technician."""
    model_config = ConfigDict(extra="forbid")

    farmId: str
    zoneId: str
    serialNumber: str
    deviceType: str = "controller"
    firmwareVersion: str = "v1.4.2"
    samplingInterval: int = 30
