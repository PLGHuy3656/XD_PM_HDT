import { useCallback, useEffect, useState } from 'react'
import { techniciansApi } from '../../../api/modules/techniciansApi.js'
import { farmsApi } from '../../../api/modules/farmsApi.js'
import { devicesApi } from '../../../api/modules/devicesApi.js'
import { alertsApi } from '../../../api/modules/alertsApi.js'
import { telemetryApi } from '../../../api/modules/telemetryApi.js'
import { USE_MOCK } from '../../../api/config.js'
import { useRevalidateOnFocus } from '../../../api/serviceStatus.js'
import { useAuth } from '../../../context/AuthContext.jsx'
import {
  getMockTechDashboard,
  getMockTechFarms,
  normalizeAssignedFarm,
  normalizeTechDevice,
  normalizeTechStats,
  normalizeTechAlert,
} from '../adapters/technicianAdapter.js'
import { normalizeZone } from '../../farms/adapters/farmAdapter.js'
import { normalizeTelemetry } from '../../telemetry/adapters/telemetryAdapter.js'

export function useTechnicianData(overrideTechId = null) {
  const { user } = useAuth()
  const technicianId = overrideTechId || user?.id || null

  const [dashboardRaw, setDashboardRaw] = useState(null)
  const [farms, setFarms] = useState([])
  const [selectedFarmId, setSelectedFarmId] = useState(null)
  const [devices, setDevices] = useState([])
  const [zones, setZones] = useState([])
  const [alerts, setAlerts] = useState([])
  const [telemetry, setTelemetry] = useState(null)
  const [alertsError, setAlertsError] = useState(null)
  const [telemetryError, setTelemetryError] = useState(null)
  const [contextNonce, setContextNonce] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchTechData = useCallback(
    async (signal) => {
      try {
        setLoading(true)
        setError(null)

        if (USE_MOCK) {
          const mockDash = getMockTechDashboard()
          setDashboardRaw(mockDash)
          const mockFarms = getMockTechFarms()
          setFarms(mockFarms)
          if (mockFarms.length > 0) {
            setSelectedFarmId((prev) => prev || mockFarms[0].id)
          }
          return
        }

        if (!technicianId) {
          setDashboardRaw(null)
          setFarms([])
          setSelectedFarmId(null)
          return
        }

        // 1. Fetch dashboard stats and assigned farms in parallel
        const [dashResp, farmsResp] = await Promise.all([
          techniciansApi.getDashboard(technicianId, { signal }),
          techniciansApi.getFarms(technicianId, { signal }),
        ])

        setDashboardRaw(dashResp)

        const rawFarmList = Array.isArray(farmsResp)
          ? farmsResp
          : farmsResp?.items || farmsResp?.data || []
        const normalizedFarms = rawFarmList.map((f) => normalizeAssignedFarm(f, false))
        setFarms(normalizedFarms)

        setSelectedFarmId((prev) => {
          if (prev && normalizedFarms.some((f) => f.id === prev)) {
            return prev
          }
          return normalizedFarms.length > 0 ? normalizedFarms[0].id : null
        })
      } catch (err) {
        if (err?.code !== 'ABORTED') {
          setError(err?.message || 'Không thể tải dữ liệu kỹ thuật viên.')
        }
      } finally {
        setLoading(false)
      }
    },
    [technicianId],
  )

  // 2. Cascade device, zone, alert, and telemetry loading when selectedFarmId changes
  useEffect(() => {
    if (USE_MOCK) {
      const mockFarms = getMockTechFarms()
      const currentFarm = mockFarms.find((f) => f.id === selectedFarmId) || mockFarms[0]
      setZones(currentFarm?.zones || [])
      return
    }

    // Immediately clear stale state from previous farm
    setDevices([])
    setZones([])
    setAlerts([])
    setTelemetry(null)
    setAlertsError(null)
    setTelemetryError(null)

    if (!selectedFarmId || !technicianId) {
      return
    }

    let isMounted = true
    const controller = new AbortController()

    async function loadFarmContext() {
      try {
        const activeFarm = farms.find((f) => f.id === selectedFarmId)
        const farmName = activeFarm?.name || 'Nhà yến'

        const [devResp, zonesResp, alertsResp, telemResp] = await Promise.allSettled([
          techniciansApi.getFarmDevices(technicianId, selectedFarmId, {
            signal: controller.signal,
          }),
          farmsApi.getFarmZones(selectedFarmId, { signal: controller.signal }),
          alertsApi.getAlerts({
            params: { farmId: selectedFarmId },
            signal: controller.signal,
          }),
          telemetryApi.getFarmLatest(selectedFarmId, { signal: controller.signal }),
        ])

        if (!isMounted) return

        // Devices
        if (devResp.status === 'fulfilled') {
          const rawDevs = Array.isArray(devResp.value)
            ? devResp.value
            : devResp.value?.items || devResp.value?.data || []
          setDevices(rawDevs.map((d) => normalizeTechDevice(d, farmName)))
        } else {
          setDevices([])
        }

        // Zones
        if (zonesResp.status === 'fulfilled') {
          const rawZones = Array.isArray(zonesResp.value)
            ? zonesResp.value
            : zonesResp.value?.items || zonesResp.value?.data || []
          setZones(rawZones.map(normalizeZone))
        } else {
          setZones([])
        }

        // Alerts
        if (alertsResp.status === 'fulfilled') {
          const rawAlerts = Array.isArray(alertsResp.value)
            ? alertsResp.value
            : alertsResp.value?.items || alertsResp.value?.data || []
          setAlerts(rawAlerts.map(normalizeTechAlert))
          setAlertsError(null)
        } else {
          setAlerts([])
          const reason = alertsResp.reason
          if (reason?.code !== 'ABORTED') {
            setAlertsError(reason?.message || 'Dịch vụ Cảnh báo chưa khả dụng.')
          }
        }

        // Telemetry
        if (telemResp.status === 'fulfilled') {
          setTelemetry(normalizeTelemetry(telemResp.value, false))
          setTelemetryError(null)
        } else {
          setTelemetry(null)
          const reason = telemResp.reason
          if (reason?.code !== 'ABORTED' && reason?.status !== 404 && reason?.statusCode !== 404) {
            setTelemetryError(reason?.message || 'Dịch vụ IoT chưa khả dụng.')
          }
        }
      } catch {
        // Ignore aborts
      }
    }

    loadFarmContext()

    return () => {
      isMounted = false
      controller.abort()
    }
  }, [selectedFarmId, technicianId, farms, contextNonce])

  useEffect(() => {
    const controller = new AbortController()
    fetchTechData(controller.signal)

    return () => {
      controller.abort()
    }
  }, [fetchTechData])

  useRevalidateOnFocus(
    useCallback(() => {
      setContextNonce((n) => n + 1)
    }, []),
    { enabled: !USE_MOCK && Boolean(selectedFarmId) },
  )

  const acknowledgeAlert = async (alertId, note = '') => {
    if (USE_MOCK) {
      setAlerts((prev) =>
        prev.map((a) => (a.id === alertId ? { ...a, status: 'INVESTIGATING' } : a)),
      )
      return { success: true }
    }

    try {
      await alertsApi.acknowledge(alertId, { note })
      setAlerts((prev) =>
        prev.map((a) => (a.id === alertId ? { ...a, status: 'INVESTIGATING' } : a)),
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

  const createDevice = useCallback(async (payload) => {
    if (USE_MOCK) {
      return { success: true, data: payload }
    }
    try {
      const created = await devicesApi.createDevice(payload)
      setContextNonce((n) => n + 1)
      return { success: true, data: created }
    } catch (err) {
      return {
        success: false,
        error: err?.message || 'Không thể đăng ký thiết bị mới.',
      }
    }
  }, [])

  const updateDeviceZone = useCallback(async (deviceId, zoneId) => {
    if (USE_MOCK) {
      setDevices((prev) =>
        prev.map((d) => (d.id === deviceId ? { ...d, zoneId: zoneId || '' } : d)),
      )
      return { success: true }
    }
    try {
      const updated = await devicesApi.updateDeviceZone(deviceId, zoneId || null)
      setContextNonce((n) => n + 1)
      return { success: true, data: updated }
    } catch (err) {
      return {
        success: false,
        error: err?.message || 'Không thể cập nhật phân bổ khu vực cho thiết bị.',
      }
    }
  }, [])

  const selectedFarm = farms.find((f) => f.id === selectedFarmId) || farms[0] || null

  const systemStats = normalizeTechStats(dashboardRaw, USE_MOCK)

  return {
    dashboard: dashboardRaw,
    systemStats,
    farms,
    selectedFarm,
    selectedFarmId,
    setSelectedFarmId,
    devices,
    zones,
    alerts,
    telemetry,
    alertsError,
    telemetryError,
    loading,
    error,
    refetch: () => fetchTechData(),
    createDevice,
    updateDeviceZone,
    acknowledgeAlert,
    resolveAlert,
  }
}

export default useTechnicianData
