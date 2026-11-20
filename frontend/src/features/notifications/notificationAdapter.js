import { formatRelativeTime } from '../telemetry/provenance.js'

/**
 * INT03: Notification Service DTO -> UI shapes. Everything comes from the persisted notification
 * (title/message/category built server-side from the domain event); nothing is invented here.
 * DTO: { id, event_id, event_type, title, message, category: info|warning|critical, data, created_at, read_at }
 */
export function notificationSource(eventType = '') {
  const t = String(eventType)
  if (t.startsWith('ai.')) return 'AI'
  if (t.startsWith('iot.') || t.startsWith('device.') || t.startsWith('environment.')) return 'IoT'
  return 'Hệ thống'
}

export function notificationSeverity(category = '') {
  const c = String(category).toLowerCase()
  if (c === 'critical' || c === 'danger') return 'CRITICAL'
  if (c === 'warning') return 'WARNING'
  return 'INFO'
}

export function notificationFarmId(n) {
  const d = n?.data || {}
  return d.farmId || d.farm_id || null
}

export function notificationZoneId(n) {
  const d = n?.data || {}
  const z = d.zoneId || d.zone_id || null
  return z && z !== 'UNASSIGNED' ? z : null
}

function confidencePercent(d) {
  const c = d?.confidence
  if (typeof c !== 'number' || !Number.isFinite(c)) return null
  return Math.round(c <= 1 ? c * 100 : c)
}

/** Header popover item */
export function toPopoverItem(n, { farmNames = {} } = {}) {
  const severity = notificationSeverity(n.category)
  const farmId = notificationFarmId(n)
  return {
    id: n.id,
    type: severity === 'CRITICAL' ? 'danger' : severity === 'WARNING' ? 'warning' : 'info',
    severity,
    source: notificationSource(n.event_type),
    title: n.title || '--',
    message: n.message || '',
    farmName: farmId ? farmNames[farmId] || null : null,
    time: n.created_at ? formatRelativeTime(n.created_at) : '--',
    createdAt: n.created_at || null,
    unread: !n.read_at,
  }
}

/** Alerts page row (owner). Status follows the current contract: unread (OPEN) / read (ACKNOWLEDGED). */
export function toAlertRow(n, { zoneNames = {}, farmNames = {} } = {}) {
  const d = n.data || {}
  const farmId = notificationFarmId(n)
  const zoneId = notificationZoneId(n)
  return {
    id: n.id,
    severity: notificationSeverity(n.category),
    status: n.read_at ? 'ACKNOWLEDGED' : 'OPEN',
    source: notificationSource(n.event_type),
    type: n.event_type,
    device: d.deviceId || d.device_id || d.cameraId || d.node_id || '--',
    title: n.title || '--',
    description: n.message || '',
    farmId: farmId || '',
    farmName: farmId ? farmNames[farmId] || '' : '',
    zoneId: zoneId || '',
    zoneName: zoneId ? zoneNames[zoneId] || zoneId : '--',
    timestamp: n.created_at || null,
    time: n.created_at ? formatRelativeTime(n.created_at) : '--',
    value: null,
    threshold: null,
    confidence: confidencePercent(d),
  }
}
