import { useCallback, useEffect, useState } from 'react'
import { devicesApi } from '../../../api/modules/devicesApi.js'
import { USE_MOCK } from '../../../api/config.js'
import {
  getMockCameras,
  getMockBirdStats,
  getMockAiEvents,
  normalizeCamera,
} from '../adapters/cameraAdapter.js'

// eslint-disable-next-line no-unused-vars -- cameraId kept for call-site compatibility
export function useCameras(farmId = null, cameraId = null, { requireFarmId = false } = {}) {
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

      if (requireFarmId && !farmId) {
        setCameras([])
        setBirdStats(null)
        setEvents([])
        return
      }
      setCameras([])
      setBirdStats(null)
      setEvents([])

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

      // INT02: bird counts / runtime status come from the AI Service per camera
      // (useCameraAiRuntime via the Gateway) - not from Analytics, which is not deployed yet.
    } catch (err) {
      if (err?.code !== 'ABORTED') {
        setError(err?.message || 'Không thể tải thông tin camera AI.')
      }
    } finally {
      setLoading(false)
    }
  }, [farmId, requireFarmId])

  useEffect(() => {
    const controller = new AbortController()
    const first = setTimeout(() => fetchCameras(controller.signal), 0)

    return () => {
      clearTimeout(first)
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
