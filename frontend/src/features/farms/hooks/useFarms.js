import { useCallback, useEffect, useState } from 'react'
import { farmsApi } from '../../../api/modules/farmsApi.js'
import { USE_MOCK } from '../../../api/config.js'
import { getMockFarms, normalizeFarm, normalizeZone } from '../adapters/farmAdapter.js'

export function useFarms() {
  const [farms, setFarms] = useState([])
  const [selectedFarmId, setSelectedFarmId] = useState(null)
  const [zones, setZones] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchFarms = useCallback(async (signal) => {
    try {
      setLoading(true)
      setError(null)

      if (USE_MOCK) {
        const mockList = getMockFarms()
        setFarms(mockList)
        setSelectedFarmId((prev) => prev || (mockList.length > 0 ? mockList[0].id : null))
        if (mockList.length > 0) {
          const first = mockList[0]
          setZones(first.zones || [])
        }
        return
      }

      // Real Gateway API mode
      const response = await farmsApi.getFarms({ signal })
      const rawList = Array.isArray(response) ? response : response?.items || response?.data || []
      const normalized = rawList.map((f) => normalizeFarm(f, false))

      setFarms(normalized)
      setSelectedFarmId((prev) => {
        if (prev && normalized.some((f) => f.id === prev)) {
          return prev
        }
        return normalized.length > 0 ? normalized[0].id : null
      })
    } catch (err) {
      if (err?.code !== 'ABORTED') {
        setError(err?.message || 'Không thể tải danh sách nhà yến.')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  // Fetch zones when selectedFarmId changes in real mode
  useEffect(() => {
    if (!selectedFarmId) {
      setZones([])
      return
    }

    if (USE_MOCK) {
      const current = farms.find((f) => f.id === selectedFarmId)
      setZones(current?.zones || [])
      return
    }

    let isMounted = true
    const controller = new AbortController()

    async function loadZones() {
      try {
        const resp = await farmsApi.getFarmZones(selectedFarmId, { signal: controller.signal })
        const rawZones = Array.isArray(resp) ? resp : resp?.items || resp?.data || []
        if (isMounted) {
          setZones(rawZones.map(normalizeZone))
        }
      } catch (err) {
        if (err?.code !== 'ABORTED' && isMounted) {
          // If zones fail, fallback to empty array
          setZones([])
        }
      }
    }

    loadZones()

    return () => {
      isMounted = false
      controller.abort()
    }
  }, [selectedFarmId, farms])

  useEffect(() => {
    const controller = new AbortController()
    fetchFarms(controller.signal)

    return () => {
      controller.abort()
    }
  }, [fetchFarms])

  const selectedFarm = farms.find((f) => f.id === selectedFarmId) || farms[0] || null

  const selectedFarmWithZones = selectedFarm
    ? {
        ...selectedFarm,
        zones: zones.length > 0 ? zones : selectedFarm.zones || [],
      }
    : null

  const runFarmMutation = useCallback(
    async (fn, fallbackError) => {
      try {
        await fn()
        await fetchFarms()
        return { success: true }
      } catch (err) {
        return { success: false, error: err?.message || fallbackError }
      }
    },
    [fetchFarms]
  )

  const createFarm = useCallback(
    (payload) => runFarmMutation(() => farmsApi.createFarm(payload), 'Tạo nhà yến thất bại'),
    [runFarmMutation]
  )

  const updateFarm = useCallback(
    (farmId, payload) => runFarmMutation(() => farmsApi.updateFarm(farmId, payload), 'Cập nhật nhà yến thất bại'),
    [runFarmMutation]
  )

  const createZone = useCallback(
    (farmId, payload) => runFarmMutation(() => farmsApi.createZone(farmId, payload), 'Tạo khu vực thất bại'),
    [runFarmMutation]
  )

  const updateZone = useCallback(
    (zoneId, payload) => runFarmMutation(() => farmsApi.updateZone(zoneId, payload), 'Cập nhật khu vực thất bại'),
    [runFarmMutation]
  )

  const deleteZone = useCallback(
    (zoneId) => runFarmMutation(() => farmsApi.deleteZone(zoneId), 'Xóa khu vực thất bại'),
    [runFarmMutation]
  )

  return {
    farms,
    selectedFarm: selectedFarmWithZones,
    selectedFarmId,
    setSelectedFarmId,
    zones,
    loading,
    error,
    createFarm,
    updateFarm,
    createZone,
    updateZone,
    deleteZone,
    refetch: () => fetchFarms(),
  }
}

export default useFarms
