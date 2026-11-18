/**
 * SwiftletCare CP12-A Real Authentication & API Gateway Live Integration Test Suite
 * Validates:
 * 1. Gateway CORS Preflight (OPTIONS /api/auth/login)
 * 2. Real Login (POST /api/auth/login) via Gateway -> Management Service
 * 3. Invalid Credentials Rejection (401 Unauthorized)
 * 4. Token Inspection & User Identity (UUID, Roles, Expire)
 * 5. Protected Introspection (GET /api/auth/me) with Bearer token
 * 6. Expired / Invalid Token Rejection (401 Unauthorized)
 * 7. RBAC Forbidden Enforcement (403 Forbidden for unauthorized roles)
 * 8. Real Mode Fail-Closed Verification (No silent mock fallback)
 * 9. Client-side Logout & Session Cleanup
 *
 * NOTE: Passwords and full JWT signatures are strictly redacted from test output.
 */

import assert from 'node:assert'
import { authApi } from '../src/api/modules/authApi.js'
import { apiClient, setAuthToken, request } from '../src/api/client.js'
import { normalizeUser, hasRole } from '../src/context/authUtils.js'

console.log('=================================================================')
console.log('SWIFTLETCARE — CP12-A REAL AUTHENTICATION & GATEWAY LIVE TEST')
console.log('=================================================================\n')

let passedTests = 0
let failedTests = 0

async function runTest(name, fn) {
  try {
    await fn()
    console.log(`[PASS] ${name}`)
    passedTests++
  } catch (err) {
    console.error(`[FAIL] ${name}:`, err.message)
    failedTests++
  }
}

const GATEWAY_URL = 'http://127.0.0.1:8000'
const DEMO_EMAIL = 'owner.a.demo@nestmate.dev'
const DEMO_PASSWORD = requireTestPassword()

// -----------------------------------------------------------------
// Test 1: Gateway CORS Preflight Handling
// -----------------------------------------------------------------
await runTest('CORS Preflight: Gateway handles OPTIONS /api/auth/login with allow-origin', async () => {
  const res = await fetch(`${GATEWAY_URL}/api/auth/login`, {
    method: 'OPTIONS',
    headers: {
      'Origin': 'http://localhost:5173',
      'Access-Control-Request-Method': 'POST',
      'Access-Control-Request-Headers': 'content-type',
    },
  })

  assert.strictEqual(res.status, 200, `Expected 200 for CORS preflight, got ${res.status}`)
  const allowOrigin = res.headers.get('access-control-allow-origin')
  assert(
    allowOrigin === 'http://localhost:5173' || allowOrigin === '*',
    `Expected allow-origin to include client, got ${allowOrigin}`,
  )
})

// -----------------------------------------------------------------
// Test 2: Real Login with Valid Credentials via Gateway
// -----------------------------------------------------------------
let testToken = null
let testUser = null

await runTest('Live Login: POST /api/auth/login authenticates via Gateway and returns JWT', async () => {
  const response = await authApi.login({
    email: DEMO_EMAIL,
    password: DEMO_PASSWORD,
  })

  assert(response, 'Response must not be empty')
  assert(response.access_token, 'Response must contain access_token')
  assert.strictEqual(response.token_type, 'bearer')
  assert(typeof response.expires_in === 'number', 'expires_in must be a number')
  assert(response.user, 'Response must contain user object')
  assert.strictEqual(response.user.email, DEMO_EMAIL)
  assert(response.user.roles.includes('FARM_OWNER'), 'User must have FARM_OWNER role')

  testToken = response.access_token
  testUser = normalizeUser(response.user)

  assert.strictEqual(testUser.id, 'd632d08d-2a47-46f0-8798-83fd733024c3')
  assert(hasRole(testUser, 'FARM_OWNER'))
  assert(!hasRole(testUser, 'ADMIN'))

  // Verify token is valid JWT structure without logging full secret
  const parts = testToken.split('.')
  assert.strictEqual(parts.length, 3, 'Token must be a valid 3-part JWT')
  console.log('       [Evidence] User UUID:', testUser.id, '| Role:', testUser.role, '| Token length:', testToken.length)
})

// -----------------------------------------------------------------
// Test 3: Invalid Credentials Denied (401)
// -----------------------------------------------------------------
await runTest('Negative Test: Invalid password returns 401 Unauthorized', async () => {
  try {
    await authApi.login({
      email: DEMO_EMAIL,
      password: 'WrongPassword999!',
    })
    assert.fail('Should have thrown ApiError for invalid credentials')
  } catch (err) {
    assert(err.isUnauthorized, `Expected 401 Unauthorized, got: ${err.status}`)
    assert.strictEqual(err.status, 401)
  }
})

// -----------------------------------------------------------------
// Test 4: Protected User Introspection (GET /api/auth/me) with Bearer Token
// -----------------------------------------------------------------
await runTest('Protected Introspection: GET /api/auth/me returns current user profile with JWT', async () => {
  assert(testToken, 'Precondition: testToken must exist')
  setAuthToken(testToken)

  const profile = await authApi.getProfile()
  assert(profile, 'Profile response must not be empty')
  assert.strictEqual(profile.email, DEMO_EMAIL)
  assert.strictEqual(profile.id, 'd632d08d-2a47-46f0-8798-83fd733024c3')
  assert.strictEqual(profile.status, 'ACTIVE')
  assert(profile.roles.includes('FARM_OWNER'))
})

// -----------------------------------------------------------------
// Test 5: Invalid / Tampered Token Denied (401)
// -----------------------------------------------------------------
await runTest('Negative Test: Tampered JWT token rejected with 401 Unauthorized', async () => {
  const forgedToken = testToken.slice(0, -6) + 'xxxxxx'
  try {
    await apiClient.get('/api/auth/me', {
      headers: { Authorization: `Bearer ${forgedToken}` },
      skipAuth: true,
    })
    assert.fail('Tampered token should have been rejected')
  } catch (err) {
    assert(err.isUnauthorized, `Expected 401 Unauthorized, got: ${err.status}`)
    assert.strictEqual(err.status, 401)
  }
})

// -----------------------------------------------------------------
// Test 6: Role-Based Access Control (403 Forbidden)
// -----------------------------------------------------------------
await runTest('RBAC Enforcement: Farm Owner token rejected with 403 on Admin endpoint', async () => {
  setAuthToken(testToken)
  try {
    // Attempting admin-only technician assignment route with Farm Owner token
    await apiClient.post(
      '/api/technicians/15e6f30f-350a-4c66-b4be-e22ab03b85dc/farms/DEMO-FARM-01/assign',
      {},
    )
    assert.fail('Non-admin user should be forbidden')
  } catch (err) {
    assert(err.isForbidden, `Expected 403 Forbidden, got: ${err.status}`)
    assert.strictEqual(err.status, 403)
  }
})

// -----------------------------------------------------------------
// Test 7: Fail-Closed Real Mode (No Mock Fallback)
// -----------------------------------------------------------------
await runTest('Fail-Closed: Requesting non-existent Gateway endpoint fails with 404 (No mock fallback)', async () => {
  try {
    await apiClient.get('/api/non-existent-endpoint')
    assert.fail('Should fail on 404')
  } catch (err) {
    assert(err.isNotFound || err.isClientError, `Expected 404, got: ${err.status}`)
    assert.strictEqual(err.status, 404)
  }
})

// -----------------------------------------------------------------
// Test 8: Logout and Session Cleanup
// -----------------------------------------------------------------
await runTest('Session Cleanup: Clearing auth token revokes authorization for subsequent calls', async () => {
  setAuthToken(null)

  try {
    await authApi.getProfile()
    assert.fail('Introspection without token should fail')
  } catch (err) {
    assert(err.isUnauthorized, `Expected 401 without token, got: ${err.status}`)
  }
})

console.log('\n=================================================================')
console.log(`TOTAL LIVE TESTS: ${passedTests + failedTests} | PASSED: ${passedTests} | FAILED: ${failedTests}`)
console.log('=================================================================\n')

if (failedTests > 0) {
  process.exit(1)
} else {
  process.exit(0)
}

// CP13 hardening R1: no default demo password. Fail fast when it is not provided.
function requireTestPassword() {
  const value = process.env.SWC_TEST_PASSWORD
  if (!value) {
    console.error('SWC_TEST_PASSWORD is required (no default password is bundled with this script).')
    process.exit(2)
  }
  return value
}
