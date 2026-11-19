import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const srcRoot = path.resolve(__dirname, '../src')

let passed = 0
function test(name, fn) {
  fn()
  passed += 1
  console.log(`[PASS] ${name}`)
}

test('DevicesPage passes exact zoneOptions, zoneId, onZoneChange, onConfirm props to DeviceAssignmentModal', () => {
  const src = fs.readFileSync(path.join(srcRoot, 'pages/technician/Devices/DevicesPage.jsx'), 'utf8')
  assert.ok(src.includes('zoneOptions={assignmentZoneOptions}'))
  assert.ok(src.includes('zoneId={assignmentZoneId}'))
  assert.ok(src.includes('onZoneChange={setAssignmentZoneId}'))
  assert.ok(src.includes('onConfirm={handleSaveAssignment}'))
  assert.ok(!src.includes('zones={assignmentZoneOptions}'))
})

test('DeviceAssignmentModal defaults zoneOptions safely and has no mock copy', () => {
  const src = fs.readFileSync(
    path.join(srcRoot, 'components/features/technician/devices/DeviceAssignmentModal.jsx'),
    'utf8',
  )
  assert.ok(src.includes('zoneOptions = []'))
  assert.ok(src.includes('Gán / đổi khu vực'))
  assert.ok(!src.includes('thao tác mock'))
})

test('DeviceTable uses "Gán / đổi khu vực" instead of "Chuyển Zone"', () => {
  const src = fs.readFileSync(
    path.join(srcRoot, 'components/features/technician/devices/DeviceTable.jsx'),
    'utf8',
  )
  assert.ok(src.includes('Gán / đổi khu vực'))
  assert.ok(!src.includes('Chuyển Zone'))
})

console.log(`\nTechnician Devices regression tests: ${passed}/${passed} PASSED`)
