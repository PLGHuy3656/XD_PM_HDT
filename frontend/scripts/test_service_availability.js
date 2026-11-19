import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  SERVICE_STATE,
  classifyServiceError,
  resolveServiceState,
} from '../src/api/serviceStatus.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const srcRoot = path.resolve(__dirname, '../src')

let passed = 0
function test(name, fn) {
  fn()
  passed += 1
  console.log(`[PASS] ${name}`)
}

test('classifyServiceError maps 502/503/504 and network errors to UNAVAILABLE', () => {
  assert.equal(classifyServiceError({ status: 503, message: 'Upstream service unreachable' }), SERVICE_STATE.UNAVAILABLE)
  assert.equal(classifyServiceError({ status: 502 }), SERVICE_STATE.UNAVAILABLE)
  assert.equal(classifyServiceError({ code: 'NETWORK_ERROR' }), SERVICE_STATE.UNAVAILABLE)
  assert.equal(classifyServiceError({ code: 'TIMEOUT' }), SERVICE_STATE.UNAVAILABLE)
})

test('classifyServiceError maps 400/500 to ERROR and ignores ABORTED', () => {
  assert.equal(classifyServiceError({ status: 400, message: 'Bad Request' }), SERVICE_STATE.ERROR)
  assert.equal(classifyServiceError({ status: 500, message: 'Internal error' }), SERVICE_STATE.ERROR)
  assert.equal(classifyServiceError({ code: 'ABORTED' }), null)
})

test('resolveServiceState distinguishes all 6 states cleanly including recovery', () => {
  assert.equal(resolveServiceState({ loading: true, error: null, hasData: false }), SERVICE_STATE.LOADING)
  assert.equal(
    resolveServiceState({ loading: false, error: { status: 503 }, hasData: false }),
    SERVICE_STATE.UNAVAILABLE,
  )
  // After service recovers and returns empty list:
  assert.equal(
    resolveServiceState({ loading: false, error: null, hasData: false, isEmpty: true }),
    SERVICE_STATE.EMPTY,
  )
  // After service recovers and returns real data:
  assert.equal(
    resolveServiceState({ loading: false, error: null, hasData: true }),
    SERVICE_STATE.AVAILABLE,
  )
  // Unknown when not loaded and no info:
  assert.equal(
    resolveServiceState({ loading: false, error: null, hasData: false, isEmpty: false }),
    SERVICE_STATE.UNKNOWN,
  )
})

test('EnvironmentControlPage uses real iotState, separates activeView from verifiedMode, and shows Chưa xác định chế độ', () => {
  const src = fs.readFileSync(
    path.join(srcRoot, 'pages/farm-owner/Environment/EnvironmentControlPage.jsx'),
    'utf8',
  )
  assert.ok(src.includes('SERVICE_STATE.UNAVAILABLE'))
  assert.ok(src.includes('Chưa xác định chế độ'))
  assert.ok(src.includes('verifiedMode'))
  assert.ok(src.includes("activeView === 'AUTO' ?"))
  assert.ok(src.includes('iotUnavailable'))
  assert.ok(!src.includes('{!USE_MOCK && (\n          <ErrorMessage'))
})

console.log(`\nService availability tests: ${passed}/${passed} PASSED`)
