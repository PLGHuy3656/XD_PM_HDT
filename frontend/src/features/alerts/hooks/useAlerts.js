import { useCallback, useEffect, useState } from 'react'
import { alertsApi } from '../../../api/modules/alertsApi.js'
import { USE_MOCK } from '../../../api/config.js'
import { getMockAlerts, normalizeAlert } from '../adapters/alertAdapter.js'

export function useAlerts(farmId = null, filterSeverity = 'ALL') {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchAlerts = useCallback(async (signal) => {
    try {
      setLoading(true)
      setError(null)

      if (USE_MOCK) {
        const mockList = getMockAlerts()
        const filtered = farmId ? mockList.filter((a) => !a.farmId || a.farmId === farmId) : mockList
        setAlerts(filtered)
        return
      }

      // In real Gateway mode, farmId is mandatory for Farm Owner tenant isolation
      if (!farmId) {
        setAlerts([])
        setLoading(false)
        return
      }

      const response = await alertsApi.getAlerts({
        params: { farmId },
        signal,
      })
      const rawList = Array.isArray(response) ? response : response?.items || response?.data || []
      setAlerts(rawList.map(normalizeAlert))
    } catch (err) {
      if (err?.code !== 'ABORTED') {
        if (err?.status === 403 || err?.status === 404) {
          // Tenant boundary or no alerts
          setAlerts([])
        } else {
          setError(err?.message || 'Không thể tải danh sách cảnh báo.')
        }
      }
    } finally {
      setLoading(false)
    }
  }, [farmId])

  useEffect(() => {
    const controller = new AbortController()
    fetchAlerts(controller.signal)

    return () => {
      controller.abort()
    }
  }, [fetchAlerts])

  const acknowledgeAlert = async (alertId, note = '') => {
    if (USE_MOCK) {
      setAlerts((prev) =>
        prev.map((a) => (a.id === alertId ? { ...a, status: 'ACKNOWLEDGED' } : a)),
      )
      return { success: true }
    }

    try {
      await alertsApi.acknowledge(alertId, { note })
      setAlerts((prev) =>
        prev.map((a) => (a.id === alertId ? { ...a, status: 'ACKNOWLEDGED' } : a)),
      )
      return { success: true }
    } catch (err) {
      return { success: false, message: err?.message || 'Không thể xác nhận cảnh báo.' }
    }
  }

  const resolveAlert = async (alertId, note = '') => {
    if (USE_MOCK) {
      setAlerts((prev) =>
        prev.map((a) => (a.id === alertId ? { ...a, status: 'RESOLVED' } : a)),
      )
      return { success: true }
    }

    try {
      await alertsApi.resolve(alertId, { note })
      setAlerts((prev) =>
        prev.map((a) => (a.id === alertId ? { ...a, status: 'RESOLVED' } : a)),
      )
      return { success: true }
    } catch (err) {
      return { success: false, message: err?.message || 'Không thể đóng cảnh báo.' }
    }
  }

  const filteredAlerts =
    filterSeverity === 'ALL'
      ? alerts
      : alerts.filter((a) => a.severity.toUpperCase() === filterSeverity.toUpperCase())

  return {
    alerts: filteredAlerts,
    allAlerts: alerts,
    loading,
    error,
    refetch: () => fetchAlerts(),
    acknowledgeAlert,
    resolveAlert,
  }
}

export default useAlerts
