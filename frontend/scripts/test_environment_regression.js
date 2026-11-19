import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { getMetricState } from '../src/components/features/farm-owner/environment/metricState.js'
import { normalizeTelemetry } from '../src/features/telemetry/adapters/telemetryAdapter.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const srcRoot = path.resolve(__dirname, '../src')

let passed = 0
function test(name, fn) {
  fn()
  passed += 1
  console.log(`[PASS] ${name}`)
}

// 1. Missing/null telemetry must NOT show "Dưới ngưỡng" or "Bình thường"
test('getMetricState returns "Chưa có dữ liệu" when value is null or hasData is false', () => {
  const nullTemp = getMetricState({ label: 'Nhiệt độ', value: null, hasData: false, safeMin: 27, safeMax: 31 })
  assert.equal(nullTemp.label, 'Chưa có dữ liệu')
  assert.equal(nullTemp.className, 'offline')

  const missingCo2 = getMetricState({ label: 'CO₂', value: undefined, safeMin: 400, safeMax: 1000 })
  assert.equal(missingCo2.label, 'Chưa có dữ liệu')
  assert.equal(missingCo2.className, 'offline')
})

// 2. Valid telemetry within and outside thresholds evaluates properly
test('getMetricState evaluates valid telemetry accurately against safeMin/safeMax', () => {
  assert.equal(
    getMetricState({ label: 'Nhiệt độ', value: 28.5, safeMin: 27, safeMax: 31 }).label,
    'Bình thường',
  )
  assert.equal(
    getMetricState({ label: 'Nhiệt độ', value: 25.0, safeMin: 27, safeMax: 31 }).label,
    'Dưới ngưỡng',
  )
  assert.equal(
    getMetricState({ label: 'Độ ẩm', value: 94, safeMin: 75, safeMax: 90 }).label,
    'Vượt ngưỡng',
  )
})

// 3. Telemetry adapter in REAL mode returns null or null fields when API returns null/empty (never fabricates 0)
test('normalizeTelemetry does not fabricate 0 or mock values in REAL mode', () => {
  assert.equal(normalizeTelemetry(null, false), null)
  const empty = normalizeTelemetry({}, false)
  assert.equal(empty.temperature, null)
  assert.equal(empty.humidity, null)
  assert.equal(empty.co2, null)
  assert.equal(empty.light, null)

  const valid = normalizeTelemetry({ temperature: 28.4, humidity: 82, co2: 610, light: 95 }, false)
  assert.equal(valid.temperature, 28.4)
  assert.equal(valid.humidity, 82)
  assert.equal(valid.co2, 610)
  assert.equal(valid.light, 95)
})

// 4. Static checks: EnvironmentPage & EnvironmentControlPage CSS parity and no mock actuator leaks
test('EnvironmentPage uses .environment-metric-grid and active/onClick props on MetricCard', () => {
  const envSrc = fs.readFileSync(path.join(srcRoot, 'pages/farm-owner/Environment/EnvironmentPage.jsx'), 'utf8')
  assert.ok(envSrc.includes('className="environment-metric-grid"'))
  assert.ok(envSrc.includes('active={selectedMetric === key}'))
  assert.ok(envSrc.includes('onClick={() => setSelectedMetric(key)}'))
  assert.ok(!envSrc.includes('isSelected={selectedMetric === key}'))
})

test('EnvironmentControlPage disables control actions when IoT Control is unavailable and omits static Fail-safe card', () => {
  const ctrlSrc = fs.readFileSync(path.join(srcRoot, 'pages/farm-owner/Environment/EnvironmentControlPage.jsx'), 'utf8')
  assert.ok(ctrlSrc.includes('iotControlAvailable'))
  assert.ok(ctrlSrc.includes('disabled={!iotControlAvailable}'))
  assert.ok(ctrlSrc.includes('Chưa kết nối dịch vụ IoT'))
  assert.ok(ctrlSrc.includes('className="environment-control-page"'))
  assert.ok(!ctrlSrc.includes('control-fail-safe-card'))
  assert.ok(!ctrlSrc.includes('FAIL-SAFE'))
})

console.log(`\nEnvironment regression tests: ${passed}/${passed} PASSED`)
