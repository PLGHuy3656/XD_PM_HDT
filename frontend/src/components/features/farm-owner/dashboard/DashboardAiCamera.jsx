import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import EnvironmentSelect from '../../../ui/Select'
import { useCameraAiRuntime } from '../../../../features/cameras/hooks/useCameraAiRuntime.js'
import { AI_CLASS_LABEL, resolveAiCameraView } from '../../../../features/cameras/aiCameraState.js'
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

function DashboardAiCamera({ cameras = [] }) {
  const navigate = useNavigate()
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

  const { running, sourceMode, source, counts, detections, status } = view
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
              <span>
                {sourceMode === 'DEMO_VIDEO'
                  ? 'Sơ đồ vị trí phát hiện trên video demo (không truyền hình ảnh về trình duyệt)'
                  : 'Vị trí phát hiện mới nhất từ AI'}
              </span>
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
            <strong>{sourceMode === 'UNAVAILABLE' ? 'AI Service không khả dụng' : 'Camera chưa có phiên AI'}</strong>
            <span>{source.note}</span>
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
                : sourceMode === 'UNAVAILABLE'
                  ? 'AI không khả dụng'
                  : 'Camera OFFLINE · chưa có phiên'}
            </strong>
            <small>
              {selected.id} · {view.runtimeLabel}
              {running && status ? ` · ${status.modelVersion} / ${status.trackerType} · ${status.fps.toFixed(1)} FPS` : ''}
            </small>
          </div>
        </div>

        {view.error && <p className="dashboard-ai-error" data-testid="dashboard-camera-error">{view.error}</p>}

        <div className="camera-stat-grid">
          <article>
            <span>Chim vào</span>
            <strong data-testid="dashboard-count-entry">{counts ? counts.entryCount : '--'}</strong>
            <small>{counts ? (sourceMode === 'DEMO_VIDEO' ? 'Phiên video demo' : 'Phiên AI hiện tại') : 'Chưa có phiên'}</small>
          </article>
          <article>
            <span>Chim ra</span>
            <strong data-testid="dashboard-count-exit">{counts ? counts.exitCount : '--'}</strong>
            <small>{counts ? `Cập nhật ${formatRelativeTime(counts.recordedAt)}` : '--'}</small>
          </article>
        </div>

        <p className="dashboard-ai-meta">
          Phát hiện mới nhất: {running ? detections.length : '--'} · Khung đã xử lý: {running && status ? status.processedFrames : '--'}
        </p>

        {!running && sourceMode !== 'UNAVAILABLE' && (
          <button type="button" className="dashboard-ai-demo-button" onClick={ai.startDemo} data-testid="dashboard-start-demo">
            Chạy video demo
          </button>
        )}
        <button type="button" className="open-camera-button" onClick={openSwiftlets} data-testid="dashboard-open-swiftlets">
          {running ? 'Xem chi tiết tại Giám sát chim yến' : 'Bật webcam / xem chi tiết'}
          <span>→</span>
        </button>
      </aside>
    </div>
  )
}

export default DashboardAiCamera
