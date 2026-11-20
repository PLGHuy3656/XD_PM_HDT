// INT02 UI sync: shared AI camera state + farm IoT state resolvers (node scripts/test_int02_dashboard_sync.mjs)
import assert from 'node:assert/strict'
import { resolveAiCameraView, mapAiEventToRow, AI_SOURCE_META } from '../src/features/cameras/aiCameraState.js'
import { validateRegistration, REGISTERABLE_DEVICE_TYPES, registrationErrorText } from '../src/features/devices/deviceRegistration.js'
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
t('uploaded video running => UPLOADED_VIDEO', () => {
  assert.equal(resolveAiCameraView(ai({ status: st('ONLINE', 'UPLOADED_VIDEO'), counts }), 'CAM-01').sourceMode, 'UPLOADED_VIDEO')
})
t('uploaded video completed keeps its own final result', () => {
  const v = resolveAiCameraView(ai({ status: { ...st('OFFLINE', 'UPLOADED_VIDEO'), sessionEnded: 'COMPLETED' }, counts }), 'CAM-01')
  assert.equal(v.phase, 'COMPLETED'); assert.equal(v.counts.entryCount, 3); assert.deepEqual(v.detections, [])
})
t('uploaded video stopped (not completed) => OFFLINE, no numbers', () => {
  const v = resolveAiCameraView(ai({ status: st('OFFLINE', 'UPLOADED_VIDEO'), counts }), 'CAM-01')
  assert.equal(v.sourceMode, 'OFFLINE'); assert.equal(v.counts, null)
})
t('synthetic fixture labelled SYNTHETIC TEST', () => assert.equal(AI_SOURCE_META.DEMO_VIDEO.label, 'SYNTHETIC TEST'))
t('AIEvent row: names from Management, confidence from event, no invented status', () => {
  const r = mapAiEventToRow({ eventId: 'E1', cameraId: 'CAM-01', zoneId: 'Z1', class: 'rat', confidence: 0.834, detectedAt: '2026-11-20T10:00:00Z' },
    { cameraNames: { 'CAM-01': 'CAM-01 · Lối vào' }, zoneNames: { Z1: 'Tầng 1' } })
  assert.equal(r.location, 'CAM-01 · Lối vào · Tầng 1'); assert.equal(r.confidence, 83); assert.equal(r.status, null)
  assert.equal(mapAiEventToRow({ eventId: 'E2', cameraId: 'X', class: 'snake' }).confidence, null)
})
t('registration offers only contract types', () => assert.deepEqual(REGISTERABLE_DEVICE_TYPES.map((x) => x.value), ['ENVIRONMENT_MONITOR', 'CAMERA']))
t('registration validation', () => {
  assert.equal(validateRegistration({ node_id: 'CAM-03', name: 'Cam', device_type: 'CAMERA' }), null)
  assert.ok(validateRegistration({ node_id: 'CAM 03', name: 'Cam', device_type: 'CAMERA' }))
  assert.ok(validateRegistration({ node_id: '../x', name: 'Cam', device_type: 'CAMERA' }))
  assert.ok(validateRegistration({ node_id: 'SPK-01', name: 'Loa', device_type: 'SPEAKER' }))
  assert.ok(validateRegistration({ node_id: 'SWC-1', name: '', device_type: 'ENVIRONMENT_MONITOR' }))
  assert.match(registrationErrorText('Device with node_id X already exists'), /đã tồn tại/)
})
console.log(`INT02 dashboard sync tests: ${pass}/19 PASSED`)
