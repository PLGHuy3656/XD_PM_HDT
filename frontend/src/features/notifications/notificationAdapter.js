import { formatRelativeTime } from '../telemetry/provenance.js'

/**
 * INT03 / INT03-R1: Notification Service DTO -> UI shapes. Everything comes from the persisted
 * notification (title/message/category built server-side from the domain event); nothing is invented.
 * DTO: { id, event_id, event_type, title, message, category: info|warning|danger, data, created_at, read_at }
 *
 * Status vocabulary is kept separate on purpose:
 *  - readState: notification UNREAD/READ (per user, persisted by the Notification Service)
 *  - alert acknowledgement / resolution: NOT supported by the current backend -> never faked
 *  - inspection request status: lives in Management (inspection_requests), never derived from "read"
 */
export function notificationSource(eventType = '') {
  const t = String(eventType)
  if (t.startsWith('ai.')) return 'AI'
  if (t.startsWith('iot.') || t.startsWith('device.') || t.startsWith('environment.')) return 'IoT'
  if (t.startsWith('management.')) return 'Quản lý'
  return 'Hệ thống'
}

export function isOperationalAlert(n) {
  const s = notificationSource(n?.event_type)
  return s === 'AI' || s === 'IoT'
}

export function notificationSeverity(category = '') {
  const c = String(category).toLowerCase()
  if (c === 'critical' || c === 'danger') return 'CRITICAL'
  if (c === 'warning') return 'WARNING'
  return 'INFO'
}

export const READ_STATE_LABELS = {
  UNREAD: 'Chưa đọc',
  READ: 'Đã đọc',
  // mock-mode legacy values
  OPEN: 'Đang mở',
  ACKNOWLEDGED: 'Đã xác nhận',
  RESOLVED: 'Đã xử lý',
}

export const SEVERITY_LABELS = { CRITICAL: 'Nghiêm trọng', WARNING: 'Cảnh báo', INFO: 'Thông tin' }

const EVENT_TYPE_LABELS = {
  'management.user.created': 'Tài khoản mới',
  'management.farm.approval_requested': 'Yêu cầu phê duyệt nhà yến',
  'management.farm.approved': 'Nhà yến được phê duyệt',
  'management.farm.rejected': 'Nhà yến bị từ chối',
  'management.technician.assigned': 'Phân công kỹ thuật viên',
  'management.technician.unassigned': 'Thu hồi phân công',
  'management.device.registered': 'Đăng ký thiết bị',
  'management.inspection_request.created': 'Yêu cầu kiểm tra mới',
  'management.inspection_request.assigned': 'Phân công yêu cầu kiểm tra',
  'management.inspection_request.status_changed': 'Cập nhật yêu cầu kiểm tra',
  'management.inspection_request.requeued': 'Yêu cầu kiểm tra chờ phân công lại',
  'iot.device.offline': 'Thiết bị mất kết nối',
  'iot.device.online': 'Thiết bị kết nối lại',
  'iot.command.failed': 'Lệnh điều khiển thất bại',
  'ai.predator.detected': 'AI phát hiện thiên địch',
}

export function eventTypeLabel(eventType = '') {
  const t = String(eventType)
  if (EVENT_TYPE_LABELS[t]) return EVENT_TYPE_LABELS[t]
  if (t.startsWith('iot.environment.')) return t.endsWith('.recovered') ? 'Môi trường ổn định trở lại' : 'Môi trường vượt ngưỡng'
  if (t.startsWith('iot.audio.')) return t.endsWith('.recovered') ? 'Âm thanh ổn định trở lại' : 'Lỗi âm thanh'
  return t || '--'
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

/** Zone label: only a zone confirmed by Management (data.zoneName) or by the farm's zone list. */
export function notificationZoneLabel(n, zoneNames = {}) {
  const d = n?.data || {}
  const zoneId = notificationZoneId(n)
  if (d.zoneName || d.zone_name) return d.zoneName || d.zone_name
  if (zoneId && zoneNames[zoneId]) return zoneNames[zoneId]
  if (d.zoneLabel) return d.zoneLabel // "Chưa phân bổ khu vực" (Management-confirmed: no zone)
  return null
}

export function notificationDevice(n) {
  const d = n?.data || {}
  return d.deviceName || d.deviceId || d.device_id || d.cameraId || d.camera_id || d.nodeId || d.node_id || null
}

/** Route to open for this notification and role (only routes that exist in the app). */
export function notificationLink(n, role) {
  const d = n?.data || {}
  if (role === 'TECHNICIAN' && d.technicianLink) return d.technicianLink
  if (role === 'FARM_OWNER' && d.ownerLink) return d.ownerLink
  const link = d.link
  if (typeof link !== 'string' || !link.startsWith('/')) return null
  const prefix = { ADMIN: '/admin', FARM_OWNER: '/owner', TECHNICIAN: '/technician' }[role]
  if (prefix && !link.startsWith(prefix)) return null // never send a user to another role's page
  return link
}

function confidencePercent(d) {
  const c = d?.confidence
  if (typeof c !== 'number' || !Number.isFinite(c)) return null
  return Math.round(c <= 1 ? c * 100 : c)
}

/** Header popover / notification center item */
export function toPopoverItem(n, { farmNames = {}, role } = {}) {
  const severity = notificationSeverity(n.category)
  const farmId = notificationFarmId(n)
  const d = n.data || {}
  return {
    id: n.id,
    eventId: n.event_id || null,
    type: severity === 'CRITICAL' ? 'danger' : severity === 'WARNING' ? 'warning' : 'info',
    severity,
    source: notificationSource(n.event_type),
    eventType: n.event_type,
    eventTypeLabel: eventTypeLabel(n.event_type),
    title: n.title || '--',
    message: n.message || '',
    farmName: d.farmName || (farmId ? farmNames[farmId] || null : null),
    zoneLabel: notificationZoneLabel(n),
    device: notificationDevice(n),
    link: notificationLink(n, role),
    time: n.created_at ? formatRelativeTime(n.created_at) : '--',
    createdAt: n.created_at || null,
    unread: !n.read_at,
    readAt: n.read_at || null,
  }
}

/**
 * Filter notification center items without ever merging distinct notifications/eventIds.
 */
export function filterNotifications(items, { readFilter = 'ALL', sourceFilter = 'ALL', query = '' } = {}) {
  const q = String(query || '').trim().toLowerCase()
  return items.filter((n) => {
    if (readFilter === 'UNREAD' && !n.unread) return false
    if (readFilter === 'READ' && n.unread) return false
    if (sourceFilter !== 'ALL' && n.source !== sourceFilter) return false
    if (!q) return true
    const haystack = [n.title, n.message, n.source, n.eventTypeLabel, n.farmName, n.zoneLabel, n.device]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return haystack.includes(q)
  })
}

/** Alerts page row (owner/technician operational alerts). Status = notification read state only. */
export function toAlertRow(n, { zoneNames = {}, farmNames = {} } = {}) {
  const d = n.data || {}
  const farmId = notificationFarmId(n)
  const zoneId = notificationZoneId(n)
  return {
    id: n.id,
    severity: notificationSeverity(n.category),
    readState: n.read_at ? 'READ' : 'UNREAD',
    status: n.read_at ? 'READ' : 'UNREAD',
    source: notificationSource(n.event_type),
    type: n.event_type,
    typeLabel: eventTypeLabel(n.event_type),
    device: notificationDevice(n) || '--',
    title: n.title || '--',
    description: n.message || '',
    farmId: farmId || '',
    farmName: d.farmName || (farmId ? farmNames[farmId] || '' : ''),
    zoneId: zoneId || '',
    zoneName: notificationZoneLabel(n, zoneNames) || 'Không có thông tin khu vực',
    timestamp: n.created_at || null,
    readAt: n.read_at || null,
    time: n.created_at ? formatRelativeTime(n.created_at) : '--',
    value: d.value !== undefined && d.value !== null ? `${d.value}${d.unit || ''}` : null,
    threshold: d.threshold !== undefined && d.threshold !== null ? `${d.threshold}${d.unit || ''}` : null,
    confidence: confidencePercent(d),
  }
}
