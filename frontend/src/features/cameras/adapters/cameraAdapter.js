import {
  cameras as mockCamerasList,
  aiEvents,
  birdStats,
  trendData,
} from '../../../components/features/farm-owner/swiftlets/swiftletsMockData.js'

/**
 * Normalizes camera device / camera entity
 * @param {any} raw
 * @param {boolean} [isMockMode=false]
 * @returns {any}
 */
export function normalizeCamera(raw, isMockMode = false) {
  if (!raw) return null

  const id = raw.id || raw.device_id || raw.camera_id || 'CAM-01'
  const code = raw.code || raw.device_code || id
  const name = raw.name || raw.device_name || raw.camera_name || code
  const rawStatus = String(raw.status || 'OFFLINE').toUpperCase()
  const isOnline = ['ONLINE', 'ACTIVE', 'HEALTHY'].includes(rawStatus)

  return {
    id,
    code,
    name,
    node: raw.node || code,
    farmId: raw.farmId || raw.farm_id || '',
    zoneId: raw.zoneId || raw.zone_id || '',
    status: isOnline ? 'ONLINE' : 'OFFLINE',
    resolution: raw.resolution || '1080p',
    fps: Number(raw.fps || 25),
    lastBirdCount: raw.lastBirdCount ?? raw.bird_count ?? (isMockMode ? 428 : 0),
    detections: Array.isArray(raw.detections)
      ? raw.detections
      : isMockMode
        ? [
            { id: 'det-1', label: 'Chim yến bay vào', confidence: 94 },
            { id: 'det-2', label: 'Chim yến lượn', confidence: 88 },
          ]
        : [],
  }
}

export function getMockCameras() {
  return mockCamerasList
}

export function getMockBirdStats() {
  return birdStats
}

export function getMockAiEvents() {
  return aiEvents
}

export function getMockTrendData() {
  return trendData
}
