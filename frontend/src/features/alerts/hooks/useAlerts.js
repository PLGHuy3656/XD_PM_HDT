import { useCallback, useEffect, useState } from 'react'
import { alertsApi } from '../../../api/modules/alertsApi.js'
import { USE_MOCK } from '../../../api/config.js'
import {
  SERVICE_STATE,
  classifyServiceError,
  useRevalidateOnFocus,
} from '../../../api/serviceStatus.js'
import { getMockAlerts, normalizeAlert } from '../adapters/alertAdapter.js'

export function useAlerts(farmId = null, filterSeverity = 'ALL') {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [serviceState, setServiceState] = useState(
    USE_MOCK ? SERVICE_STATE.AVAILABLE : SERVICE_STATE.LOADING,
  )

  const fetchAlerts = useCallback(async (signal) => {
    try {
      setLoading(true)
      setError(null)

      if (USE_MOCK) {
        const mockList = getMockAlerts()
        const filtered = farmId ? mockList.filter((a) => !a.farmId || a.farmId === farmId) : mockList
        setAlerts(filtered)
        setServiceState(filtered.length > 0 ? SERVICE_STATE.AVAILABLE : SERVICE_STATE.EMPTY)
        return
      }

      if (!farmId) {
        setAlerts([])
        setServiceState(SERVICE_STATE.UNKNOWN)
        setLoading(false)
        return
      }
      setAlerts([])
      setServiceState(SERVICE_STATE.LOADING)

      const response = await alertsApi.getAlerts({
        params: { farmId },
        signal,
      })
      const rawList = Array.isArray(response) ? response : response?.items || response?.data || []
      const normalized = rawList.map(normalizeAlert)
      setAlerts(normalized)
      setError(null)
      setServiceState(normalized.length > 0 ? SERVICE_STATE.AVAILABLE : SERVICE_STATE.EMPTY)
    } catch (err) {
      if (err?.code !== 'ABORTED') {
        if (err?.status === 403 || err?.status === 404) {
          setAlerts([])
          setError(null)
          setServiceState(SERVICE_STATE.EMPTY)
        } else {
          setServiceState(classifyServiceError(err) || SERVICE_STATE.ERROR)
          setError(err?.message || 'Không thể tải danh sách cảnh báo.')
        }
      }
    } finally {
      setLoading(false)
    }
  }, [farmId])

  useEffect(() => {
    const controller = new AbortController()
    queueMicrotask(() => {
      if (!controller.signal.aborted) {
        fetchAlerts(controller.signal)
      }
    })

    return () => {
      controller.abort()
    }
  }, [fetchAlerts])

  useRevalidateOnFocus(
    useCallback(() => {
      fetchAlerts()
    }, [fetchAlerts]),
    { enabled: !USE_MOCK && Boolean(farmId) },
  )

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
    serviceState,
    refetch: () => fetchAlerts(),
    acknowledgeAlert,
    resolveAlert,
  }
}

export default useAlerts
