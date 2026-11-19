/**
 * SWIFTLETCARE — CP12-C TECHNICIAN REAL API INTEGRATION TEST SUITE
 * Validates:
 * 1. Live Authentication & JWT Bearer handshake for TECHNICIAN role
 * 2. Technician Profile & Dashboard API Gateway consumption
 * 3. Assigned Farms Scoping & Detail retrieval
 * 4. Assigned Farm Devices & Metadata inspection
 * 5. Assigned Farm Zones discovery & Telemetry handling
 * 6. Scoped Technical Alerts retrieval & Tenant Isolation
 * 7. Negative Security: Cross-technician access blocked (403)
 * 8. Negative Security: Unassigned farm access blocked (403)
 * 9. Negative Security: Admin-only farm assignment blocked for technician (403)
 * 10. Fail-Closed Client Integrity (Zero mock fallback)
 */

import { apiClient, setAuthToken } from '../src/api/client.js'
import { authApi } from '../src/api/modules/authApi.js'
import { techniciansApi } from '../src/api/modules/techniciansApi.js'
import { farmsApi } from '../src/api/modules/farmsApi.js'
import { alertsApi } from '../src/api/modules/alertsApi.js'
import { telemetryApi } from '../src/api/modules/telemetryApi.js'
import { ApiError } from '../src/api/errors.js'

import {
  normalizeAssignedFarm,
  normalizeTechDevice,
  normalizeTechStats,
  normalizeTechAlert,
} from '../src/features/technicians/adapters/technicianAdapter.js'
import { normalizeZone } from '../src/features/farms/adapters/farmAdapter.js'

let passed = 0
let failed = 0

function assert(condition, message) {
  if (!condition) {
    failed++
    console.error(`[FAIL] ${message}`)
    throw new Error(message)
  } else {
    passed++
    console.log(`[PASS] ${message}`)
  }
}

async function runTests() {
  console.log('='.repeat(65))
  console.log('SWIFTLETCARE — CP12-C TECHNICIAN REAL API INTEGRATION SUITE')
  console.log('='.repeat(65))

  const TECH_EMAIL = 'tech.a.demo@nestmate.dev'
  const TECH_PASSWORD = requireTestPassword()
  const CANONICAL_TECH_ID = '15e6f30f-350a-4c66-b4be-e22ab03b85dc'
  const ASSIGNED_FARM_ID = 'a18d8eee-cb1a-4b00-b375-d505eb8128d7'
  const UNASSIGNED_FARM_ID = 'f8fc4fa7-0d27-4e0b-89c0-e676e0e73469'
  const OTHER_TECH_ID = '00000000-0000-0000-0000-000000000099'

  let token = null
  let technicianId = null

  // 1. Live Authentication Handshake
  try {
    const loginResult = await authApi.login({
      email: TECH_EMAIL,
      password: TECH_PASSWORD,
    })
    token = loginResult.access_token
    technicianId = loginResult.user?.id
    setAuthToken(token)

    assert(Boolean(token), 'Live Auth: Technician authenticates via Gateway and acquires JWT')
    assert(
      technicianId === CANONICAL_TECH_ID,
      `User Identity: Canonical technician UUID confirmed (${technicianId})`,
    )
    assert(
      Array.isArray(loginResult.user?.roles) && loginResult.user.roles.includes('TECHNICIAN'),
      'RBAC Claims: Token carries TECHNICIAN role',
    )
  } catch (err) {
    assert(false, `Live Auth failed: ${err.message}`)
  }

  // 2. Protected Introspection
  try {
    const profile = await authApi.getProfile()
    assert(
      profile.id === CANONICAL_TECH_ID && profile.email === TECH_EMAIL,
      `Protected Introspection: GET /api/auth/me returns valid technician profile (${profile.full_name})`,
    )
  } catch (err) {
    assert(false, `Introspection failed: ${err.message}`)
  }

  // 3. Technician Dashboard API & Stats Normalization
  try {
    const dashboard = await techniciansApi.getDashboard(technicianId)
    assert(
      dashboard && dashboard.technician_id === CANONICAL_TECH_ID,
      `Dashboard API: GET /api/technicians/${technicianId}/dashboard returns valid summary DTO`,
    )
    assert(
      dashboard.assigned_farm_count >= 1 &&
        dashboard.zone_count >= 2 &&
        dashboard.device_count >= 2,
      `Dashboard Metrics: assigned_farms=${dashboard.assigned_farm_count}, zones=${dashboard.zone_count}, devices=${dashboard.device_count}`,
    )

    const stats = normalizeTechStats(dashboard, false)
    assert(
      Array.isArray(stats) && stats.length === 4,
      'Dashboard Adapter: Normalized raw metrics into 4 UI SystemStatCard objects',
    )
    assert(
      stats[0].id === 'nodes' && stats[1].id === 'farms',
      'Dashboard Adapter: Card types and indicators formatted cleanly',
    )
  } catch (err) {
    assert(false, `Dashboard retrieval failed: ${err.message}`)
  }

  // 4. Assigned Farms Scoping & Detail Retrieval
  try {
    const rawFarms = await techniciansApi.getFarms(technicianId)
    const farmsList = Array.isArray(rawFarms) ? rawFarms : rawFarms?.items || []
    assert(
      farmsList.length >= 1,
      `Assigned Farms: Retrieved ${farmsList.length} assigned farm(s) for technician`,
    )

    const assigned = farmsList.find((f) => f.farm_id === ASSIGNED_FARM_ID)
    assert(Boolean(assigned), `Farm Lookup: Assigned farm '${ASSIGNED_FARM_ID}' found in list`)

    const normFarm = normalizeAssignedFarm(assigned, false)
    assert(
      normFarm.id === ASSIGNED_FARM_ID &&
        normFarm.name === 'Nhà yến Demo 01' &&
        normFarm.code === 'DEMO-FARM-01' &&
        normFarm.zoneCount === 2,
      `Farm Normalization: Correctly mapped assigned farm properties (${normFarm.name})`,
    )

    const farmDetail = await techniciansApi.getFarmDetail(technicianId, ASSIGNED_FARM_ID)
    assert(
      farmDetail && farmDetail.farm_id === ASSIGNED_FARM_ID,
      'Farm Detail API: GET /api/technicians/{id}/farms/{farm_id} returned active farm details',
    )
  } catch (err) {
    assert(false, `Assigned farms retrieval failed: ${err.message}`)
  }

  // 5. Assigned Farm Devices Scoping & Normalization
  try {
    const rawDevices = await techniciansApi.getFarmDevices(technicianId, ASSIGNED_FARM_ID)
    const devList = Array.isArray(rawDevices) ? rawDevices : rawDevices?.items || []
    assert(
      devList.length >= 2,
      `Assigned Devices: Retrieved ${devList.length} device(s) within assigned farm`,
    )

    const normDevices = devList.map((d) => normalizeTechDevice(d, 'Nhà yến Demo 01'))
    const cameraNode = normDevices.find((d) => d.type === 'CAMERA')
    const sensorNode = normDevices.find((d) => d.type === 'SENSOR')

    assert(
      Boolean(cameraNode && cameraNode.id === 'c0000001-0000-0000-0000-000000000001'),
      `Device Normalization: Camera node mapped (${cameraNode?.name})`,
    )
    assert(
      Boolean(sensorNode && sensorNode.nodeId === 'SWC-DEMO-NODE-001'),
      `Device Normalization: Environment sensor node mapped (${sensorNode?.name})`,
    )

    const devDetail = await techniciansApi.getFarmDeviceDetail(
      technicianId,
      ASSIGNED_FARM_ID,
      'c0000001-0000-0000-0000-000000000001',
    )
    assert(
      devDetail && devDetail.device_id === 'c0000001-0000-0000-0000-000000000001',
      'Device Detail API: GET /api/technicians/{id}/farms/{farm_id}/devices/{device_id} succeeded',
    )
  } catch (err) {
    assert(false, `Assigned farm devices retrieval failed: ${err.message}`)
  }

  // 6. Farm Zones & Telemetry Handling
  try {
    const rawZones = await farmsApi.getFarmZones(ASSIGNED_FARM_ID)
    const zonesList = Array.isArray(rawZones) ? rawZones : rawZones?.items || []
    assert(zonesList.length >= 2, `Farm Zones: Retrieved ${zonesList.length} zone(s)`)

    const normZones = zonesList.map(normalizeZone)
    assert(
      normZones.some((z) => z.name === 'Tầng 1') && normZones.some((z) => z.name === 'Tầng 2'),
      'Zone Normalization: Tầng 1 and Tầng 2 zones resolved correctly',
    )

    let telemHandled = false
    try {
      await telemetryApi.getFarmLatest(ASSIGNED_FARM_ID)
      telemHandled = true
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        telemHandled = true
      }
    }
    assert(telemHandled, 'Telemetry Handling: Unseeded telemetry (HTTP 404) handled gracefully')
  } catch (err) {
    assert(false, `Zones & Telemetry check failed: ${err.message}`)
  }

  // 7. Scoped Technical Alerts & Tenant Isolation
  try {
    const scopedAlerts = await alertsApi.getAlerts({ params: { farmId: ASSIGNED_FARM_ID } })
    assert(
      Array.isArray(scopedAlerts),
      `Scoped Alerts: GET /api/v1/alerts?farmId=${ASSIGNED_FARM_ID} returned valid array (count=${scopedAlerts.length})`,
    )

    let unscopedRejected = false
    try {
      await alertsApi.getAlerts()
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        unscopedRejected = true
      }
    }
    assert(
      unscopedRejected,
      'Tenant Boundary: Calling /api/v1/alerts without farmId rejected with 403 Forbidden',
    )
  } catch (err) {
    assert(false, `Alerts check failed: ${err.message}`)
  }

  // 8. Negative Test: Cross-Technician Resource Access (RBAC)
  try {
    let crossTechDashboardBlocked = false
    try {
      await techniciansApi.getDashboard(OTHER_TECH_ID)
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        crossTechDashboardBlocked = true
      }
    }
    assert(
      crossTechDashboardBlocked,
      `RBAC Security: Technician querying other technician's dashboard rejected with 403 Forbidden`,
    )

    let crossTechProfileBlocked = false
    try {
      await techniciansApi.getTechnicianById(OTHER_TECH_ID)
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        crossTechProfileBlocked = true
      }
    }
    assert(
      crossTechProfileBlocked,
      `RBAC Security: Technician querying other technician's profile rejected with 403 Forbidden`,
    )
  } catch (err) {
    assert(false, `Cross-technician negative test failed: ${err.message}`)
  }

  // 9. Negative Test: Unassigned Farm Resource Access (RBAC)
  try {
    let unassignedFarmBlocked = false
    try {
      await techniciansApi.getFarmDetail(technicianId, UNASSIGNED_FARM_ID)
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        unassignedFarmBlocked = true
      }
    }
    assert(
      unassignedFarmBlocked,
      `Assignment Isolation: Accessing unassigned farm '${UNASSIGNED_FARM_ID}' rejected with 403 Forbidden`,
    )

    let unassignedDevicesBlocked = false
    try {
      await techniciansApi.getFarmDevices(technicianId, UNASSIGNED_FARM_ID)
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        unassignedDevicesBlocked = true
      }
    }
    assert(
      unassignedDevicesBlocked,
      `Assignment Isolation: Accessing devices of unassigned farm rejected with 403 Forbidden`,
    )
  } catch (err) {
    assert(false, `Unassigned farm negative test failed: ${err.message}`)
  }

  // 10. Negative Test: Admin-only Farm Assignment Mutation
  try {
    let assignForbidden = false
    try {
      await techniciansApi.assignFarm(technicianId, UNASSIGNED_FARM_ID)
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        assignForbidden = true
      }
    }
    assert(
      assignForbidden,
      'Mutation RBAC: Technician attempting Admin-only farm assignment rejected with 403 Forbidden',
    )
  } catch (err) {
    assert(false, `Admin mutation negative test failed: ${err.message}`)
  }

  // 11. Fail-Closed Verification
  try {
    let failedClosed = false
    try {
      await apiClient.get('/api/v1/technicians/non-existent-endpoint')
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        failedClosed = true
      }
    }
    assert(
      failedClosed,
      'Fail-Closed Verification: Non-existent endpoint throws ApiError (404), zero mock fallback',
    )
  } catch (err) {
    assert(false, `Fail-closed test failed: ${err.message}`)
  }

  console.log('='.repeat(65))
  console.log(`TOTAL CP12-C TESTS: ${passed + failed} | PASSED: ${passed} | FAILED: ${failed}`)
  console.log('='.repeat(65))

  if (failed > 0) {
    process.exit(1)
  }
}

runTests().catch((err) => {
  console.error('Unhandled test suite failure:', err)
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
