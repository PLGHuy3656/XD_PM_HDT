import assert from 'node:assert/strict'
import {
  MAX_INSPECTION_RESULT_LENGTH,
  availableActions,
  errorMessage,
  validateInspectionResult,
} from '../src/features/inspections/inspectionModel.js'

// 1. Short valid Vietnamese / English results ("ổn", "OK", "đạt") must be accepted
for (const validText of ['ổn', '  ổn  ', 'OK', 'đạt', 'Đã kiểm tra xong']) {
  const res = validateInspectionResult(validText)
  assert.equal(res.valid, true, `Expected "${validText}" to be valid`)
  assert.equal(res.trimmed, validText.trim())
  assert.equal(res.message, null)
}

// 2. Empty or whitespace-only results must be rejected with clear Vietnamese guidance
for (const invalidText of ['', '   ', '\n\t  ', null, undefined]) {
  const res = validateInspectionResult(invalidText)
  assert.equal(res.valid, false, `Expected ${JSON.stringify(invalidText)} to be invalid`)
  assert.ok(res.message && res.message.includes('Vui lòng nhập kết quả kiểm tra'), 'Expected clear Vietnamese hint')
}

// 3. Over-max-length results must be rejected with clear message
const tooLong = 'a'.repeat(MAX_INSPECTION_RESULT_LENGTH + 1)
const longRes = validateInspectionResult(tooLong)
assert.equal(longRes.valid, false)
assert.ok(longRes.message && longRes.message.includes(String(MAX_INSPECTION_RESULT_LENGTH)))

// 4. RBAC: assigned technician gets "complete" only in IN_PROGRESS; unassigned tech or owner does not
const inProgressReq = {
  id: 'req-1',
  status: 'IN_PROGRESS',
  assigned_technician_id: 'tech-1',
}
assert.deepEqual(availableActions(inProgressReq, { id: 'tech-1', role: 'TECHNICIAN' }), ['complete'])
assert.deepEqual(availableActions(inProgressReq, { id: 'tech-2', role: 'TECHNICIAN' }), [])
assert.deepEqual(availableActions(inProgressReq, { id: 'owner-1', role: 'FARM_OWNER' }), [])

// 5. 422 validation error message is readable
assert.ok(errorMessage({ status: 422 }, 'fallback').includes('Dữ liệu nhập chưa hợp lệ'))

console.log('PASS: inspection completion validation & RBAC regression checks (5/5)')
