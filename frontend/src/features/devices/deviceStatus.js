/**
 * INT01-R1: one device-status vocabulary for Owner / Technician / Admin views.
 *
 *   ONLINE      – IoT presence ONLINE (heartbeat within window)
 *   WARNING     – reported degraded
 *   OFFLINE     – confirmed offline (LWT / stale heartbeat)
 *   UNKNOWN     – IoT reachable but the device never reported (no heartbeat yet)
 *   UNAVAILABLE – IoT presence could not be obtained at all (service down / auth error)
 *
 * Nothing here ever invents RSSI, IP or a "last seen" time.
 */
export const DEVICE_STATUS_META = {
  ONLINE: { label: 'Trực tuyến', className: 'online' },
  WARNING: { label: 'Cần chú ý', className: 'warning' },
  OFFLINE: { label: 'Ngoại tuyến', className: 'offline' },
  UNKNOWN: { label: 'Chưa có heartbeat', className: 'unknown' },
  UNAVAILABLE: { label: 'Không xác định (IoT không khả dụng)', className: 'unavailable' },
}

export function resolveDeviceStatus(raw) {
  if (!raw) return 'UNKNOWN'
  if (raw.iot_available === false || raw.iotAvailable === false) return 'UNAVAILABLE'
  const s = String(raw.presence_status || raw.status || '').toUpperCase()
  if (['ONLINE', 'ACTIVE', 'HEALTHY'].includes(s)) return 'ONLINE'
  if (['WARNING', 'DEGRADED'].includes(s)) return 'WARNING'
  if (['OFFLINE', 'STALE'].includes(s)) return 'OFFLINE'
  if (s === 'UNAVAILABLE') return 'UNAVAILABLE'
  return 'UNKNOWN'
}

export function deviceStatusMeta(status) {
  return DEVICE_STATUS_META[status] || DEVICE_STATUS_META.UNKNOWN
}

/** RSSI only from a real source value; null -> null (UI renders "--"). */
export function realNumberOrNull(value) {
  if (value === null || value === undefined || value === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}
