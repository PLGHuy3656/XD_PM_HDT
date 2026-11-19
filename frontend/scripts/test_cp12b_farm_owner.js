/**
 * SWIFTLETCARE — CP12-B FARM OWNER REAL API INTEGRATION TEST SUITE
 * Verifies end-to-end integration of all Farm Owner domain endpoints,
 * tenant isolation, resource guards, fail-closed behavior, and adapter normalization.
 */

import { apiClient, setAuthToken } from '../src/api/client.js'
import { authApi } from '../src/api/modules/authApi.js'
import { farmsApi } from '../src/api/modules/farmsApi.js'
import { devicesApi } from '../src/api/modules/devicesApi.js'
import { alertsApi } from '../src/api/modules/alertsApi.js'
import { telemetryApi } from '../src/api/modules/telemetryApi.js'
import { camerasApi } from '../src/api/modules/camerasApi.js'
import { analyticsApi } from '../src/api/modules/analyticsApi.js'
import { ApiError } from '../src/api/errors.js'

import { normalizeFarm, normalizeZone } from '../src/features/farms/adapters/farmAdapter.js'
import { normalizeDevice } from '../src/features/devices/adapters/deviceAdapter.js'
import { normalizeAlert } from '../src/features/alerts/adapters/alertAdapter.js'
import {
  normalizeTelemetry,
  formatHeaderEnvironment,
} from '../src/features/telemetry/adapters/telemetryAdapter.js'
import {
  normalizeBirdPerformance,
  normalizeAnalyticsSummary,
} from '../src/features/analytics/adapters/analyticsAdapter.js'

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
  console.log('SWIFTLETCARE — CP12-B FARM OWNER REAL API INTEGRATION SUITE')
  console.log('='.repeat(65))

  const DEMO_OWNER_EMAIL = 'owner.a.demo@nestmate.dev'
  const DEMO_OWNER_PASS = requireTestPassword()
  const DEMO_FARM_ID = 'a18d8eee-cb1a-4b00-b375-d505eb8128d7'
  const OWN_CAMERA_ID = 'c0000001-0000-0000-0000-000000000001'
  const CROSS_FARM_CAMERA_ID = 'c0000002-0000-0000-0000-000000000002'

  let token = null

  // 1. Live Authentication
  try {
    const loginResult = await authApi.login({
      email: DEMO_OWNER_EMAIL,
      password: DEMO_OWNER_PASS,
    })
    token = loginResult.access_token
    setAuthToken(token)
    assert(Boolean(token), 'Live Auth: Farm Owner authenticates via Gateway and acquires JWT')
  } catch (err) {
    assert(false, `Live Auth failed: ${err.message}`)
  }

  // 2. Farm Listing & DTO Normalization
  try {
    const rawFarms = await farmsApi.getFarms()
    const farmList = Array.isArray(rawFarms) ? rawFarms : rawFarms?.items || []
    assert(farmList.length > 0, `Farm List: Gateway returned ${farmList.length} accessible farm(s)`)

    const targetFarm = farmList.find((f) => f.farm_id === DEMO_FARM_ID || f.id === DEMO_FARM_ID)
    assert(Boolean(targetFarm), `Farm Lookup: Demo farm '${DEMO_FARM_ID}' found in payload`)

    const normalized = normalizeFarm(targetFarm, false)
    assert(
      normalized.id === DEMO_FARM_ID &&
        normalized.name === 'Nhà yến Demo 01' &&
        normalized.code === 'DEMO-FARM-01' &&
        normalized.zoneCount === 2 &&
        normalized.totalDevices === 2,
      `Farm Normalization: Correctly mapped snake_case to camelCase (name="${normalized.name}", code="${normalized.code}", zoneCount=${normalized.zoneCount}, totalDevices=${normalized.totalDevices})`,
    )
    assert(
      normalized.temperature === null && normalized.humidity === null,
      'Farm Fail-Closed: Real mode returns null for unseeded metrics without injecting fake numbers',
    )
  } catch (err) {
    assert(false, `Farm Listing failed: ${err.message}`)
  }

  // 3. Farm Zones Discovery
  try {
    const rawZones = await farmsApi.getFarmZones(DEMO_FARM_ID)
    const zonesList = Array.isArray(rawZones) ? rawZones : rawZones?.items || []
    assert(zonesList.length >= 2, `Farm Zones: Retrieved ${zonesList.length} zone(s) for demo farm`)

    const normalizedZones = zonesList.map(normalizeZone)
    const floor1 = normalizedZones.find((z) => z.name === 'Tầng 1')
    assert(
      Boolean(floor1) && floor1.floorNumber === 1,
      `Zone Normalization: Correctly resolved zone '${floor1?.name}' with floorNumber=1`,
    )
  } catch (err) {
    assert(false, `Farm Zones failed: ${err.message}`)
  }

  // 4. Farm Devices Scoping
  try {
    const rawDevices = await devicesApi.getDevices({ params: { farm_id: DEMO_FARM_ID } })
    const devList = Array.isArray(rawDevices) ? rawDevices : rawDevices?.items || []
    assert(devList.length >= 2, `Farm Devices: Retrieved ${devList.length} device(s) for farm`)

    const normalizedDevices = devList.map(normalizeDevice)
    const cameraDevice = normalizedDevices.find((d) => d.type === 'CAMERA')
    const sensorDevice = normalizedDevices.find((d) => d.type === 'SENSOR' || d.type === 'CONTROLLER')

    assert(
      Boolean(cameraDevice) && cameraDevice.id === OWN_CAMERA_ID,
      `Device Scoping: Found camera node '${cameraDevice?.name}' (${cameraDevice?.id})`,
    )
    assert(
      Boolean(sensorDevice),
      `Device Scoping: Found IoT environment node '${sensorDevice?.name}'`,
    )
  } catch (err) {
    assert(false, `Farm Devices failed: ${err.message}`)
  }

  // 5. Scoped Alerts & Tenant Isolation Guard
  try {
    const scopedAlerts = await alertsApi.getAlerts({ params: { farmId: DEMO_FARM_ID } })
    assert(
      Array.isArray(scopedAlerts),
      `Scoped Alerts: GET /api/v1/alerts?farmId=${DEMO_FARM_ID} returned valid array (count=${scopedAlerts.length})`,
    )

    // Negative Test: Unscoped alert call MUST be rejected with 403 Forbidden
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
      'Tenant Boundary: Unscoped /api/v1/alerts without farmId rejected with 403 Forbidden',
    )
  } catch (err) {
    assert(false, `Alerts tenant isolation failed: ${err.message}`)
  }

  // 6. Camera Ownership & Resource Guard (NB-2 Parity)
  try {
    // Farm Owner querying own camera: should be authorized (status returns 404 because camera stream process is offline, NOT 403)
    let ownCameraAuthorized = false
    try {
      await camerasApi.getCameraStatus(OWN_CAMERA_ID)
      ownCameraAuthorized = true
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        ownCameraAuthorized = true // 404 means route & ownership check passed, camera daemon offline
      }
    }
    assert(
      ownCameraAuthorized,
      `Camera Guard (Positive): Own camera '${OWN_CAMERA_ID}' passed ownership verification (HTTP 404 offline, not 403)`,
    )

    // Farm Owner querying cross-farm camera: MUST be rejected with 403 Forbidden
    let crossCameraBlocked = false
    try {
      await camerasApi.getCameraStatus(CROSS_FARM_CAMERA_ID)
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        crossCameraBlocked = true
      }
    }
    assert(
      crossCameraBlocked,
      `Camera Guard (Negative): Cross-farm camera '${CROSS_FARM_CAMERA_ID}' blocked with 403 Forbidden`,
    )
  } catch (err) {
    assert(false, `Camera Resource Guard failed: ${err.message}`)
  }

  // 7. Analytics Summary & Trends (PostgreSQL B4 Parity)
  try {
    const summary = await analyticsApi.getFarmSummary(DEMO_FARM_ID)
    assert(
      Boolean(summary && summary.farmId === DEMO_FARM_ID),
      `Analytics Summary: Retrieved live summary for '${summary?.farmName}' (period=${summary?.period})`,
    )

    const normSummary = normalizeAnalyticsSummary(summary, false)
    assert(
      normSummary.birdPerformance && typeof normSummary.birdPerformance.entries === 'number',
      'Analytics Normalization: Bird performance and microclimate scores normalized cleanly',
    )

    const trends = await analyticsApi.getFarmTrends(DEMO_FARM_ID)
    assert(
      Boolean(trends && Array.isArray(trends.hourlyBirdActivity)),
      `Analytics Trends: Retrieved trend arrays (hourlyBirdActivity=${trends?.hourlyBirdActivity?.length})`,
    )
  } catch (err) {
    assert(false, `Analytics retrieval failed: ${err.message}`)
  }

  // 8. Telemetry 404 Handling & Formatted Headers
  try {
    let telemetryHandled = false
    let telemetryPayload = null
    try {
      telemetryPayload = await telemetryApi.getFarmLatest(DEMO_FARM_ID)
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        telemetryPayload = null
        telemetryHandled = true
      }
    }

    const normTelemetry = normalizeTelemetry(telemetryPayload, false)
    const formattedHeaders = formatHeaderEnvironment(normTelemetry, false)

    assert(
      telemetryHandled || telemetryPayload !== null,
      'Telemetry Handling: Gateway 404 on unseeded farm telemetry handled gracefully without throwing',
    )
    assert(
      formattedHeaders[0].value === '--°C' && formattedHeaders[1].value === '--%',
      `Telemetry Placeholders: Formatted empty metrics as '--°C' and '--%' (no fake 28.5/80 mock values)`,
    )
  } catch (err) {
    assert(false, `Telemetry handling failed: ${err.message}`)
  }

  // 9. Fail-Closed Client Integrity
  try {
    let failedClosed = false
    try {
      await apiClient.get('/api/v1/non-existent-endpoint')
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        failedClosed = true
      }
    }
    assert(
      failedClosed,
      'Fail-Closed Verification: Unknown endpoint throws ApiError (404), zero mock fallback',
    )
  } catch (err) {
    assert(false, `Fail-Closed verification failed: ${err.message}`)
  }

  console.log('='.repeat(65))
  console.log(`TOTAL CP12-B TESTS: ${passed + failed} | PASSED: ${passed} | FAILED: ${failed}`)
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
