/**
 * INT01-R1 data provenance & freshness helpers.
 *
 * Labels come from IoT Service `metricSources` (server-derived):
 *   PHYSICAL    – firmware declared a real sensor reading
 *   SIMULATED   – ESP32 simulator / mock sensor module
 *   UNAVAILABLE – no sensor or no value (rendered as "--", never a default number)
 *   UNVERIFIED  – value exists but its origin was not declared (never shown as physical)
 */

export const SOURCE_META = {
  PHYSICAL: { label: 'Cảm biến thật', short: 'Thật', className: 'physical' },
  SIMULATED: { label: 'Mô phỏng', short: 'Mô phỏng', className: 'simulated' },
  UNAVAILABLE: { label: 'Không có cảm biến', short: 'Không khả dụng', className: 'unavailable' },
  UNVERIFIED: { label: 'Chưa xác minh nguồn', short: 'Chưa xác minh', className: 'unverified' },
}

/** Frontend metric key -> IoT metricSources key */
export const METRIC_SOURCE_KEY = {
  temperature: 'temperature',
  humidity: 'humidity',
  co2: 'co2',
  light: 'lux',
  lux: 'lux',
  audio: 'audio',
  rssi: 'networkRssi',
  networkRssi: 'networkRssi',
}

export function metricSource(telemetry, metricKey) {
  if (!telemetry) return 'UNAVAILABLE'
  const key = METRIC_SOURCE_KEY[metricKey] || metricKey
  const declared = telemetry.sources?.[key]
  if (declared && SOURCE_META[declared]) return declared
  const value = metricKey === 'light' ? telemetry.light : telemetry[metricKey]
  return value == null ? 'UNAVAILABLE' : 'UNVERIFIED'
}

export function sourceLabel(source) {
  return SOURCE_META[source]?.label || SOURCE_META.UNVERIFIED.label
}

/** True when any displayed metric is simulated. */
export function isSimulatedTelemetry(telemetry) {
  if (!telemetry) return false
  if (telemetry.provenanceSource === 'SIMULATED' || telemetry.provenanceSource === 'MIXED') return true
  return Object.values(telemetry.sources || {}).includes('SIMULATED')
}

/** Overall source badge for a telemetry snapshot. */
export function overallSource(telemetry) {
  if (!telemetry) return 'UNAVAILABLE'
  const values = Object.entries(telemetry.sources || {})
    .filter(([key]) => key !== 'networkRssi')
    .map(([, v]) => v)
    .filter((v) => v !== 'UNAVAILABLE')
  if (values.length === 0) return 'UNAVAILABLE'
  if (values.every((v) => v === 'PHYSICAL')) return 'PHYSICAL'
  if (values.includes('SIMULATED')) return 'SIMULATED'
  return 'UNVERIFIED'
}

export const TELEMETRY_STALE_AFTER_MS = 15000

/** Relative Vietnamese time from an ISO timestamp; null/invalid -> '--' (never "Vừa xong" by default). */
export function formatRelativeTime(iso, now = Date.now()) {
  if (!iso) return '--'
  const t = new Date(iso).getTime()
  if (!Number.isFinite(t)) return '--'
  const diff = Math.max(0, Math.round((now - t) / 1000))
  if (diff < 5) return 'vài giây trước'
  if (diff < 60) return `${diff} giây trước`
  if (diff < 3600) return `${Math.floor(diff / 60)} phút trước`
  if (diff < 86400) return `${Math.floor(diff / 3600)} giờ trước`
  return new Date(t).toLocaleString('vi-VN')
}
