import { useCallback, useEffect, useState } from 'react'
import { techniciansApi } from '../../../api/modules/techniciansApi.js'
import { farmsApi } from '../../../api/modules/farmsApi.js'
import { alertsApi } from '../../../api/modules/alertsApi.js'
import { telemetryApi } from '../../../api/modules/telemetryApi.js'
import { USE_MOCK } from '../../../api/config.js'
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
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchTechData = useCallback(
    async (signal) => {
      try {
        setLoading(true)
        setError(null)

        if (USE_MOCK || !technicianId) {
          const mockDash = getMockTechDashboard()
          setDashboardRaw(mockDash)
          const mockFarms = getMockTechFarms()
          setFarms(mockFarms)
          if (mockFarms.length > 0) {
            setSelectedFarmId((prev) => prev || mockFarms[0].id)
          }
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
    if (!selectedFarmId || !technicianId || USE_MOCK) {
      if (USE_MOCK) {
        const mockFarms = getMockTechFarms()
        const currentFarm = mockFarms.find((f) => f.id === selectedFarmId) || mockFarms[0]
        setZones(currentFarm?.zones || [])
      }
      return
    }

    let isMounted = true
    const controller = new AbortController()

    async function loadFarmContext() {
      try {
        // Parallel queries scoped to the assigned farm
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
        } else {
          setAlerts([])
        }

        // Telemetry
        if (telemResp.status === 'fulfilled') {
          setTelemetry(normalizeTelemetry(telemResp.value, false))
        } else {
          setTelemetry(null)
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
  }, [selectedFarmId, technicianId, farms])

  useEffect(() => {
    const controller = new AbortController()
    fetchTechData(controller.signal)

    return () => {
      controller.abort()
    }
  }, [fetchTechData])

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
    loading,
    error,
    refetch: () => fetchTechData(),
    acknowledgeAlert,
    resolveAlert,
  }
}

export default useTechnicianData
