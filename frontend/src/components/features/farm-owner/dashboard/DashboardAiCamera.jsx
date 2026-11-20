import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import EnvironmentSelect from '../../../ui/Select'
import { useCameraAiRuntime } from '../../../../features/cameras/hooks/useCameraAiRuntime.js'
import { AI_CLASS_LABEL, mapAiEventToRow, resolveAiCameraView } from '../../../../features/cameras/aiCameraState.js'
import { useFarmAiEvents } from '../../../../features/cameras/hooks/useFarmAiEvents.js'
import { formatRelativeTime } from '../../../../features/telemetry/provenance.js'
import { USE_MOCK } from '../../../../api/config.js'

/**
 * INT02 UI sync: Owner Dashboard camera block driven by the same AI runtime (via the Gateway)
 * and the same state resolver as the Swiftlets page — never by the device-registry status.
 *
 * - No session yet => OFFLINE with clear guidance (valid state, not an error).
 * - The dashboard can start the demo video; the webcam is only turned on from the Swiftlets
 *   page after the user clicks it and grants permission (never automatically here).
 * - Counts/detections only while a session is running; otherwise "--".
 */
function CameraIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="6" width="18" height="13" rx="2" />
      <circle cx="12" cy="12.5" r="3.5" />
      <path d="M8 6 9.5 4h5L16 6" />
    </svg>
  )
}

function boxStyle(bbox, width, height) {
  if (!bbox || !width || !height) return null
  const x1 = Math.max(0, bbox.x1 / width)
  const y1 = Math.max(0, bbox.y1 / height)
  const x2 = Math.min(1, bbox.x2 / width)
  const y2 = Math.min(1, bbox.y2 / height)
  if (x2 <= x1 || y2 <= y1) return null
  return { left: `${x1 * 100}%`, top: `${y1 * 100}%`, width: `${(x2 - x1) * 100}%`, height: `${(y2 - y1) * 100}%` }
}

const EVENT_STATE_TEXT = {
  LOADING: 'Đang tải…',
  EMPTY: 'Chưa ghi nhận sự kiện AI',
  FORBIDDEN: 'Không có quyền xem sự kiện AI',
  UNAVAILABLE: 'AI Service không khả dụng',
  ERROR: 'Không tải được sự kiện AI',
  IDLE: '--',
}

const REMOTE_NOTE = {
  LOCAL_CAMERA: 'Webcam đang gửi khung hình từ trang Giám sát chim yến của một trình duyệt khác — hình ảnh trực tiếp chỉ hiển thị tại đó.',
  UPLOADED_VIDEO: 'Video tải lên đang được AI phân tích — bản xem trước chỉ có ở trình duyệt đã tải video.',
  DEMO_VIDEO: 'Sơ đồ vị trí phát hiện trên video kiểm thử tổng hợp (không truyền hình ảnh về trình duyệt).',
  LAN_CAMERA: 'Vị trí phát hiện mới nhất từ AI.',
}

function DashboardAiCamera({ cameras = [], farmId = null }) {
  const navigate = useNavigate()
  const aiEvents = useFarmAiEvents(USE_MOCK ? null : farmId, 5)
  const [pickedId, setPickedId] = useState(null)
  const selected = cameras.find((c) => c.id === pickedId) || cameras[0] || null
  const ai = useCameraAiRuntime(selected && !USE_MOCK ? selected.id : null)
  const view = resolveAiCameraView(ai, selected?.id)

  if (!selected) {
    return (
      <div className="dashboard-ai-empty" data-testid="dashboard-camera-none">
        Chưa có camera AI nào được đăng ký cho nhà yến này.
      </div>
    )
  }

  const { running, completed, sourceMode, source, counts, detections, status } = view
  const eventRows = aiEvents.events.slice(0, 3).map((e) =>
    mapAiEventToRow(e, { cameraNames: Object.fromEntries(cameras.map((c) => [c.id, c.code || c.id])) }),
  )
  const index = cameras.findIndex((c) => c.id === selected.id)
  const move = (offset) => setPickedId(cameras[(index + offset + cameras.length) % cameras.length].id)
  const openSwiftlets = () => navigate(`/owner/swiftlets?camera=${encodeURIComponent(selected.id)}`)

  return (
    <div className="live-camera-layout" data-testid="dashboard-ai-camera" data-source-mode={sourceMode}>
      <div className={`camera-preview ${running ? '' : 'camera-preview-offline'}`}>
        <div className="camera-toolbar">
          <div>
            <span className={`camera-live-dot ${running ? '' : 'offline'}`} />
            <span data-testid="dashboard-camera-source">{source.label}</span>
          </div>
          <span>
            {selected.code || selected.id} · {selected.name}
          </span>
        </div>

        {running ? (
          <>
            <div className="camera-placeholder">
              <CameraIcon />
              <strong>AI đang xử lý · {source.short}</strong>
              <span data-testid="dashboard-camera-note">{REMOTE_NOTE[sourceMode] || REMOTE_NOTE.LAN_CAMERA}</span>
            </div>
            {detections.slice(0, 6).map((d, i) => {
              const style = boxStyle(d.bbox, status?.width, status?.height)
              if (!style) return null
              return (
                <div key={`${d.trackId ?? 'x'}-${i}`} className="mock-detection dashboard-ai-box" style={style}>
                  <span>
                    {AI_CLASS_LABEL[d.class] || d.class} · {Math.round(d.confidence * 100)}%
                  </span>
                </div>
              )
            })}
          </>
        ) : (
          <div className="camera-placeholder camera-offline-placeholder" data-testid="dashboard-camera-idle">
            <CameraIcon />
            <strong>
              {sourceMode === 'UNAVAILABLE' ? 'AI Service không khả dụng' : completed ? 'AI đã xử lý xong video tải lên' : 'Camera chưa có phiên AI'}
            </strong>
            <span>{completed ? 'Kết quả bên cạnh thuộc phiên video vừa hoàn tất.' : source.note}</span>
          </div>
        )}
      </div>

      <aside className="camera-information">
        {cameras.length > 1 && (
          <div className="dashboard-camera-selector">
            <button type="button" onClick={() => move(-1)} aria-label="Camera trước">‹</button>
            <EnvironmentSelect
              value={selected.id}
              onChange={setPickedId}
              options={cameras.map((c) => ({ value: c.id, label: `${c.code || c.id} · ${c.name}` }))}
            />
            <button type="button" onClick={() => move(1)} aria-label="Camera tiếp theo">›</button>
          </div>
        )}

        <div className={`camera-online ${running ? '' : 'offline'}`} data-testid="dashboard-camera-status">
          <span className="camera-online-dot" />
          <div>
            <strong>
              {running
                ? `AI đang xử lý · ${source.short}`
                : completed
                  ? 'Đã xử lý xong · Video từ máy'
                  : sourceMode === 'UNAVAILABLE'
                  ? 'AI không khả dụng'
                  : 'Camera OFFLINE · chưa có phiên'}
            </strong>
            <small>
              {selected.id} · {view.runtimeLabel}
              {status ? ` · ${status.modelVersion} / ${status.trackerType}${running ? ` · ${status.fps.toFixed(1)} FPS` : ''}` : ''}
            </small>
          </div>
        </div>

        {view.error && <p className="dashboard-ai-error" data-testid="dashboard-camera-error">{view.error}</p>}

        <div className="camera-stat-grid">
          <article>
            <span>Chim vào</span>
            <strong data-testid="dashboard-count-entry">{counts ? counts.entryCount : '--'}</strong>
            <small>{counts ? (completed ? 'Video đã phân tích' : sourceMode === 'DEMO_VIDEO' ? 'Video kiểm thử' : 'Phiên AI hiện tại') : 'Chưa có phiên'}</small>
          </article>
          <article>
            <span>Chim ra</span>
            <strong data-testid="dashboard-count-exit">{counts ? counts.exitCount : '--'}</strong>
            <small>{counts ? `Cập nhật ${formatRelativeTime(counts.recordedAt)}` : '--'}</small>
          </article>
        </div>

        <p className="dashboard-ai-meta">
          Phát hiện mới nhất: {running ? detections.length : '--'} · Khung đã xử lý: {status ? status.processedFrames : '--'}
        </p>

        <div className="dashboard-ai-events" data-testid="dashboard-ai-events" data-state={aiEvents.state}>
          <strong>Sự kiện AI gần đây</strong>
          {eventRows.length === 0 ? (
            <small>{EVENT_STATE_TEXT[aiEvents.state] || '--'}</small>
          ) : (
            <ul>
              {eventRows.map((r) => (
                <li key={r.id}>
                  {r.title} · {r.location} · {r.confidence != null ? `${r.confidence}%` : '--'} · {formatRelativeTime(r.detectedAt)}
                </li>
              ))}
            </ul>
          )}
        </div>

        {!running && sourceMode !== 'UNAVAILABLE' && (
          <button type="button" className="dashboard-ai-demo-button" onClick={ai.startDemo} data-testid="dashboard-start-demo">
            Chạy video kiểm thử tổng hợp
          </button>
        )}
        <button type="button" className="open-camera-button" onClick={openSwiftlets} data-testid="dashboard-open-swiftlets">
          {running ? 'Xem chi tiết tại Giám sát chim yến' : 'Bật webcam / tải video / xem chi tiết'}
          <span>→</span>
        </button>
      </aside>
    </div>
  )
}

export default DashboardAiCamera
