import { useCallback, useEffect, useState } from 'react'
import { alertsApi } from '../../../api/modules/alertsApi.js'
import { USE_MOCK } from '../../../api/config.js'
import {
  SERVICE_STATE,
  classifyServiceError,
  useRevalidateOnFocus,
} from '../../../api/serviceStatus.js'
import { getMockAlerts } from '../adapters/alertAdapter.js'
import { useAuth } from '../../../context/AuthContext'
import { useNotifications } from '../../notifications/useNotifications.js'
import { isOperationalAlert, notificationFarmId, toAlertRow } from '../../notifications/notificationAdapter.js'

/**
 * INT03: in real mode alerts ARE the caller's notifications (Notification Service, server-scoped
 * recipients) for the selected farm. The current contract supports read/unread only:
 * "acknowledge" = mark read; "resolve" does not exist yet and is reported as such.
 */
export function useAlerts(farmId = null, filterSeverity = 'ALL') {
  const { user } = useAuth()
  const live = useNotifications(USE_MOCK ? null : user?.id || user?.user_id || user?.sub || null)
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [serviceState, setServiceState] = useState(
    USE_MOCK ? SERVICE_STATE.AVAILABLE : SERVICE_STATE.LOADING,
  )

  const fetchAlerts = useCallback(async () => {
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

      // Real mode is driven by useNotifications below (no call to the non-existent /api/v1/alerts)
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
      if (USE_MOCK && !controller.signal.aborted) {
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
    { enabled: false },
  )

  const acknowledgeAlert = async (alertId, note = '') => {
    if (!USE_MOCK) return live.markRead(alertId)
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
    if (!USE_MOCK) {
      return { success: false, message: 'Contract Notification hiện hành chỉ hỗ trợ đã đọc/chưa đọc — chưa có trạng thái "đã xử lý".' }
    }
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

  const realAlerts = USE_MOCK
    ? null
    : farmId
      ? live.items.filter((n) => notificationFarmId(n) === farmId && isOperationalAlert(n)).map((n) => toAlertRow(n))
      : []
  const effectiveAlerts = USE_MOCK ? alerts : realAlerts
  const filteredAlerts =
    filterSeverity === 'ALL'
      ? effectiveAlerts
      : effectiveAlerts.filter((a) => a.severity.toUpperCase() === filterSeverity.toUpperCase())

  const realState = live.state === 'UNAVAILABLE'
    ? SERVICE_STATE.UNAVAILABLE
    : live.state === 'ERROR'
      ? SERVICE_STATE.ERROR
      : live.state === 'LOADING'
        ? SERVICE_STATE.LOADING
        : realAlerts && realAlerts.length
          ? SERVICE_STATE.AVAILABLE
          : SERVICE_STATE.EMPTY

  return {
    alerts: filteredAlerts,
    allAlerts: effectiveAlerts,
    loading: USE_MOCK ? loading : live.state === 'LOADING',
    error: USE_MOCK ? error : live.state === 'UNAVAILABLE' || live.state === 'ERROR' ? live.error || 'Notification Service unavailable' : null,
    serviceState: USE_MOCK ? serviceState : realState,
    refetch: () => (USE_MOCK ? fetchAlerts() : live.refresh()),
    acknowledgeAlert,
    resolveAlert,
  }
}

export default useAlerts
