import { farmsMockData } from '../../../components/features/farm-owner/farms/farmsMockData.js'

/**
 * Normalizes backend farm zone entity
 * @param {any} raw
 * @returns {any}
 */
export function normalizeZone(raw) {
  if (!raw) return null
  return {
    id: raw.id || raw.zone_id || 'unknown-zone',
    code: raw.zone_code || raw.code || '--',
    name: raw.name || raw.zone_name || 'Khu vực',
    farmId: raw.farmId || raw.farm_id || '',
    type: raw.type || raw.zone_type || 'FLOOR',
    floorNumber: raw.floorNumber ?? raw.floor_number ?? 1,
  }
}

/**
 * Normalizes backend farm entity to frontend view model
 * @param {any} raw
 * @param {boolean} [isMockMode=false]
 * @returns {any}
 */
export function normalizeFarm(raw, isMockMode = false) {
  if (!raw) return null

  const tempVal = raw.temperature ?? raw.avg_temperature
  const humVal = raw.humidity ?? raw.avg_humidity
  const birdVal = raw.birdsToday ?? raw.bird_count
  const onlineDevVal = raw.onlineDevices ?? raw.online_devices
  const totalDevVal = raw.totalDevices ?? raw.device_count ?? raw.total_devices

  const rawZones = Array.isArray(raw.zones) ? raw.zones.map(normalizeZone) : []

  return {
    id: raw.id || raw.farm_id || 'unknown-farm',
    name: raw.name || raw.farm_name || raw.farmName || 'Nhà yến chưa đặt tên',
    code: raw.code || raw.farm_code || `NM-${String(raw.id || raw.farm_id || '').slice(0, 4)}`.toUpperCase(),
    address: raw.address || raw.location || 'Chưa cập nhật địa chỉ',
    status: raw.status || 'ACTIVE',
    approvalStatus: raw.approval_status || 'APPROVED',
    rejectionReason: raw.rejection_reason || null,
    health: raw.health || (raw.status === 'ACTIVE' ? 'Tốt' : 'Cần kiểm tra'),
    temperature: tempVal != null ? Number(tempVal) : isMockMode ? 28.5 : null,
    humidity: humVal != null ? Number(humVal) : isMockMode ? 80 : null,
    birdsToday: birdVal != null ? Number(birdVal) : isMockMode ? 428 : null,
    onlineDevices: onlineDevVal != null ? Number(onlineDevVal) : isMockMode ? 10 : null,
    totalDevices: totalDevVal != null ? Number(totalDevVal) : 0,
    zoneCount: Number(raw.zone_count ?? rawZones.length),
    assignedTechnician: raw.assignedTechnician || {
      name: raw.technician_name || (isMockMode ? 'Nguyễn Minh Khang' : 'Chưa phân công'),
      phone: raw.technician_phone || (isMockMode ? '090 345 6789' : '---'),
      status: raw.technician_name ? 'Đang phụ trách' : isMockMode ? 'Đang phụ trách' : 'Chưa phân công',
    },
    zones: rawZones,
  }
}

export function formatFarmOptionLabel(farm) {
  if (!farm) return ''
  const name = farm.name || farm.farm_name || 'Nhà yến'
  const code = farm.code || farm.farm_code
  return code && code !== '--' ? `${name} (${code})` : name
}

/**
 * Returns mock farms list for local mock simulation
 */
export function getMockFarms() {
  return farmsMockData
}
