import { alerts as ownerAlertsMock } from '../../../components/features/farm-owner/alerts/alertsMockData.js'

/**
 * Normalizes alert entity from API or mock
 * @param {any} raw
 * @returns {any}
 */
export function normalizeAlert(raw) {
  if (!raw) return null

  const rawSeverity = String(raw.severity || 'INFO').toUpperCase()
  const severity = ['CRITICAL', 'DANGER'].includes(rawSeverity)
    ? 'CRITICAL'
    : ['WARNING', 'WARN'].includes(rawSeverity)
      ? 'WARNING'
      : 'INFO'

  return {
    id: raw.id || raw.alert_id || 'ALT-0000',
    severity,
    status: raw.status || (raw.acknowledged ? 'ACKNOWLEDGED' : 'OPEN'),
    source: raw.source || raw.alert_type || 'System',
    type: raw.type || 'ENVIRONMENT',
    title: raw.title || raw.message || 'Cảnh báo hệ thống',
    description: raw.description || raw.detail || '',
    farmId: raw.farmId || raw.farm_id || '',
    farmName: raw.farmName || raw.farm_name || '',
    zoneId: raw.zoneId || raw.zone_id || '',
    zoneName: raw.zoneName || raw.zone_name || '',
    timestamp: raw.timestamp || raw.created_at || 'Vừa xong',
    timeAgo: raw.timeAgo || raw.time || 'Vừa xong',
  }
}

export function getMockAlerts() {
  return ownerAlertsMock.map(normalizeAlert)
}
