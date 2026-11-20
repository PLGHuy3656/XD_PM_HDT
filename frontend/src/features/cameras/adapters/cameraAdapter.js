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

  // INT02: the AI Service and Gateway identify cameras by Management node_id (e.g. CAM-01)
  const id = isMockMode
    ? raw.id || raw.device_id || raw.camera_id || 'CAM-01'
    : raw.node_id || raw.code || raw.camera_id || raw.id || raw.device_id
  const code = raw.node_id || raw.code || raw.device_code || id
  const name = raw.name || raw.device_name || raw.camera_name || code
  const rawStatus = String(raw.status || 'OFFLINE').toUpperCase()
  const isOnline = ['ONLINE', 'ACTIVE', 'HEALTHY'].includes(rawStatus)

  return {
    id,
    deviceId: raw.device_id || raw.id || null,
    code,
    name,
    node: raw.node || code,
    farmId: raw.farmId || raw.farm_id || '',
    zoneId: raw.zoneId || raw.zone_id || '',
    zoneName: raw.zoneName || raw.zone_name || '',
    // Real mode: camera runtime status comes from the AI Service, not from MQTT presence
    status: isMockMode ? (isOnline ? 'ONLINE' : 'OFFLINE') : 'UNKNOWN',
    resolution: isMockMode ? raw.resolution || '1080p' : null,
    fps: isMockMode ? Number(raw.fps || 25) : null,
    lastBirdCount: raw.lastBirdCount ?? raw.bird_count ?? (isMockMode ? 428 : null),
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
