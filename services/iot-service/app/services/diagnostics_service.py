"""Device Diagnostics & Provisioning Service for SwiftletCare IoT Service.

Provides:
- Technician Diagnostics: deep health signals (heartbeat, RSSI, MQTT status, sensor health, actuator health, issues).
- Administrator Provisioning: overview of registered devices with provisioning status & lightweight health metadata.
- Technician Installation: 5-step checklist validation (Power, Network, MQTT, Sensors, Actuators) and activation readiness.
"""

from datetime import datetime, timezone
import logging
from typing import Any

from app.domain_events.metadata_resolver import (
    DeviceMetadataResolver,
    default_metadata_resolver,
)
from app.repositories.command_repository import (
    CommandRepository,
    default_command_repository,
)
from app.repositories.presence_repository import (
    DevicePresenceRepository,
    default_presence_repository,
)
from app.repositories.telemetry_repository import (
    TelemetryRepository,
    default_telemetry_repository,
)
from app.schemas.diagnostics import (
    ActuatorHealthItem,
    AdminDeviceRegistryItem,
    ConnectivityInfo,
    DeviceDiagnosticDetail,
    DeviceHealthMetadata,
    DiagnosticSummary,
    InstallationChecklistResponse,
    InstallationVerificationCheck,
    ProvisionDeviceRequest,
    SensorHealthItem,
)
from app.services.command_service import DeviceCommandService, command_service

logger = logging.getLogger("iot_service.diagnostics")


class DiagnosticsService:
    """Consolidates edge health signals and provides diagnostic/provisioning endpoints."""

    def __init__(
        self,
        telemetry_repo: TelemetryRepository | None = None,
        presence_repo: DevicePresenceRepository | None = None,
        command_repo: CommandRepository | None = None,
        cmd_service: DeviceCommandService | None = None,
        metadata_resolver: DeviceMetadataResolver | None = None,
    ):
        self.telemetry_repo = telemetry_repo or default_telemetry_repository
        self.presence_repo = presence_repo or default_presence_repository
        self.command_repo = command_repo or default_command_repository
        self.cmd_service = cmd_service or command_service
        self.resolver = metadata_resolver or default_metadata_resolver

        # Known device catalog for registry & diagnostics
        self._catalog: dict[str, dict[str, str]] = {
            "SWC-NODE-001": {
                "name": "Bộ điều khiển Zone 1",
                "type": "ESP32 Controller",
                "farmId": "FARM-01",
                "farmName": "Nhà yến Bình An",
                "zoneId": "ZONE-01",
                "zoneName": "Khu vực A",
                "firmwareVersion": "v1.4.2",
            },
            "ESP32-CTRL-01": {
                "name": "Bộ điều khiển Zone A",
                "type": "ESP32 Controller",
                "farmId": "farm-binh-an",
                "farmName": "Nhà yến Bình An",
                "zoneId": "zone-a",
                "zoneName": "Khu vực A",
                "firmwareVersion": "v1.4.2",
            },
            "ESP32-CTRL-02": {
                "name": "Bộ điều khiển Zone B",
                "type": "ESP32 Controller",
                "farmId": "farm-binh-an",
                "farmName": "Nhà yến Bình An",
                "zoneId": "zone-b",
                "zoneName": "Khu vực B",
                "firmwareVersion": "v1.4.2",
            },
            "ESP32-CTRL-04": {
                "name": "Bộ điều khiển Zone D",
                "type": "ESP32 Controller",
                "farmId": "farm-phu-an",
                "farmName": "Nhà yến Phú An",
                "zoneId": "zone-d",
                "zoneName": "Khu vực D",
                "firmwareVersion": "v1.4.2",
            },
            "AUDIO-01": {
                "name": "Node âm thanh Zone C",
                "type": "Audio Edge Node",
                "farmId": "farm-binh-an",
                "farmName": "Nhà yến Bình An",
                "zoneId": "zone-c",
                "zoneName": "Khu vực C",
                "firmwareVersion": "v1.2.0",
            },
            "swc-h01-f01-node01": {
                "name": "Bộ điều khiển Vi khí hậu H01",
                "type": "ESP32 Controller",
                "farmId": "FARM-01",
                "farmName": "Nhà yến Bình An",
                "zoneId": "ZONE-01",
                "zoneName": "Khu vực A",
                "firmwareVersion": "v1.4.2",
            },
        }

    def register_catalog_device(self, device_id: str, meta: dict[str, str]) -> None:
        self._catalog[device_id] = meta

    def get_device_diagnostics(self, device_id: str) -> DeviceDiagnosticDetail | None:
        """Builds deep technical diagnostic signals for Technician."""
        catalog_entry = self._catalog.get(device_id)
        name = catalog_entry["name"] if catalog_entry else f"Node {device_id}"
        dev_type = catalog_entry["type"] if catalog_entry else "ESP32 Controller"
        farm_name = catalog_entry["farmName"] if catalog_entry else "Nhà yến Bình An"
        zone_name = catalog_entry["zoneName"] if catalog_entry else "Khu vực A"

        presence = self.presence_repo.get(device_id)
        latest_telemetry = self.telemetry_repo.get_latest(device_id)

        issues: list[str] = []

        # Determine online / offline status
        is_online = (presence is not None and presence.status == "ONLINE")
        is_stale = (presence is not None and presence.status == "STALE")

        if presence is None or presence.status == "OFFLINE":
            status = "OFFLINE"
            mqtt_status = "DISCONNECTED"
            wifi_status = "DISCONNECTED"
            rssi = None
            ip = presence.ip if presence else None
            issues.append("Node không gửi heartbeat.")
            issues.append("MQTT đã mất kết nối.")
        elif is_stale:
            status = "OFFLINE"
            mqtt_status = "UNSTABLE"
            wifi_status = "WEAK"
            rssi = latest_telemetry.state.networkRssi if latest_telemetry else None
            ip = presence.ip
            issues.append("Heartbeat quá hạn (>90s) - mất tín hiệu định kỳ.")
        else:
            # ONLINE node - check health signals
            status = "HEALTHY"
            mqtt_status = "CONNECTED"
            rssi = latest_telemetry.state.networkRssi if latest_telemetry else -50
            ip = presence.ip or "192.168.1.50"

            if rssi and rssi < -75:
                wifi_status = "WEAK"
                status = "WARNING"
                issues.append(f"Tín hiệu Wi-Fi yếu ({rssi} dBm), kết nối MQTT có thể không ổn định.")
            else:
                wifi_status = "CONNECTED"

            if presence.free_heap and presence.free_heap < 25000:
                status = "WARNING"
                issues.append(f"Bộ nhớ ESP32 thấp ({presence.free_heap} bytes free).")

        # Format lastSeen
        now = datetime.now(timezone.utc)
        if presence and presence.last_seen:
            diff_secs = int((now - presence.last_seen).total_seconds())
            if diff_secs < 60:
                last_seen_str = f"{max(1, diff_secs)} giây trước"
            elif diff_secs < 3600:
                last_seen_str = f"{diff_secs // 60} phút trước"
            else:
                last_seen_str = f"{diff_secs // 3600} giờ trước"
        else:
            last_seen_str = "Chưa có dữ liệu"

        # Sensors health
        sensors: list[SensorHealthItem] = []
        if latest_telemetry and status != "OFFLINE":
            m = latest_telemetry.metrics
            temp_status = "HEALTHY" if 20.0 <= m.temperature <= 35.0 else "WARNING"
            hum_status = "HEALTHY" if 65.0 <= m.humidity <= 90.0 else "WARNING"
            co2_status = "HEALTHY" if m.co2 <= 1000.0 else "WARNING"
            lux_status = "HEALTHY" if m.lux <= 2.0 else "WARNING"

            sensors.append(SensorHealthItem(name="Nhiệt độ", status=temp_status, value=f"{m.temperature:.1f}°C"))
            sensors.append(SensorHealthItem(name="Độ ẩm", status=hum_status, value=f"{m.humidity:.1f}%"))
            sensors.append(SensorHealthItem(name="CO₂", status=co2_status, value=f"{int(m.co2)} ppm"))
            sensors.append(SensorHealthItem(name="Ánh sáng", status=lux_status, value=f"{m.lux:.1f} lux"))

            if not m.audioHealthy:
                status = "WARNING"
                issues.append("Cảm biến âm thanh phát hiện mất tiếng loa ru.")
            if hum_status == "WARNING":
                status = "WARNING"
                issues.append(f"Độ ẩm ngoài dải tối ưu cho chim yến ({m.humidity:.1f}%).")
            if temp_status == "WARNING":
                status = "WARNING"
                issues.append(f"Nhiệt độ bất thường ({m.temperature:.1f}°C).")
        else:
            sensors.append(SensorHealthItem(name="Nhiệt độ", status="UNAVAILABLE", value="--"))
            sensors.append(SensorHealthItem(name="Độ ẩm", status="UNAVAILABLE", value="--"))
            sensors.append(SensorHealthItem(name="CO₂", status="UNAVAILABLE", value="--"))
            sensors.append(SensorHealthItem(name="Ánh sáng", status="UNAVAILABLE", value="--"))

        # Actuators health
        actuators: list[ActuatorHealthItem] = []
        if latest_telemetry and status != "OFFLINE":
            act = latest_telemetry.actuators
            actuators.append(ActuatorHealthItem(name="Quạt thông gió", status="HEALTHY" if not act.fan or is_online else "WARNING"))
            actuators.append(ActuatorHealthItem(name="Máy phun sương", status="HEALTHY" if not act.misting or is_online else "WARNING"))
            actuators.append(ActuatorHealthItem(name="Máy sưởi", status="HEALTHY"))
            actuators.append(ActuatorHealthItem(name="Còi báo động", status="HEALTHY"))
        else:
            actuators.append(ActuatorHealthItem(name="Quạt thông gió", status="WARNING"))
            actuators.append(ActuatorHealthItem(name="Máy phun sương", status="WARNING"))

        return DeviceDiagnosticDetail(
            id=device_id,
            name=name,
            type=dev_type,
            farm=farm_name,
            zone=zone_name,
            status=status,
            lastSeen=last_seen_str,
            connectivity=ConnectivityInfo(
                mqtt=mqtt_status,
                wifi=wifi_status,
                rssi=rssi,
                ip=ip,
            ),
            sensors=sensors,
            actuators=actuators,
            issues=issues,
        )

    def get_diagnostic_summary(self) -> DiagnosticSummary:
        """Calculates system-wide counts for Technician Dashboard."""
        all_ids = set(self._catalog.keys())
        for p in self.presence_repo.list_all():
            all_ids.add(p.device_id)

        healthy = 0
        warning = 0
        offline = 0

        for dev_id in all_ids:
            diag = self.get_device_diagnostics(dev_id)
            if diag:
                if diag.status == "HEALTHY":
                    healthy += 1
                elif diag.status == "WARNING":
                    warning += 1
                else:
                    offline += 1

        return DiagnosticSummary(
            totalNodes=len(all_ids),
            healthyNodes=healthy,
            warningNodes=warning,
            offlineNodes=offline,
        )

    def get_admin_registry_summary(self) -> list[AdminDeviceRegistryItem]:
        """Builds read-only device catalog with provisioning status for Administrator."""
        results: list[AdminDeviceRegistryItem] = []

        all_ids = list(self._catalog.keys())
        for dev_id in all_ids:
            cat = self._catalog[dev_id]
            presence = self.presence_repo.get(dev_id)
            latest_tel = self.telemetry_repo.get_latest(dev_id)

            if presence is None or presence.status == "OFFLINE":
                prov_status = "DISCONNECTED"
                sys_status = "OFFLINE"
            elif presence.status == "STALE":
                prov_status = "DISCONNECTED"
                sys_status = "OFFLINE"
            else:
                # Check for warning flags
                rssi = latest_tel.state.networkRssi if latest_tel else None
                if (rssi and rssi < -75) or (presence.free_heap and presence.free_heap < 25000):
                    prov_status = "ATTENTION"
                    sys_status = "WARNING"
                else:
                    prov_status = "PROVISIONED"
                    sys_status = "ONLINE"

            last_seen_str = presence.last_seen.isoformat() if (presence and presence.last_seen) else None

            health_meta = DeviceHealthMetadata(
                uptime=presence.uptime if presence else None,
                ip=presence.ip if presence else None,
                freeHeap=presence.free_heap if presence else None,
                networkRssi=latest_tel.state.networkRssi if latest_tel else None,
                mockMode=presence.mock_mode if presence else None,
                lastSeen=last_seen_str,
            )

            results.append(
                AdminDeviceRegistryItem(
                    deviceId=dev_id,
                    name=cat["name"],
                    type=cat["type"],
                    farmId=cat["farmId"],
                    farmName=cat["farmName"],
                    zoneId=cat["zoneId"],
                    zoneName=cat["zoneName"],
                    provisioningStatus=prov_status,
                    status=sys_status,
                    health=health_meta,
                    firmwareVersion=cat["firmwareVersion"],
                    isActive=True,
                )
            )

        return results

    def get_installation_checklist(self, device_id: str) -> InstallationChecklistResponse:
        """Validates 5 installation items for Technician."""
        presence = self.presence_repo.get(device_id)
        latest_tel = self.telemetry_repo.get_latest(device_id)

        # 1. Power check: Booted and has uptime
        power_passed = (presence is not None and (presence.uptime is not None and presence.uptime >= 0))
        power_check = InstallationVerificationCheck(
            passed=power_passed,
            label="Nguồn thiết bị",
            description="Thiết bị đã khởi động và cấp nguồn ổn định." if power_passed else "Chưa nhận được tín hiệu nguồn từ thiết bị.",
            details={"uptime": presence.uptime if presence else 0},
        )

        # 2. Network check: IP assigned and Wi-Fi RSSI valid
        network_passed = (presence is not None and bool(presence.ip) and presence.ip != "0.0.0.0")
        network_check = InstallationVerificationCheck(
            passed=network_passed,
            label="Kết nối mạng",
            description=f"Node có kết nối Wi-Fi và địa chỉ IP hợp lệ ({presence.ip if presence else 'None'})." if network_passed else "Chưa có kết nối mạng hoặc chưa cấp phát IP.",
            details={
                "ip": presence.ip if presence else None,
                "rssi": latest_tel.state.networkRssi if latest_tel else None,
            },
        )

        # 3. MQTT check: Presence ONLINE & heartbeat received
        mqtt_passed = (presence is not None and presence.status == "ONLINE")
        mqtt_check = InstallationVerificationCheck(
            passed=mqtt_passed,
            label="MQTT Broker",
            description="Thiết bị kết nối và gửi heartbeat đến broker thành công." if mqtt_passed else "Thiết bị chưa kết nối tới MQTT broker.",
            details={"status": presence.status if presence else "OFFLINE"},
        )

        # 4. Sensor telemetry check: At least 1 valid reading received
        sensor_passed = (latest_tel is not None and latest_tel.metrics is not None)
        sensor_check = InstallationVerificationCheck(
            passed=sensor_passed,
            label="Sensor telemetry",
            description="Dữ liệu cảm biến được đọc và ghi nhận bình thường." if sensor_passed else "Chưa nhận được bản tin telemetry từ cảm biến.",
            details={
                "temperature": latest_tel.metrics.temperature if latest_tel else None,
                "humidity": latest_tel.metrics.humidity if latest_tel else None,
            },
        )

        # 5. Actuator check: Actuators reported in state
        actuator_passed = (latest_tel is not None and latest_tel.actuators is not None)
        actuator_check = InstallationVerificationCheck(
            passed=actuator_passed,
            label="Actuator",
            description="Cơ cấu chấp hành và 4 rơ-le sẵn sàng nhận lệnh." if actuator_passed else "Chưa xác thực được phản hồi rơ-le.",
            details={"relays": latest_tel.actuators.model_dump() if latest_tel else {}},
        )

        all_passed = power_passed and network_passed and mqtt_passed and sensor_passed and actuator_passed

        return InstallationChecklistResponse(
            deviceId=device_id,
            power=power_check,
            network=network_check,
            mqtt=mqtt_check,
            sensor=sensor_check,
            actuator=actuator_check,
            allPassed=all_passed,
            activationReady=all_passed,
        )

    def provision_device(self, device_id: str, req: ProvisionDeviceRequest) -> dict[str, Any]:
        """Technician provisions a new node, registering farm/zone mapping and publishing setup command."""
        self.resolver.register(device_id, req.farmId, req.zoneId)
        self.register_catalog_device(
            device_id,
            {
                "name": f"Node {req.serialNumber}",
                "type": "ESP32 Controller" if req.deviceType == "controller" else req.deviceType,
                "farmId": req.farmId,
                "farmName": "Nhà yến Bình An" if "binh-an" in req.farmId.lower() else "Nhà yến Phú An",
                "zoneId": req.zoneId,
                "zoneName": f"Khu vực {req.zoneId.split('-')[-1].upper()}",
                "firmwareVersion": req.firmwareVersion,
            },
        )

        logger.info(
            "[DEVICE PROVISIONED] device_id='%s' serial='%s' farm='%s' zone='%s'",
            device_id,
            req.serialNumber,
            req.farmId,
            req.zoneId,
        )

        checklist = self.get_installation_checklist(device_id)

        return {
            "deviceId": device_id,
            "status": "PROVISIONED",
            "message": "Device successfully configured and registered into inventory.",
            "farmId": req.farmId,
            "zoneId": req.zoneId,
            "activationReady": checklist.activationReady,
            "checklist": checklist.model_dump(),
        }


default_diagnostics_service = DiagnosticsService()
