import { devices as ownerDevicesMock } from '../../../components/features/farm-owner/devices/devicesMockData.js'
import { realNumberOrNull, resolveDeviceStatus } from '../deviceStatus.js'
import { formatRelativeTime } from '../../telemetry/provenance.js'

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

  // INT01-R1: UNKNOWN (never heartbeat) and UNAVAILABLE (IoT down) are no longer collapsed into OFFLINE
  const status = resolveDeviceStatus(raw)
  const health = raw.health_metadata || raw.healthMetadata || {}
  const lastSeenIso = raw.lastSeenAt || raw.last_seen_at || health.lastSeen || null
  const hasBeenSeen = Boolean(lastSeenIso) && ['ONLINE', 'WARNING', 'OFFLINE'].includes(status)

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
  // INT02-F04: a registered camera is REGISTERED (not "no heartbeat") — it never reports to IoT
  const effectiveStatus = type === 'CAMERA' && (status === 'UNKNOWN' || status === 'UNAVAILABLE') ? 'REGISTERED' : status

  return {
    id: raw.id || raw.device_id || 'unknown-device',
    code,
    name: raw.name || raw.device_name || code || 'Thiết bị không tên',
    type,
    typeLabel,
    farmId: raw.farmId || raw.farm_id || '',
    zoneId: raw.zoneId || raw.zone_id || '',
    zoneName: raw.zoneName || raw.zone_name || '',
    status: effectiveStatus,
    nodeId: raw.node_id || raw.nodeId || code,
    firmware: raw.firmware || raw.firmware_version || '--',
    // INT01-R1: never a fallback RSSI; Management does not report radio signal (detail panel reads telemetry)
    signal: realNumberOrNull(raw.signal ?? raw.rssi),
    lastSeenAt: lastSeenIso,
    lastSeen:
      lastSeenIso
        ? formatRelativeTime(lastSeenIso)
        : typeof raw.lastSeen === 'string' && !raw.health_metadata
          ? raw.lastSeen // mock fixtures only
          : '--',
    registeredIp: raw.ip_address || null,
    reportedIp: hasBeenSeen ? health.ip || null : null,
    iotAvailable: raw.iot_available !== false,
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
