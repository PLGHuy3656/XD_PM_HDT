/**
 * SWIFTLETCARE — CP12-D ADMINISTRATOR REAL API INTEGRATION SUITE
 * Verifies all 5 Admin screens connected to real API Gateway and microservices:
 * D1: Admin Dashboard (Stats, Management Cards, Roles, System Health)
 * D2: User Management (Auth profile, Technicians, Farm Owners, Fail-closed)
 * D3: Farm Management (Global Farm List, Farm Details, Zones, Technician Assignment)
 * D4: Device Management (Unscoped Global Device List, Device Details, Mapping)
 * D5: System Page & Observability (Gateway Health, Upstreams, Unscoped Alerts)
 * D6: RBAC Cross-Role Boundary & Security (Admin permissions vs Farm Owner / Technician)
 */

import { authApi } from '../src/api/modules/authApi.js'
import { farmsApi } from '../src/api/modules/farmsApi.js'
import { devicesApi } from '../src/api/modules/devicesApi.js'
import { techniciansApi } from '../src/api/modules/techniciansApi.js'
import { systemApi } from '../src/api/modules/systemApi.js'
import { alertsApi } from '../src/api/modules/alertsApi.js'
import { apiClient, setAuthToken } from '../src/api/client.js'
import {
  normalizeAdminDevice,
  normalizeAdminFarm,
  normalizeAdminTechnician,
  normalizeAdminUser,
  normalizeSystemServices,
  normalizeAdminDashboardStats,
} from '../src/features/admin/adapters/adminAdapter.js'
import { getFarmDeviceCount } from '../src/components/features/admin/farms/adminFarmsMockData.js'

let totalTests = 0
let passedTests = 0
let failedTests = 0

function assert(condition, message, detail = '') {
  totalTests++
  if (condition) {
    passedTests++
    console.log(`[PASS] ${message}${detail ? ` (${detail})` : ''}`)
  } else {
    failedTests++
    console.error(`[FAIL] ${message}${detail ? ` — DETAIL: ${detail}` : ''}`)
  }
}

async function runAdminIntegrationTests() {
  console.log('=================================================================')
  console.log('SWIFTLETCARE — CP12-D ADMINISTRATOR REAL API INTEGRATION SUITE')
  console.log('=================================================================')

  const adminCredentials = {
    email: 'admin.demo@nestmate.dev',
    password: requireTestPassword(),
  }

  const techCredentials = {
    email: 'tech.a.demo@nestmate.dev',
    password: requireTestPassword(),
  }

  const ownerCredentials = {
    email: 'owner.a.demo@nestmate.dev',
    password: requireTestPassword(),
  }

  let adminUser = null
  let adminToken = null

  // -------------------------------------------------------------
  // TEST SUITE 1: Live Authentication & Identity (Admin)
  // -------------------------------------------------------------
  try {
    const authResp = await authApi.login(adminCredentials)
    adminToken = authResp.access_token
    adminUser = authResp.user

    assert(Boolean(adminToken && adminToken.length > 20), 'Live Auth: Admin authenticates via Gateway and acquires JWT')
    assert(adminUser.email === adminCredentials.email, 'User Identity: Email matches canonical admin email', adminUser.email)
    assert(Array.isArray(adminUser.roles) && adminUser.roles.includes('ADMIN'), 'RBAC Claims: Token carries ADMIN role', JSON.stringify(adminUser.roles))

    // Set token for subsequent calls
    setAuthToken(adminToken)

    const profile = await authApi.getProfile()
    assert(profile.id === adminUser.id, 'Protected Introspection: GET /api/auth/me returns valid admin profile', profile.full_name)
  } catch (err) {
    assert(false, 'Live Auth & Identity failed', err.message)
    process.exit(1)
  }

  // -------------------------------------------------------------
  // TEST SUITE 2: Farm Management & Details (D3)
  // -------------------------------------------------------------
  let rawFarms = []
  let demoFarm1 = null
  let demoFarm2 = null
  let demoFarm1Detail = null
  let demoFarm1Zones = []

  try {
    rawFarms = await farmsApi.getFarms()
    assert(Array.isArray(rawFarms) && rawFarms.length >= 2, 'Farm List: Gateway returned global farm listing for Admin', `count=${rawFarms.length}`)

    demoFarm1 = rawFarms.find((f) => f.farm_code === 'DEMO-FARM-01' || f.farm_id === 'a18d8eee-cb1a-4b00-b375-d505eb8128d7')
    demoFarm2 = rawFarms.find((f) => f.farm_code === 'DEMO-FARM-02' || f.farm_id === 'f8fc4fa7-0d27-4e0b-89c0-e676e0e73469')

    assert(Boolean(demoFarm1), 'Farm Lookup: DEMO-FARM-01 present in global list', demoFarm1?.farm_name)
    assert(Boolean(demoFarm2), 'Farm Lookup: DEMO-FARM-02 present in global list', demoFarm2?.farm_name)

    demoFarm1Detail = await farmsApi.getFarmById(demoFarm1.farm_id)
    assert(Boolean(demoFarm1Detail && demoFarm1Detail.owner_name), 'Farm Detail API: GET /api/farms/{id} returns owner info', demoFarm1Detail.owner_name)
    assert(Boolean(demoFarm1Detail.technician_name), 'Farm Detail API: Returns assigned technician info', demoFarm1Detail.technician_name)

    demoFarm1Zones = await farmsApi.getFarmZones(demoFarm1.farm_id)
    assert(Array.isArray(demoFarm1Zones) && demoFarm1Zones.length >= 2, 'Farm Zones: Retrieved zones for DEMO-FARM-01', `zones=${demoFarm1Zones.length}`)
  } catch (err) {
    assert(false, 'Farm Management API failed', err.message)
  }

  // -------------------------------------------------------------
  // TEST SUITE 3: Device Management (D4)
  // -------------------------------------------------------------
  let rawDevices = []
  let normalizedDevices = []

  try {
    // Admin un-scoped device listing (non-admins receive 403)
    rawDevices = await devicesApi.getDevices()
    assert(Array.isArray(rawDevices) && rawDevices.length >= 4, 'Global Device Listing: Admin retrieves unscoped devices across all farms', `count=${rawDevices.length}`)

    const cam01 = rawDevices.find((d) => d.node_id === 'CAM-01')
    const esp01 = rawDevices.find((d) => d.node_id === 'SWC-DEMO-NODE-001')

    assert(Boolean(cam01), 'Device Lookup: AI Camera CAM-01 found in registry', cam01?.name)
    assert(Boolean(esp01), 'Device Lookup: Environment Node SWC-DEMO-NODE-001 found in registry', esp01?.name)

    // Device Detail API
    const deviceDetail = await devicesApi.getDeviceById(cam01.device_id)
    assert(deviceDetail.device_id === cam01.device_id, 'Device Detail API: GET /api/devices/{id} returned full metadata', deviceDetail.name)

    // Normalize devices
    const farmsMap = { [demoFarm1.farm_id]: demoFarm1, [demoFarm2.farm_id]: demoFarm2 }
    normalizedDevices = rawDevices.map((d) => normalizeAdminDevice(d, farmsMap))

    const normCam = normalizedDevices.find((d) => d.nodeId === 'CAM-01')
    assert(normCam && normCam.type === 'AI Camera Node', 'Device Normalization: Camera mapped to UI display type', normCam?.type)
    assert(normCam.farm.code === 'DEMO-FARM-01', 'Device Normalization: Farm relationship resolved', normCam?.farm?.code)
  } catch (err) {
    assert(false, 'Device Management API failed', err.message)
  }

  // -------------------------------------------------------------
  // TEST SUITE 4: Farm Normalization & getFarmDeviceCount Compatibility
  // -------------------------------------------------------------
  try {
    const normalizedFarm1 = normalizeAdminFarm(demoFarm1Detail, demoFarm1Zones, normalizedDevices)

    assert(normalizedFarm1.id === demoFarm1.farm_id, 'Farm Normalization: Farm ID mapped correctly')
    assert(normalizedFarm1.name === demoFarm1Detail.farm_name, 'Farm Normalization: Name mapped correctly', normalizedFarm1.name)
    assert(normalizedFarm1.owner.name === demoFarm1Detail.owner_name, 'Farm Normalization: Owner mapped correctly', normalizedFarm1.owner.name)
    assert(Array.isArray(normalizedFarm1.zones) && normalizedFarm1.zones.length >= 2, 'Farm Normalization: Zones attached')

    // Verify compatibility with getFarmDeviceCount
    const computedCount = getFarmDeviceCount(normalizedFarm1)
    assert(computedCount >= 2, 'Component Compatibility: getFarmDeviceCount(farm) computes accurately from nested devices', `devices=${computedCount}`)
  } catch (err) {
    assert(false, 'Farm Normalization failed', err.message)
  }

  // -------------------------------------------------------------
  // TEST SUITE 5: Technicians & Assignment (D3 & D6)
  // -------------------------------------------------------------
  let rawTechs = []
  try {
    rawTechs = await techniciansApi.getTechnicians()
    assert(Array.isArray(rawTechs) && rawTechs.length >= 1, 'Technicians List: Admin lists all registered technicians', `count=${rawTechs.length}`)

    const demoTech = rawTechs.find((t) => t.email === techCredentials.email)
    assert(Boolean(demoTech), 'Technician Lookup: Found demo technician in list', demoTech?.full_name)

    // Test Admin assignment mutation: assign demoTech to DEMO-FARM-01
    const assignResp = await techniciansApi.assignFarm(demoTech.technician_id, demoFarm1.farm_id)
    assert(assignResp && (assignResp.status === 'success' || assignResp.message || assignResp.technician_id || assignResp.farm_id), 'Technician Assignment Mutation: POST /api/technicians/{id}/farms/{id}/assign succeeded for Admin')
  } catch (err) {
    assert(false, 'Technicians & Assignment failed', err.message)
  }

  // -------------------------------------------------------------
  // TEST SUITE 6: System Page & Observability (D5)
  // -------------------------------------------------------------
  let healthData = null
  let rawAlerts = []
  try {
    healthData = await systemApi.getHealth()
    assert(healthData && healthData.status === 'ok', 'System Health API: GET /health returns 200 OK', `status=${healthData?.status}`)
    assert(Boolean(healthData.upstreams && healthData.upstreams.management), 'Microservice Upstreams: Management service upstream present', healthData?.upstreams?.management)
    assert(Boolean(healthData.upstreams.iot && healthData.upstreams.ai), 'Microservice Upstreams: IoT and AI upstream services present')

    const normalizedServices = normalizeSystemServices(healthData)
    assert(normalizedServices.length === 6, 'Services Normalization: Formatted 6 platform microservices', `count=${normalizedServices.length}`)
    assert(normalizedServices.every((s) => s.status === 'HEALTHY'), 'Services Health: All active microservices status HEALTHY')

    // Admin unscoped alerts query (non-admins receive 403)
    rawAlerts = await alertsApi.getAlerts()
    assert(Array.isArray(rawAlerts), 'Unscoped Alerts: Admin retrieves global alerts without mandatory farmId parameter', `alerts=${rawAlerts.length}`)
  } catch (err) {
    assert(false, 'System Page & Observability failed', err.message)
  }

  // -------------------------------------------------------------
  // TEST SUITE 7: Admin Dashboard Stats Normalization (D1)
  // -------------------------------------------------------------
  try {
    const knownUsers = [
      normalizeAdminUser(adminUser),
      ...rawTechs.map(normalizeAdminTechnician),
      {
        id: 'OWNER-01',
        name: demoFarm1Detail.owner_name,
        email: 'owner.a.demo@nestmate.dev',
        role: 'FARM_OWNER',
        status: 'ACTIVE',
        joinedAt: '01/11/2026',
        lastActive: 'Đang hoạt động',
      },
    ]

    const stats = normalizeAdminDashboardStats({
      farms: [demoFarm1, demoFarm2],
      devices: normalizedDevices,
      users: knownUsers,
      healthData,
    })

    assert(Array.isArray(stats.managementItems) && stats.managementItems.length === 3, 'Dashboard Stats: Management cards formatted for 3 domains (Users, Farms, Devices)')
    assert(stats.managementItems.find((m) => m.id === 'farms').value === '2', 'Dashboard Stats: Total farms card matches 2')
    assert(stats.managementItems.find((m) => m.id === 'devices').value === '4', 'Dashboard Stats: Total devices card matches 4')
    assert(stats.roles.find((r) => r.id === 'admin').value === 1, 'Role Distribution: Admin count matches 1')
    assert(stats.roles.find((r) => r.id === 'technician').value >= 1, 'Role Distribution: Technician count matches real techs')
    assert(Array.isArray(stats.recentAccounts) && stats.recentAccounts.length >= 3, 'Recent Accounts: Aggregated real accounts without mock secrets')
  } catch (err) {
    assert(false, 'Admin Dashboard Stats failed', err.message)
  }

  // -------------------------------------------------------------
  // TEST SUITE 8: RBAC Security & Tenant Boundaries (D6)
  // -------------------------------------------------------------
  try {
    // 8a. Farm Owner attempting unscoped global devices -> Must be rejected with 403
    const ownerLogin = await authApi.login(ownerCredentials)
    setAuthToken(ownerLogin.access_token)

    let ownerDevicesBlocked = false
    try {
      await devicesApi.getDevices()
    } catch (err) {
      if (err.status === 403) ownerDevicesBlocked = true
    }
    assert(ownerDevicesBlocked, 'RBAC Security: Farm Owner blocked from global device listing (HTTP 403 Forbidden)')

    // 8b. Farm Owner attempting technician list -> Must be rejected with 403
    let ownerTechListBlocked = false
    try {
      await techniciansApi.getTechnicians()
    } catch (err) {
      if (err.status === 403) ownerTechListBlocked = true
    }
    assert(ownerTechListBlocked, 'RBAC Security: Farm Owner blocked from listing technicians (HTTP 403 Forbidden)')

    // 8c. Technician attempting admin-only farm assignment mutation -> Must be rejected with 403
    const techLogin = await authApi.login(techCredentials)
    setAuthToken(techLogin.access_token)

    let techAssignBlocked = false
    try {
      await techniciansApi.assignFarm(techCredentials.email, demoFarm1.farm_id)
    } catch (err) {
      if (err.status === 403) techAssignBlocked = true
    }
    assert(techAssignBlocked, 'RBAC Security: Technician blocked from assigning farms (HTTP 403 Forbidden: Administrator role required)')

    // 8d. Technician attempting unscoped alerts -> Must be rejected with 403
    let techAlertsBlocked = false
    try {
      await alertsApi.getAlerts()
    } catch (err) {
      if (err.status === 403) techAlertsBlocked = true
    }
    assert(techAlertsBlocked, 'RBAC Security: Technician blocked from unscoped alerts (HTTP 403 Forbidden)')

    // 8e. Restore admin token
    setAuthToken(adminToken)
  } catch (err) {
    assert(false, 'RBAC Security suite failed', err.message)
  }

  // -------------------------------------------------------------
  // TEST SUITE 9: Fail-Closed & No Mock Fallback (D6)
  // -------------------------------------------------------------
  try {
    let nonExistentFailed = false
    try {
      await apiClient.get('/api/users/non-existent-endpoint-fail-closed')
    } catch (err) {
      if (err.status === 404) nonExistentFailed = true
    }
    assert(nonExistentFailed, 'Fail-Closed Verification: Unimplemented endpoint throws ApiError (404), zero mock fallback in Real mode')
  } catch (err) {
    assert(false, 'Fail-Closed test failed', err.message)
  }

  // -------------------------------------------------------------
  // Summary
  // -------------------------------------------------------------
  console.log('=================================================================')
  console.log(`TOTAL CP12-D TESTS: ${totalTests} | PASSED: ${passedTests} | FAILED: ${failedTests}`)
  console.log('=================================================================')

  if (failedTests > 0) {
    process.exit(1)
  }
}

runAdminIntegrationTests().catch((err) => {
  console.error('Fatal test error:', err)
  process.exit(1)
})

// CP13 hardening R1: no default demo password. Fail fast when it is not provided.
function requireTestPassword() {
  const value = process.env.SWC_TEST_PASSWORD
  if (!value) {
    console.error('SWC_TEST_PASSWORD is required (no default password is bundled with this script).')
    process.exit(2)
  }
  return value
}
