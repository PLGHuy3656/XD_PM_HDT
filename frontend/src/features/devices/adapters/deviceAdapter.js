import { devices as ownerDevicesMock } from '../../../components/features/farm-owner/devices/devicesMockData.js'

const TYPE_LABELS = {
  CONTROLLER: 'ESP32 Controller',
  SENSOR: 'Cảm biến môi trường',
  ENVIRONMENT_MONITOR: 'Cảm biến môi trường',
  CAMERA: 'AI Camera Node',
  AUDIO: 'Audio Monitoring Node',
}

/**
 * Normalizes device DTO from API or mock
 * @param {any} raw
 * @returns {any}
 */
export function normalizeDevice(raw) {
  if (!raw) return null

  const rawStatus = String(raw.status || 'OFFLINE').toUpperCase()
  const status = ['ONLINE', 'ACTIVE', 'HEALTHY'].includes(rawStatus)
    ? 'ONLINE'
    : ['WARNING', 'DEGRADED'].includes(rawStatus)
      ? 'WARNING'
      : 'OFFLINE'

  const rawType = String(raw.type || raw.device_type || 'SENSOR').toUpperCase()
  const type =
    rawType.includes('CAMERA')
      ? 'CAMERA'
      : rawType.includes('CONTROLLER') || rawType.includes('CTRL')
        ? 'CONTROLLER'
        : rawType.includes('AUDIO')
          ? 'AUDIO'
          : 'SENSOR'

  const typeLabel =
    raw.typeLabel ||
    raw.type_label ||
    TYPE_LABELS[rawType] ||
    TYPE_LABELS[type] ||
    'Thiết bị IoT'

  const code = raw.node_id || raw.code || raw.device_code || raw.id || ''

  return {
    id: raw.id || raw.device_id || 'unknown-device',
    code,
    name: raw.name || raw.device_name || code || 'Thiết bị không tên',
    type,
    typeLabel,
    farmId: raw.farmId || raw.farm_id || '',
    zoneId: raw.zoneId || raw.zone_id || '',
    zoneName: raw.zoneName || raw.zone_name || '',
    status,
    firmware: raw.firmware || raw.firmware_version || 'v1.0.0',
    signal: raw.signal != null ? Number(raw.signal) : raw.rssi != null ? Number(raw.rssi) : -60,
    lastSeen: raw.lastSeen || raw.last_seen || raw.last_ping || 'Vừa xong',
    description:
      raw.description ||
      (type === 'CAMERA'
        ? 'Camera giám sát AI'
        : type === 'SENSOR'
          ? 'Cảm biến theo dõi vi khí hậu'
          : 'Thiết bị vận hành nhà yến'),
  }
}

export function getMockDevices() {
  return ownerDevicesMock.map(normalizeDevice)
}
