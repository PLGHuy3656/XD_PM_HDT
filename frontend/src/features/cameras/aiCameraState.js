/**
 * INT02 UI sync: one resolver for the AI camera state, shared by the Owner Dashboard and the
 * Swiftlets (Giám sát chim yến) page so both always show the same camera the same way.
 *
 *   DEMO_VIDEO   – AI Service replays the synthetic demo fixture through the real pipeline
 *   LOCAL_CAMERA – frames from this computer's webcam (only while the user keeps it on)
 *   LAN_CAMERA   – network camera (not provisioned in INT02)
 *   OFFLINE      – camera registered, AI reachable, but no session is running (valid state)
 *   UNAVAILABLE  – AI Service unreachable / not authorised: nothing is shown in its place
 *
 * Counts and detections are only exposed while a session is running — never from a
 * stopped session, never invented.
 */
export const AI_SOURCE_META = {
  DEMO_VIDEO: { label: 'DEMO VIDEO', short: 'Video demo', className: 'demo', note: 'Video mẫu tổng hợp (synthetic) được AI Service xử lý — không phải camera thật.' },
  LOCAL_CAMERA: { label: 'LOCAL CAMERA', short: 'Webcam', className: 'local', note: 'Webcam của máy này — khung hình chỉ được gửi khi phiên đang bật, không lưu lại.' },
  LAN_CAMERA: { label: 'LAN CAMERA', short: 'Camera LAN', className: 'lan', note: 'Camera qua mạng LAN.' },
  OFFLINE: { label: 'OFFLINE', short: 'Chưa có phiên', className: 'unavailable', note: 'Camera chưa có phiên AI. Chọn "Chạy video demo" hoặc bật webcam tại trang Giám sát chim yến.' },
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
    return { running: false, sourceMode: 'OFFLINE', source: AI_SOURCE_META.OFFLINE, counts: null, detections: [], status: null, runtimeLabel: '--', error: null }
  }
  const status = ai.status
  const unavailable = ai.sessionState === 'UNAVAILABLE' || ai.sessionState === 'FORBIDDEN'
  const running = ai.sessionState === 'ACTIVE' && Boolean(status) && RUNNING.includes(status.status)
  const sourceMode = unavailable ? 'UNAVAILABLE' : running ? status.sourceMode || 'LAN_CAMERA' : 'OFFLINE'
  const runtimeError = status?.status === 'ERROR' ? status.errorMessage || status.errorCode || 'AI runtime lỗi' : null
  return {
    running,
    sourceMode,
    source: AI_SOURCE_META[sourceMode] || AI_SOURCE_META.UNAVAILABLE,
    counts: running && ai.counts && ai.counts.cameraId === cameraId ? ai.counts : null,
    detections: running ? ai.detection?.detections || [] : [],
    status: running ? status : null,
    runtimeLabel: unavailable ? 'Không khả dụng' : status ? AI_RUNTIME_LABEL[status.status] || status.status : 'Chưa chạy',
    error:
      ai.sessionState === 'FORBIDDEN'
        ? 'Không có quyền truy cập camera này.'
        : ai.sessionState === 'ERROR'
          ? ai.error || 'Lỗi khi đọc trạng thái AI.'
          : runtimeError,
  }
}
