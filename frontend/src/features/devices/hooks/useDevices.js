import { useCallback, useEffect, useState } from 'react'
import { devicesApi } from '../../../api/modules/devicesApi.js'
import { USE_MOCK } from '../../../api/config.js'
import { getMockDevices, normalizeDevice } from '../adapters/deviceAdapter.js'

export function useDevices(farmId = null) {
  const [devices, setDevices] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchDevices = useCallback(async (signal) => {
    try {
      setLoading(true)
      setError(null)

      if (USE_MOCK) {
        const mockList = getMockDevices()
        const filtered = farmId ? mockList.filter((d) => d.farmId === farmId) : mockList
        setDevices(filtered)
        return
      }

      // Query real Gateway /api/devices with optional farm_id filter
      const options = {
        signal,
        params: farmId ? { farm_id: farmId } : {},
      }
      const response = await devicesApi.getDevices(options)
      const rawList = Array.isArray(response) ? response : response?.items || response?.data || []
      const normalized = rawList.map(normalizeDevice)
      const filtered = farmId ? normalized.filter((d) => d.farmId === farmId) : normalized
      setDevices(filtered)
    } catch (err) {
      if (err?.code !== 'ABORTED') {
        setError(err?.message || 'Không thể tải danh sách thiết bị.')
      }
    } finally {
      setLoading(false)
    }
  }, [farmId])

  useEffect(() => {
    const controller = new AbortController()
    fetchDevices(controller.signal)

    return () => {
      controller.abort()
    }
  }, [fetchDevices])

  return {
    devices,
    loading,
    error,
    refetch: () => fetchDevices(),
  }
}

export default useDevices
