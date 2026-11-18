import { useCallback, useEffect, useState } from 'react'
import { devicesApi } from '../../../api/modules/devicesApi.js'
import { camerasApi } from '../../../api/modules/camerasApi.js'
import { analyticsApi } from '../../../api/modules/analyticsApi.js'
import { USE_MOCK } from '../../../api/config.js'
import {
  getMockCameras,
  getMockBirdStats,
  getMockAiEvents,
  normalizeCamera,
} from '../adapters/cameraAdapter.js'

export function useCameras(farmId = null, cameraId = null) {
  const [cameras, setCameras] = useState(() => (USE_MOCK ? getMockCameras() : []))
  const [birdStats, setBirdStats] = useState(() => (USE_MOCK ? getMockBirdStats() : null))
  const [events, setEvents] = useState(() => (USE_MOCK ? getMockAiEvents() : []))
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchCameras = useCallback(async (signal) => {
    try {
      setLoading(true)
      setError(null)

      if (USE_MOCK) {
        const mockList = getMockCameras()
        const filtered = farmId ? mockList.filter((c) => !c.farmId || c.farmId === farmId) : mockList
        setCameras(filtered)
        setBirdStats(getMockBirdStats())
        setEvents(getMockAiEvents())
        return
      }

      // Real Mode: Query devices of type CAMERA for the farm
      const devParams = farmId ? { farm_id: farmId } : {}
      const devResponse = await devicesApi.getDevices({ params: devParams, signal })
      const rawDevices = Array.isArray(devResponse)
        ? devResponse
        : devResponse?.items || devResponse?.data || []

      const cameraDevices = rawDevices
        .filter((d) => String(d.device_type || d.type || '').toUpperCase() === 'CAMERA')
        .map((c) => normalizeCamera(c, false))

      setCameras(cameraDevices)

      // In real mode, load live bird performance from Analytics if farmId is provided
      if (farmId) {
        try {
          const summary = await analyticsApi.getFarmSummary(farmId, { signal })
          if (summary?.birdPerformance) {
            setBirdStats({
              totalCount: summary.birdPerformance.entries ?? 0,
              entries: summary.birdPerformance.entries ?? 0,
              exits: summary.birdPerformance.exits ?? 0,
              activeNests: summary.yieldSummary?.activeNests ?? 0,
              change: summary.birdPerformance.change ?? 0,
            })
          }
        } catch {
          // Analytics may be empty or gap
        }
      }

      // Check status of individual camera if requested
      if (cameraId) {
        try {
          const statusResp = await camerasApi.getCameraStatus(cameraId, { signal })
          if (statusResp) {
            setCameras((prev) =>
              prev.map((c) => (c.id === cameraId ? { ...c, ...statusResp } : c)),
            )
          }
        } catch {
          // Offline camera returns 404
        }
      }
    } catch (err) {
      if (err?.code !== 'ABORTED') {
        setError(err?.message || 'Không thể tải thông tin camera AI.')
      }
    } finally {
      setLoading(false)
    }
  }, [farmId, cameraId])

  useEffect(() => {
    const controller = new AbortController()
    fetchCameras(controller.signal)

    return () => {
      controller.abort()
    }
  }, [fetchCameras])

  return {
    cameras,
    birdStats,
    events,
    loading,
    error,
    refetch: () => fetchCameras(),
  }
}

export default useCameras
