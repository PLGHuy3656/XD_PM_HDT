// INT02 UI sync: shared AI camera state + farm IoT state resolvers (node scripts/test_int02_dashboard_sync.mjs)
import assert from 'node:assert/strict'
import { resolveAiCameraView } from '../src/features/cameras/aiCameraState.js'
import { resolveIotState } from '../src/features/devices/deviceStatus.js'

let pass = 0
const t = (name, fn) => { fn(); pass++; console.log(`[PASS] ${name}`) }
const ai = (o) => ({ sessionState: 'ACTIVE', status: null, counts: null, detection: null, webcam: { state: 'OFF' }, ...o })
const st = (status, sourceMode) => ({ status, sourceMode, modelVersion: 'best', trackerType: 'bytetrack', fps: 10, processedFrames: 5 })
const counts = { cameraId: 'CAM-01', entryCount: 3, exitCount: 2 }

t('no session (404) => OFFLINE, no numbers', () => {
  const v = resolveAiCameraView(ai({ sessionState: 'NONE', counts }), 'CAM-01')
  assert.equal(v.sourceMode, 'OFFLINE'); assert.equal(v.counts, null); assert.equal(v.running, false)
})
t('stopped pipeline keeps last counts hidden', () => {
  const v = resolveAiCameraView(ai({ status: st('OFFLINE', 'DEMO_VIDEO'), counts }), 'CAM-01')
  assert.equal(v.sourceMode, 'OFFLINE'); assert.equal(v.counts, null); assert.deepEqual(v.detections, [])
})
t('demo running => DEMO_VIDEO with counts', () => {
  const v = resolveAiCameraView(ai({ status: st('ONLINE', 'DEMO_VIDEO'), counts }), 'CAM-01')
  assert.equal(v.sourceMode, 'DEMO_VIDEO'); assert.equal(v.counts.entryCount, 3)
})
t('webcam running => LOCAL_CAMERA', () => {
  assert.equal(resolveAiCameraView(ai({ status: st('ONLINE', 'LOCAL_CAMERA') }), 'CAM-01').sourceMode, 'LOCAL_CAMERA')
})
t('counts of another camera never shown', () => {
  const v = resolveAiCameraView(ai({ status: st('ONLINE', 'DEMO_VIDEO'), counts: { ...counts, cameraId: 'CAM-02' } }), 'CAM-01')
  assert.equal(v.counts, null)
})
t('AI unreachable / forbidden => UNAVAILABLE', () => {
  assert.equal(resolveAiCameraView(ai({ sessionState: 'UNAVAILABLE', counts }), 'CAM-01').sourceMode, 'UNAVAILABLE')
  const f = resolveAiCameraView(ai({ sessionState: 'FORBIDDEN' }), 'CAM-01')
  assert.equal(f.sourceMode, 'UNAVAILABLE'); assert.ok(f.error)
})
t('runtime ERROR surfaces error, not running', () => {
  const v = resolveAiCameraView(ai({ status: { ...st('ERROR', 'DEMO_VIDEO'), errorMessage: 'source lost' } }), 'CAM-01')
  assert.equal(v.running, false); assert.equal(v.error, 'source lost')
})
t('IoT: cameras only => NONE', () => assert.equal(resolveIotState([{ type: 'CAMERA', status: 'UNKNOWN' }], 'ok'), 'NONE'))
t('IoT: online sensor => ONLINE', () => assert.equal(resolveIotState([{ type: 'SENSOR', status: 'ONLINE' }], 'ok'), 'ONLINE'))
t('IoT: never heartbeat => UNKNOWN', () => assert.equal(resolveIotState([{ type: 'SENSOR', status: 'UNKNOWN' }], 'empty'), 'UNKNOWN'))
t('IoT: offline => OFFLINE', () => assert.equal(resolveIotState([{ type: 'SENSOR', status: 'OFFLINE' }], 'empty'), 'OFFLINE'))
t('IoT: service down => UNAVAILABLE', () => assert.equal(resolveIotState([{ type: 'SENSOR', status: 'ONLINE' }], 'unavailable'), 'UNAVAILABLE'))
console.log(`INT02 dashboard sync tests: ${pass}/12 PASSED`)
