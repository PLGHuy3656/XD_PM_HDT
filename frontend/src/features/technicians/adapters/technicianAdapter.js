import {
  devices as mockTechDevices,
  systemStats as mockTechStats,
  sensorHealth as mockSensorHealth,
  alerts as mockTechAlerts,
} from '../../../components/features/technician/dashboard/dashboardMockData.js'

import {
  farms as mockTechFarms,
  initialDevices as mockInitialDevices,
} from '../../../components/features/technician/devices/devicesMockData.js'

import {
  environmentSummary as mockEnvSummary,
  environmentZones as mockEnvZones,
} from '../../../components/features/technician/environment/environmentMockData.js'

/**
 * Normalizes assigned farm DTO for technician
 * @param {any} raw
 * @param {boolean} [isMockMode=false]
 * @returns {any}
 */
export function normalizeAssignedFarm(raw, isMockMode = false) {
  if (!raw) return null

  return {
    id: raw.id || raw.farm_id || 'unknown-farm',
    name: raw.name || raw.farm_name || 'Nhà yến chưa đặt tên',
    code: raw.code || raw.farm_code || 'DEMO-FARM',
    address: raw.address || 'Chưa cập nhật địa chỉ',
    status: raw.status || 'ACTIVE',
    zoneCount: Number(raw.zone_count ?? (Array.isArray(raw.zones) ? raw.zones.length : 0)),
    deviceCount: Number(raw.device_count ?? (Array.isArray(raw.devices) ? raw.devices.length : 0)),
    ownerName: raw.owner_name || (isMockMode ? 'Chủ trại Demo' : 'Chưa cập nhật'),
    ownerPhone: raw.owner_phone || (isMockMode ? '090 123 4567' : '---'),
    zones: Array.isArray(raw.zones) ? raw.zones : [],
  }
}

/**
 * Normalizes technician device DTO
 * @param {any} raw
 * @param {string} [farmName='']
 * @returns {any}
 */
export function normalizeTechDevice(raw, farmName = '') {
  if (!raw) return null

  const rawStatus = String(raw.status || 'OFFLINE').toUpperCase()
  const status = ['ONLINE', 'ACTIVE', 'HEALTHY'].includes(rawStatus)
    ? 'ONLINE'
    : ['WARNING', 'DEGRADED'].includes(rawStatus)
      ? 'WARNING'
      : 'OFFLINE'

  const id = raw.id || raw.device_id || raw.node_id || 'unknown-device'
  const name = raw.name || raw.device_name || raw.node_id || id
  const rawType = String(raw.type || raw.device_type || 'SENSOR').toUpperCase()
  const type =
    rawType.includes('CAMERA')
      ? 'CAMERA'
      : rawType.includes('CONTROLLER') || rawType.includes('CTRL')
        ? 'CONTROLLER'
        : rawType.includes('AUDIO')
          ? 'AUDIO'
          : 'SENSOR'
  const zoneName = raw.zone_name || raw.zoneName || 'Tầng 1'
  const effectiveFarmName = farmName || raw.farm_name || raw.farmName || 'Nhà yến'

  return {
    id,
    nodeId: raw.node_id || id,
    name,
    type,
    typeLabel: raw.type_label || raw.typeLabel || type,
    farmId: raw.farm_id || raw.farmId || '',
    farmName: effectiveFarmName,
    zoneId: raw.zone_id || raw.zoneId || '',
    zoneName,
    zone: `${effectiveFarmName} · ${zoneName}`,
    status,
    statusLower: status.toLowerCase(),
    firmware: raw.firmware_version || raw.firmware || 'v1.0.0',
    ipAddress: raw.ip_address || '---',
    mqttStatus: raw.mqtt_status || (status === 'ONLINE' ? 'Connected' : 'Disconnected'),
    signal: raw.rssi != null ? Number(raw.rssi) : -60,
    lastSeen: raw.last_seen || raw.lastSeen || 'Vừa xong',
    sensors: type === 'CAMERA' ? '0 / 0' : '2 / 2',
    description: raw.description || `Node ${name} đang hoạt động tại ${effectiveFarmName}`,
  }
}

/**
 * Normalizes technician dashboard stats into UI systemStats cards
 * @param {any} raw
 * @param {boolean} [isMockMode=false]
 * @returns {any[]}
 */
export function normalizeTechStats(raw, isMockMode = false) {
  if (!raw) return isMockMode ? mockTechStats : []

  const totalDev = Number(raw.device_count ?? 0)
  const onlineDev = Number(raw.online_device_count ?? 0)
  const offlineDev = Number(raw.offline_device_count ?? 0)
  const farmCount = Number(raw.assigned_farm_count ?? 0)
  const zoneCount = Number(raw.zone_count ?? 0)

  const nodeStatus = offlineDev > 0 ? 'warning' : 'healthy'
  const nodeStatusLabel = offlineDev > 0 ? `${offlineDev} ngoại tuyến` : 'Hoạt động tốt'

  return [
    {
      id: 'nodes',
      label: 'Device Nodes',
      value: `${onlineDev} / ${totalDev}`,
      description: offlineDev > 0 ? `${offlineDev} node cần kiểm tra kết nối` : 'Tất cả node đang trực tuyến',
      status: nodeStatus,
      statusLabel: nodeStatusLabel,
      icon: 'N',
    },
    {
      id: 'farms',
      label: 'Nhà yến phụ trách',
      value: `${farmCount}`,
      description: `${zoneCount} khu vực đang được giám sát`,
      status: 'healthy',
      statusLabel: 'Đang phụ trách',
      icon: 'F',
    },
    {
      id: 'sensors',
      label: 'Sensors & Môi trường',
      value: `${zoneCount * 2} sensors`,
      description: 'Giám sát nhiệt độ, độ ẩm vi khí hậu',
      status: 'healthy',
      statusLabel: 'Hoạt động',
      icon: 'S',
    },
    {
      id: 'mqtt',
      label: 'Gateway & MQTT',
      value: 'Connected',
      description: 'Kết nối API Gateway ổn định',
      status: 'healthy',
      statusLabel: 'Đã kết nối',
      icon: 'M',
    },
  ]
}

/**
 * Normalizes alert for technician view
 * @param {any} raw
 * @returns {any}
 */
export function normalizeTechAlert(raw) {
  if (!raw) return null

  const rawSeverity = String(raw.severity || raw.level || 'INFO').toUpperCase()
  const level = ['CRITICAL', 'DANGER'].includes(rawSeverity)
    ? 'critical'
    : ['WARNING', 'WARN'].includes(rawSeverity)
      ? 'warning'
      : 'info'

  return {
    id: raw.id || raw.alert_id || 'ALT-000',
    level,
    status: raw.status || (raw.acknowledged ? 'INVESTIGATING' : 'OPEN'),
    title: raw.title || raw.message || 'Cảnh báo kỹ thuật',
    description: raw.description || `${raw.farm_name || raw.farmName || 'Nhà yến'} · ${raw.zone_name || raw.zoneName || 'Khu vực'}`,
    farm: raw.farm_name || raw.farmName || 'Nhà yến',
    farmId: raw.farm_id || raw.farmId || '',
    zone: raw.zone_name || raw.zoneName || 'Khu vực',
    zoneId: raw.zone_id || raw.zoneId || '',
    device: raw.device_name || raw.deviceName || 'Node',
    deviceId: raw.device_id || raw.deviceId || '',
    time: raw.time || raw.timeAgo || raw.timestamp || 'Vừa xong',
  }
}

export function getMockTechDashboard() {
  return {
    systemStats: mockTechStats,
    devices: mockTechDevices,
    sensorHealth: mockSensorHealth,
    alerts: mockTechAlerts,
  }
}

export function getMockTechFarms() {
  return mockTechFarms
}

export function getMockTechDevices() {
  return mockInitialDevices
}

export function getMockEnvZones() {
  return mockEnvZones
}
