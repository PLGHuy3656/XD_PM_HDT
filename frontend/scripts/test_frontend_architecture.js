/**
 * SwiftletCare CP12-PREP Automated Frontend Architecture Verification Test Suite
 * Validates:
 * 1. API Client, Error Normalization, and AbortSignal
 * 2. Identity Normalization and Role Checks
 * 3. 22 Route Registry and Integrity
 * 4. Fail-closed behavior (Real API does NOT fallback silently to mock)
 * 5. Feature Adapters & Mock Data Preservation
 */

import assert from 'node:assert'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const srcDir = path.resolve(__dirname, '../src')

console.log('=================================================================')
console.log('SWIFTLETCARE — CP12-PREP FRONTEND ARCHITECTURE TEST SUITE')
console.log('=================================================================\n')

let passedTests = 0
let failedTests = 0

function runTest(name, fn) {
  try {
    fn()
    console.log(`[PASS] ${name}`)
    passedTests++
  } catch (err) {
    console.error(`[FAIL] ${name}:`, err.message)
    failedTests++
  }
}

async function runAsyncTest(name, fn) {
  try {
    await fn()
    console.log(`[PASS] ${name}`)
    passedTests++
  } catch (err) {
    console.error(`[FAIL] ${name}:`, err.message)
    failedTests++
  }
}

// -------------------------------------------------------------
// Test 1: Verify 22 Route Definitions in App.jsx
// -------------------------------------------------------------
runTest('Verify exact 22 page routes declared in App.jsx', () => {
  const appFile = fs.readFileSync(path.join(srcDir, 'App.jsx'), 'utf-8')
  
  const expectedRoutes = [
    '/login',
    '/register',
    '/settings',
    '/owner/dashboard',
    '/owner/farms',
    '/owner/environment',
    '/owner/environment/control',
    '/owner/devices',
    '/owner/swiftlets',
    '/owner/alerts',
    '/owner/analytics',
    '/technician/dashboard',
    '/technician/environment',
    '/technician/devices',
    '/technician/installation',
    '/technician/diagnostics',
    '/technician/alerts',
    '/admin/dashboard',
    '/admin/users',
    '/admin/farms',
    '/admin/devices',
    '/admin/system',
  ]

  for (const route of expectedRoutes) {
    assert(
      appFile.includes(`path="${route}"`),
      `App.jsx must declare route path "${route}"`,
    )
  }
  assert.strictEqual(expectedRoutes.length, 22)
})

// -------------------------------------------------------------
// Test 2: Verify API Endpoints Registry parity with Gateway CP11
// -------------------------------------------------------------
await runAsyncTest('Verify API Endpoints Registry structure and Gateway parity', async () => {
  const { ENDPOINTS } = await import('../src/api/endpoints.js')
  
  assert.strictEqual(ENDPOINTS.AUTH.LOGIN, '/api/auth/login')
  assert.strictEqual(ENDPOINTS.AUTH.ME, '/api/auth/me')
  assert.strictEqual(ENDPOINTS.FARMS.LIST, '/api/farms')
  assert.strictEqual(ENDPOINTS.FARMS.DETAIL('f-1'), '/api/farms/f-1')
  assert.strictEqual(ENDPOINTS.DEVICES.LIST, '/api/devices')
  assert.strictEqual(ENDPOINTS.DEVICES.COMMAND_RELAY('dev-1'), '/api/iot/devices/dev-1/commands/relay')
  assert.strictEqual(ENDPOINTS.TELEMETRY.FARM_LATEST('f-1'), '/api/iot/farms/f-1/telemetry/latest')
  assert.strictEqual(ENDPOINTS.AI.CAMERAS, '/api/v1/ai/cameras')
  assert.strictEqual(ENDPOINTS.ALERTS.LIST, '/api/v1/alerts')
  assert.strictEqual(ENDPOINTS.ALERTS.ACKNOWLEDGE('alt-1'), '/api/v1/alerts/alt-1/acknowledge')
  assert.strictEqual(ENDPOINTS.ANALYTICS.FARM_SUMMARY('f-1'), '/api/v1/analytics/farms/f-1/summary')
  assert.strictEqual(ENDPOINTS.TECHNICIANS.LIST, '/api/technicians')
})

// -------------------------------------------------------------
// Test 3: Verify ApiError normalization & classification
// -------------------------------------------------------------
await runAsyncTest('Verify ApiError normalization and status classification', async () => {
  const { ApiError, normalizeError } = await import('../src/api/errors.js')

  const netErr = new TypeError('Failed to fetch')
  const normalizedNet = normalizeError(netErr, '/api/test')
  assert(normalizedNet.isNetworkError)
  assert.strictEqual(normalizedNet.status, 0)
  assert.strictEqual(normalizedNet.code, 'NETWORK_ERROR')

  const authErr = new ApiError('Unauthorized', 401, 'UNAUTHORIZED')
  assert(authErr.isUnauthorized)
  assert(!authErr.isForbidden)
  assert(authErr.isClientError)
  assert(!authErr.isServerError)

  const abortErr = new DOMException('The user aborted a request.', 'AbortError')
  const normalizedAbort = normalizeError(abortErr)
  assert(normalizedAbort.isAborted)
})

// -------------------------------------------------------------
// Test 4: Verify User Normalization and Role Checker
// -------------------------------------------------------------
await runAsyncTest('Verify user identity normalization and hasRole checks', async () => {
  const { normalizeUser, hasRole } = await import('../src/context/authUtils.js')

  const backendUser = {
    user_id: 'uuid-1234',
    email: 'owner@swiftletcare.com',
    fullName: 'Nguyen Van A',
    roles: ['FARM_OWNER', 'TECHNICIAN'],
  }

  const normalized = normalizeUser(backendUser)
  assert.strictEqual(normalized.id, 'uuid-1234')
  assert.strictEqual(normalized.name, 'Nguyen Van A')
  assert.strictEqual(normalized.role, 'FARM_OWNER')
  assert.deepStrictEqual(normalized.roles, ['FARM_OWNER', 'TECHNICIAN'])

  assert(hasRole(normalized, 'FARM_OWNER'))
  assert(hasRole(normalized, 'TECHNICIAN'))
  assert(!hasRole(normalized, 'ADMIN'))
  assert(hasRole(normalized, ['ADMIN', 'FARM_OWNER']))
})

// -------------------------------------------------------------
// Test 5: Verify Fail-Closed API behavior in Real Mode
// -------------------------------------------------------------
await runAsyncTest('Verify client request throws ApiError when endpoint is unreachable (No silent mock fallback)', async () => {
  const { request } = await import('../src/api/client.js')

  try {
    // Calling an unreachable endpoint on a closed port
    await request('http://127.0.0.1:59999/api/unreachable', { timeout: 1000 })
    assert.fail('Request should have thrown ApiError')
  } catch (err) {
    assert(err.isNetworkError || err.isTimeout, `Expected network error or timeout, got: ${err.message}`)
  }
})

// -------------------------------------------------------------
// Test 6: Verify Telemetry Normalization & Header Formatting
// -------------------------------------------------------------
await runAsyncTest('Verify telemetry adapter normalizes units and formats header tokens', async () => {
  const { normalizeTelemetry, formatHeaderEnvironment } = await import('../src/features/telemetry/adapters/telemetryAdapter.js')

  const raw = {
    metrics: {
      temperature: 29.42,
      humidity: 82.1,
      co2: 650,
      light: 140,
    },
  }

  const normalized = normalizeTelemetry(raw)
  assert.strictEqual(normalized.temperature, 29.42)
  assert.strictEqual(normalized.humidity, 82.1)
  assert.strictEqual(normalized.co2, 650)
  assert.strictEqual(normalized.light, 140)

  const formatted = formatHeaderEnvironment(normalized)
  assert.strictEqual(formatted.length, 4)
  assert.strictEqual(formatted[0].value, '29.4°C')
  assert.strictEqual(formatted[1].value, '82%')
  assert.strictEqual(formatted[2].value, '650 ppm')
  assert.strictEqual(formatted[3].value, '140 lux')
})

// -------------------------------------------------------------
// Test 7: Verify Async Feedback UI Primitives Exist and Export
// -------------------------------------------------------------
runTest('Verify async UX components (LoadingSpinner, Skeleton, EmptyState, ErrorMessage, ErrorBoundary) exist and export', () => {
  const feedbackDir = path.join(srcDir, 'components/common/feedback')
  const indexContent = fs.readFileSync(path.join(feedbackDir, 'index.js'), 'utf-8')

  const requiredExports = [
    'LoadingSpinner',
    'Skeleton',
    'SkeletonCard',
    'TableSkeleton',
    'EmptyState',
    'ErrorMessage',
    'ErrorBoundary',
  ]

  for (const exp of requiredExports) {
    assert(indexContent.includes(exp), `feedback/index.js must export "${exp}"`)
  }

  // Verify component files and CSS exist
  const files = [
    'LoadingSpinner.jsx', 'LoadingSpinner.css',
    'Skeleton.jsx', 'Skeleton.css',
    'EmptyState.jsx', 'EmptyState.css',
    'ErrorMessage.jsx', 'ErrorMessage.css',
    'ErrorBoundary.jsx', 'ErrorBoundary.css',
  ]
  for (const file of files) {
    assert(fs.existsSync(path.join(feedbackDir, file)), `File "${file}" must exist in feedback/`)
  }
})

console.log('\n=================================================================')
console.log(`TOTAL TESTS: ${passedTests + failedTests} | PASSED: ${passedTests} | FAILED: ${failedTests}`)
console.log('=================================================================\n')

if (failedTests > 0) {
  process.exit(1)
} else {
  process.exit(0)
}
