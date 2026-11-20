/**
 * INT02 UI sync: one resolver for the AI camera state, shared by the Owner Dashboard and the
 * Swiftlets (Giám sát chim yến) page so both always show the same camera the same way.
 *
 *   DEMO_VIDEO     – SYNTHETIC TEST: geometric fixture replayed by the AI Service (not real birds)
 *   UPLOADED_VIDEO – a local MP4 the user uploaded, processed once by the real pipeline
 *   LOCAL_CAMERA – frames from this computer's webcam (only while the user keeps it on)
 *   LAN_CAMERA   – network camera (not provisioned in INT02)
 *   OFFLINE      – camera registered, AI reachable, but no session is running (valid state)
 *   UNAVAILABLE  – AI Service unreachable / not authorised: nothing is shown in its place
 *
 * Counts and detections are only exposed while a session is running — never from a
 * stopped session, never invented.
 */
export const AI_SOURCE_META = {
  DEMO_VIDEO: { label: 'SYNTHETIC TEST', short: 'Video kiểm thử tổng hợp', className: 'demo', note: 'Video kiểm thử hình học tổng hợp (synthetic) — chỉ để kiểm tra hệ thống, không phải video chim yến thật.' },
  UPLOADED_VIDEO: { label: 'UPLOADED VIDEO', short: 'Video từ máy', className: 'lan', note: 'Video người dùng tải lên, được AI xử lý một lượt bằng model best.pt; file tạm bị xóa khi phiên kết thúc.' },
  LOCAL_CAMERA: { label: 'LOCAL CAMERA', short: 'Webcam', className: 'local', note: 'Webcam của máy này — khung hình chỉ được gửi khi phiên đang bật, không lưu lại.' },
  LAN_CAMERA: { label: 'LAN CAMERA', short: 'Camera LAN', className: 'lan', note: 'Camera qua mạng LAN.' },
  OFFLINE: { label: 'OFFLINE', short: 'Chưa có phiên', className: 'unavailable', note: 'Camera chưa có phiên AI. Tại trang Giám sát chim yến: tải "Video từ máy", bật webcam hoặc chạy video kiểm thử tổng hợp.' },
  UNAVAILABLE: { label: 'UNAVAILABLE', short: 'Không khả dụng', className: 'unavailable', note: 'Không kết nối được AI Service. Không có số liệu nào được hiển thị thay thế.' },
}

export const AI_RUNTIME_LABEL = {
  STARTING: 'Đang khởi động',
  ONLINE: 'Đang xử lý',
  DEGRADED: 'Suy giảm',
  OFFLINE: 'Đã dừng',
  ERROR: 'Lỗi',
}

export const AI_CLASS_LABEL = { swiftlet: 'Chim yến', rat: 'Chuột', snake: 'Rắn' }

const RUNNING = ['STARTING', 'ONLINE', 'DEGRADED']

export function resolveAiCameraView(ai, cameraId) {
  if (!ai || !cameraId) {
    return { running: false, completed: false, phase: 'IDLE', sourceMode: 'OFFLINE', source: AI_SOURCE_META.OFFLINE, counts: null, detections: [], status: null, runtimeLabel: '--', error: null }
  }
  const status = ai.status
  const unavailable = ai.sessionState === 'UNAVAILABLE' || ai.sessionState === 'FORBIDDEN'
  const running = ai.sessionState === 'ACTIVE' && Boolean(status) && RUNNING.includes(status.status)
  // An uploaded video that was processed to the end keeps showing ITS final result (same session)
  const completed =
    !running && ai.sessionState === 'ACTIVE' && status?.sourceMode === 'UPLOADED_VIDEO' && status?.sessionEnded === 'COMPLETED'
  const sourceMode = unavailable ? 'UNAVAILABLE' : running || completed ? status.sourceMode || 'LAN_CAMERA' : 'OFFLINE'
  const runtimeError = status?.status === 'ERROR' ? status.errorMessage || status.errorCode || 'AI runtime lỗi' : null
  return {
    running,
    completed,
    phase: unavailable ? 'UNAVAILABLE' : running ? 'RUNNING' : completed ? 'COMPLETED' : 'IDLE',
    sourceMode,
    source: AI_SOURCE_META[sourceMode] || AI_SOURCE_META.UNAVAILABLE,
    counts: (running || completed) && ai.counts && ai.counts.cameraId === cameraId ? ai.counts : null,
    detections: running ? ai.detection?.detections || [] : [],
    status: running || completed ? status : null,
    runtimeLabel: unavailable ? 'Không khả dụng' : completed ? 'Đã xử lý xong video' : status ? AI_RUNTIME_LABEL[status.status] || status.status : 'Chưa chạy',
    error:
      ai.sessionState === 'FORBIDDEN'
        ? 'Không có quyền truy cập camera này.'
        : ai.sessionState === 'ERROR'
          ? ai.error || 'Lỗi khi đọc trạng thái AI.'
          : runtimeError,
  }
}

/** INT02-F03: canonical AIEvent (PREDATOR_DETECTED) -> table row. Names come from Management
 *  (camera registry / zones); confidence only from the event; the V1 contract has no status. */
export function mapAiEventToRow(event, { cameraNames = {}, zoneNames = {} } = {}) {
  const cls = event.class || event.cls
  const camera = cameraNames[event.cameraId] || event.cameraId
  const zone = event.zoneId ? zoneNames[event.zoneId] || event.zoneId : null
  return {
    id: event.eventId,
    type: 'PREDATOR',
    title: `Phát hiện ${AI_CLASS_LABEL[cls] || cls || 'thiên địch'}`,
    location: zone ? `${camera} · ${zone}` : camera,
    detectedAt: event.detectedAt,
    confidence: typeof event.confidence === 'number' ? Math.round(event.confidence * 100) : null,
    status: null,
  }
}
