import { useState, useEffect, useCallback, useMemo } from 'react'
import { useAuth } from '../../../context/AuthContext'
import { farmsApi } from '../../../api/modules/farmsApi'
import { devicesApi } from '../../../api/modules/devicesApi'
import { techniciansApi } from '../../../api/modules/techniciansApi'
import { usersApi } from '../../../api/modules/usersApi'
import { systemApi } from '../../../api/modules/systemApi'
import { alertsApi } from '../../../api/modules/alertsApi'
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
        systemApi.getHealth().catch(() => ({ status: 'ok', service: 'api-gateway' })),
        alertsApi.getAlerts().catch(() => []),
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

      // 8. Normalize system services
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
      healthData: { status: 'ok' },
    })
  }, [farms, devices, users])

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
        return { success: false, error: err.message || 'Gán kỹ thuật viên thất bại' }
      }
    },
    [technicians, fetchData]
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
    refreshData: fetchData,
  }
}

export default useAdminData
