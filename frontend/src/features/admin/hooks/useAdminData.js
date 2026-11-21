import { useState, useEffect, useCallback, useMemo } from 'react'
import { useAuth } from '../../../context/AuthContext'
import { farmsApi } from '../../../api/modules/farmsApi'
import { devicesApi } from '../../../api/modules/devicesApi'
import { techniciansApi } from '../../../api/modules/techniciansApi'
import { usersApi } from '../../../api/modules/usersApi'
import { systemApi } from '../../../api/modules/systemApi'
import {
  normalizeAdminDevice,
  normalizeAdminFarm,
  normalizeAdminTechnician,
  normalizeAdminUser,
  normalizeSystemServices,
  normalizeAdminDashboardStats,
} from '../adapters/adminAdapter'

// Mock Data Fallbacks for Mock Mode (VITE_USE_MOCK=true)
import { adminFarms } from '../../../components/features/admin/farms/adminFarmsMockData'
import { getAdminDevices } from '../../../components/features/admin/devices/adminDevicesData'
import { initialAdminUsers } from '../../../components/features/admin/users/usersMockData'
import {
  managementItems as mockManagementItems,
  roles as mockRoles,
  recentAccounts as mockRecentAccounts,
  services as mockServices,
} from '../../../components/features/admin/dashboard/dashboardMockData'

const isMockMode = import.meta.env.VITE_USE_MOCK === 'true'

/**
 * useAdminData Hook
 * Central hook for Administrator screens. Fetches and normalizes live data from
 * Gateway, Management Service, IoT Service, and System Health.
 */
export function useAdminData() {
  const { user: authUser } = useAuth()

  const [farms, setFarms] = useState([])
  const [devices, setDevices] = useState([])
  const [technicians, setTechnicians] = useState([])
  const [users, setUsers] = useState([])
  const [systemHealth, setSystemHealth] = useState([])
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)

    if (isMockMode) {
      setFarms(adminFarms)
      setDevices(getAdminDevices())
      setUsers(initialAdminUsers)
      setTechnicians(
        initialAdminUsers.filter((u) => u.role === 'TECHNICIAN' && u.status === 'ACTIVE')
      )
      setSystemHealth(mockServices)
      setAlerts([])
      setLoading(false)
      return
    }

    try {
      // 1. Parallel fetch top-level resources
      const [rawFarms, rawDevices, rawTechs, healthData, rawAlerts, rawUsers] = await Promise.all([
        farmsApi.getFarms(),
        devicesApi.getDevices(),
        techniciansApi.getTechnicians(),
        systemApi.getStatus().catch(() => null),
        // INT03-R1: /api/v1/alerts does not exist behind the Gateway (default-deny 404). Admin
        // notifications come from the Notification Service (bell / Trung tâm thông báo) instead.
        Promise.resolve([]),
        usersApi.getUsers().catch(() => null),
      ])

      // 2. Fetch farm details and zones in parallel
      const farmDetailsList = await Promise.all(
        (rawFarms || []).map(async (farm) => {
          const farmId = farm.farm_id || farm.id
          try {
            const [detail, zones] = await Promise.all([
              farmsApi.getFarmById(farmId).catch(() => farm),
              farmsApi.getFarmZones(farmId).catch(() => []),
            ])
            return { raw: detail || farm, zones: zones || [] }
          } catch {
            return { raw: farm, zones: [] }
          }
        })
      )

      // 3. Build farms lookup map
      const farmsMap = {}
      farmDetailsList.forEach(({ raw }) => {
        const id = raw.farm_id || raw.id
        farmsMap[id] = raw
      })

      // 4. Normalize devices
      const normalizedDevices = (rawDevices || []).map((d) => normalizeAdminDevice(d, farmsMap))

      // 5. Normalize farms with nested zones and devices
      const normalizedFarms = farmDetailsList.map(({ raw, zones }) =>
        normalizeAdminFarm(raw, zones, normalizedDevices)
      )

      // 6. Normalize technicians
      const normalizedTechs = (rawTechs || []).map(normalizeAdminTechnician)

      // 7. Aggregate known users from authoritative endpoints
      const knownUsers = []

      // 7a. Current admin user
      if (authUser) {
        knownUsers.push(normalizeAdminUser(authUser))
      }

      // 7b. Technicians
      normalizedTechs.forEach((t) => {
        if (!knownUsers.some((u) => u.id === t.id || u.email === t.email)) {
          knownUsers.push(t)
        }
      })

      // 7c. Farm owners from farm details
      farmDetailsList.forEach(({ raw }) => {
        if (raw.owner_name) {
          const ownerId = raw.owner_id || `OWNER-${raw.farm_code || '01'}`
          if (!knownUsers.some((u) => u.name === raw.owner_name)) {
            knownUsers.push({
              id: ownerId,
              name: raw.owner_name,
              email: raw.owner_email || `${raw.owner_name.toLowerCase().replace(/\s+/g, '.')}@nestmate.dev`,
              phone: raw.owner_phone || '--',
              role: 'FARM_OWNER',
              status: 'ACTIVE',
              joinedAt: '01/11/2026',
              lastActive: 'Đang hoạt động',
            })
          }
        }
      })

      // 7d. Use authoritative users from API if available
      let finalUsers = knownUsers
      if (rawUsers && Array.isArray(rawUsers) && rawUsers.length > 0) {
        finalUsers = rawUsers.map((u) => ({
          id: u.id,
          name: u.full_name,
          email: u.email,
          phone: u.phone || '--',
          role: (u.roles && u.roles[0]) || 'FARM_OWNER',
          roles: u.roles || [],
          status: u.status || 'ACTIVE',
          joinedAt: u.created_at ? new Date(u.created_at).toLocaleDateString('vi-VN') : '14/11/2026',
          lastActive: u.status === 'ACTIVE' ? 'Đang hoạt động' : 'Đã khóa',
        }))
      }

      // 8. Normalize system services honestly from Gateway live probes (INT01-R1 /api/system/status)
      const normalizedServices = normalizeSystemServices(healthData)

      setFarms(normalizedFarms)
      setDevices(normalizedDevices)
      setTechnicians(normalizedTechs)
      setUsers(finalUsers)
      setSystemHealth(normalizedServices)
      setAlerts(rawAlerts || [])
    } catch (err) {
      setError(err.message || 'Không thể tải dữ liệu quản trị từ API Gateway')
    } finally {
      setLoading(false)
    }
  }, [authUser])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Computed dashboard stats
  const dashboardStats = useMemo(() => {
    if (isMockMode) {
      return {
        managementItems: mockManagementItems,
        roles: mockRoles,
        recentAccounts: mockRecentAccounts,
        services: mockServices,
      }
    }

    return normalizeAdminDashboardStats({
      farms,
      devices,
      users,
      services: systemHealth,
    })
  }, [farms, devices, users, systemHealth])

  // Action: Assign technician to farm
  const assignTechnician = useCallback(
    async (farmId, technicianId) => {
      if (isMockMode) {
        setFarms((prev) =>
          prev.map((f) => {
            if (f.id === farmId) {
              const tech = technicians.find((t) => t.id === technicianId)
              return {
                ...f,
                technician: tech
                  ? {
                      id: tech.id,
                      name: tech.name,
                      email: tech.email,
                      phone: tech.phone,
                      status: 'ASSIGNED',
                    }
                  : null,
              }
            }
            return f
          })
        )
        return { success: true }
      }

      try {
        await techniciansApi.assignFarm(technicianId, farmId)
        await fetchData()
        return { success: true }
      } catch (err) {
        return { success: false, error: err?.message || 'Gán kỹ thuật viên thất bại' }
      }
    },
    [technicians, fetchData]
  )

  const runMutation = useCallback(
    async (fn, fallbackError) => {
      try {
        const data = await fn()
        await fetchData()
        return { success: true, data }
      } catch (err) {
        return { success: false, error: err?.message || fallbackError }
      }
    },
    [fetchData]
  )

  const unassignTechnician = useCallback(
    (farmId, technicianId) => {
      if (isMockMode) {
        setFarms((prev) => prev.map((f) => (f.id === farmId ? { ...f, technician: null } : f)))
        return Promise.resolve({ success: true })
      }
      return runMutation(() => techniciansApi.unassignFarm(technicianId, farmId), 'Hủy phân công kỹ thuật viên thất bại')
    },
    [runMutation]
  )

  const createFarm = useCallback(
    (payload) => runMutation(() => farmsApi.createFarm(payload), 'Tạo nhà yến thất bại'),
    [runMutation]
  )

  const updateFarm = useCallback(
    (farmId, payload) => runMutation(() => farmsApi.updateFarm(farmId, payload), 'Cập nhật nhà yến thất bại'),
    [runMutation]
  )

  const deleteFarm = useCallback(
    (farmId) => runMutation(() => farmsApi.deleteFarm(farmId), 'Xóa nhà yến thất bại'),
    [runMutation]
  )

  const approveFarm = useCallback(
    (farmId) => runMutation(() => farmsApi.approveFarm(farmId), 'Phê duyệt nhà yến thất bại'),
    [runMutation]
  )

  const rejectFarm = useCallback(
    (farmId, rejectionReason) =>
      runMutation(
        () => farmsApi.rejectFarm(farmId, { rejection_reason: rejectionReason }),
        'Từ chối nhà yến thất bại'
      ),
    [runMutation]
  )

  const createZone = useCallback(
    (farmId, payload) => runMutation(() => farmsApi.createZone(farmId, payload), 'Tạo khu vực thất bại'),
    [runMutation]
  )

  const updateZone = useCallback(
    (zoneId, payload) => runMutation(() => farmsApi.updateZone(zoneId, payload), 'Cập nhật khu vực thất bại'),
    [runMutation]
  )

  const deleteZone = useCallback(
    (zoneId) => runMutation(() => farmsApi.deleteZone(zoneId), 'Xóa khu vực thất bại'),
    [runMutation]
  )

  const createDevice = useCallback(
    (payload) => runMutation(() => devicesApi.createDevice(payload), 'Đăng ký thiết bị thất bại'),
    [runMutation]
  )

  const updateDevice = useCallback(
    (deviceId, payload) => runMutation(() => devicesApi.updateDevice(deviceId, payload), 'Cập nhật thiết bị thất bại'),
    [runMutation]
  )

  const deleteDevice = useCallback(
    (deviceId) => runMutation(() => devicesApi.deleteDevice(deviceId), 'Xóa thiết bị thất bại'),
    [runMutation]
  )

  return {
    farms,
    devices,
    technicians,
    users,
    systemHealth,
    alerts,
    dashboardStats,
    loading,
    error,
    assignTechnician,
    unassignTechnician,
    createFarm,
    updateFarm,
    deleteFarm,
    approveFarm,
    rejectFarm,
    createZone,
    updateZone,
    deleteZone,
    createDevice,
    updateDevice,
    deleteDevice,
    refreshData: fetchData,
  }
}

export default useAdminData
