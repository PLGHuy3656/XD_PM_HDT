import { useEffect, useRef } from 'react'
import { formatRelativeTime } from '../../../../features/telemetry/provenance.js'
import { AI_CLASS_LABEL, resolveAiCameraView } from '../../../../features/cameras/aiCameraState.js'

/**
 * INT02: AI camera panel driven by the real AI Service (through the Gateway).
 *
 * Source modes are always explicit: DEMO VIDEO (synthetic fixture replayed on the AI Service),
 * LOCAL CAMERA (this computer's webcam, frames sent while the session is on), LAN CAMERA
 * (not provisioned in INT02) and UNAVAILABLE. No video is shown unless it is the real local
 * webcam preview; demo detections are drawn on a schematic canvas, never on a fake video.
 */
const CLASS_LABEL = AI_CLASS_LABEL

function DetectionOverlay({ detection, width, height, className }) {
  const canvasRef = useRef(null)
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const w = detection?.frame?.width || width || 640
    const h = detection?.frame?.height || height || 480
    canvas.width = w
    canvas.height = h
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, w, h)
    ctx.lineWidth = Math.max(2, Math.round(w / 240))
    ctx.font = `${Math.max(12, Math.round(w / 40))}px sans-serif`
    for (const d of detection?.detections || []) {
      const b = d.bbox || {}
      const x1 = b.x1 ?? b.xMin ?? b.left ?? 0
      const y1 = b.y1 ?? b.yMin ?? b.top ?? 0
      const x2 = b.x2 ?? b.xMax ?? (b.left != null && b.width != null ? b.left + b.width : x1)
      const y2 = b.y2 ?? b.yMax ?? (b.top != null && b.height != null ? b.top + b.height : y1)
      const color = d.class === 'swiftlet' ? '#2f9e6b' : '#c0392b'
      ctx.strokeStyle = color
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)
      const label = `${CLASS_LABEL[d.class] || d.class} ${(d.confidence * 100).toFixed(0)}%${d.trackId != null ? ` #${d.trackId}` : ''}`
      ctx.fillStyle = color
      ctx.fillText(label, x1 + 4, Math.max(14, y1 - 6))
    }
  }, [detection, width, height])
  return <canvas ref={canvasRef} className={className} aria-label="Khung nhận diện AI" />
}

function LiveCameraCard({ camera, ai }) {
  const videoRef = useRef(null)
  const cameraId = camera?.id && camera.id !== 'CAM-NONE' ? camera.id : null

  if (!cameraId || !ai) {
    return (
      <section className="swiftlet-card swiftlet-camera-card" data-testid="ai-camera-card">
        <div className="swiftlet-card-heading swiftlet-camera-heading">
          <div>
            <h2>Camera AI</h2>
            <p>Chưa có camera AI được đăng ký cho nhà yến này.</p>
          </div>
        </div>
      </section>
    )
  }

  const status = ai.status
  const view = resolveAiCameraView(ai, cameraId)
  const { running, sourceMode, source, counts, detections } = view
  const webcamOn = ai.webcam.state === 'STREAMING' || ai.webcam.state === 'REQUESTING'
  const detection = running ? ai.detection : null

  return (
    <section className="swiftlet-card swiftlet-camera-card ai-camera-card" data-testid="ai-camera-card" data-source-mode={sourceMode} data-session-state={ai.sessionState}>
      <div className="swiftlet-card-heading swiftlet-camera-heading">
        <div>
          <div className="swiftlet-live-title">
            <i className={running ? '' : 'offline'} />
            <h2>Camera AI · {camera.code || cameraId}</h2>
          </div>
          <p>{camera.name}</p>
        </div>
        <span className={`ai-source-chip ai-source-chip--${source.className}`} data-testid="ai-source-mode">{source.label}</span>
      </div>

      <div className="ai-camera-actions">
        <button type="button" onClick={ai.startDemo} disabled={ai.sessionState === 'UNAVAILABLE' || webcamOn} data-testid="ai-start-demo">
          Chạy video demo
        </button>
        <button type="button" onClick={() => ai.startWebcam(videoRef.current)} disabled={ai.sessionState === 'UNAVAILABLE' || webcamOn} data-testid="ai-start-webcam">
          Bật webcam máy này
        </button>
        <button type="button" onClick={ai.stopSession} disabled={!running && !webcamOn} data-testid="ai-stop">
          Dừng
        </button>
      </div>

      <div className="ai-camera-stage">
        <video
          ref={videoRef}
          className={`ai-camera-video ${ai.webcam.state === 'STREAMING' || ai.webcam.state === 'REQUESTING' ? '' : 'is-hidden'}`}
          muted
          playsInline
          data-testid="ai-webcam-preview"
        />
        {sourceMode === 'LOCAL_CAMERA' && webcamOn && (
          <DetectionOverlay detection={detection} width={status?.width} height={status?.height} className="ai-camera-overlay" />
        )}
        {sourceMode === 'DEMO_VIDEO' && (
          <div className="ai-camera-schematic">
            <DetectionOverlay detection={detection} width={status?.width} height={status?.height} className="ai-camera-schematic-canvas" />
            <small>Sơ đồ vị trí phát hiện của AI trên video demo (hình ảnh video không truyền về trình duyệt).</small>
          </div>
        )}
        {(sourceMode === 'UNAVAILABLE' || sourceMode === 'OFFLINE') && !webcamOn && (
          <div className="ai-camera-empty" data-testid="ai-camera-unavailable">
            <strong>{ai.sessionState === 'UNAVAILABLE' ? 'Dịch vụ AI không khả dụng' : 'Chưa có nguồn hình ảnh'}</strong>{' '}
            <span>
              {ai.sessionState === 'UNAVAILABLE'
                ? 'Không kết nối được AI Service. Không có số liệu nào được hiển thị thay thế.'
                : 'Camera chưa có phiên AI. Chọn "Chạy video demo" hoặc "Bật webcam máy này".'}
            </span>
          </div>
        )}
      </div>

      <p className="ai-camera-note">{source.note}</p>
      {(ai.webcam.error || ai.actionError || ai.error || status?.errorMessage) && (
        <p className="ai-camera-error" data-testid="ai-camera-error">
          {ai.webcam.error || ai.actionError || ai.error || `${status.errorCode}: ${status.errorMessage}`}
        </p>
      )}

      <dl className="ai-camera-runtime" data-testid="ai-runtime">
        <div><dt>Trạng thái AI</dt><dd>{view.runtimeLabel}</dd></div>
        <div><dt>Model / Tracker</dt><dd>{status ? `${status.modelVersion} · ${status.trackerType}` : '--'}</dd></div>
        <div><dt>FPS xử lý</dt><dd>{running ? status.fps.toFixed(1) : '--'}</dd></div>
        <div><dt>Khung đã xử lý</dt><dd>{running ? status.processedFrames : '--'}</dd></div>
        <div><dt>Khung hình gần nhất</dt><dd>{status?.lastFrameAt ? formatRelativeTime(status.lastFrameAt) : '--'}</dd></div>
        <div><dt>Webcam gửi / lỗi</dt><dd>{sourceMode === 'LOCAL_CAMERA' || webcamOn ? `${ai.webcam.sent} / ${ai.webcam.rejected}` : '--'}</dd></div>
      </dl>

      <div className="ai-camera-results">
        <div data-testid="ai-detections">
          <strong>Phát hiện mới nhất</strong>
          {detections.length === 0 ? (
            <span className="ai-muted">{running ? 'Không có đối tượng trong khung gần nhất' : '--'}</span>
          ) : (
            <ul>
              {detections.slice(0, 6).map((d, i) => (
                <li key={`${d.trackId ?? 'x'}-${i}`}>
                  {CLASS_LABEL[d.class] || d.class} · {(d.confidence * 100).toFixed(0)}%{d.trackId != null ? ` · track #${d.trackId}` : ''}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div data-testid="ai-counts">
          <strong>Đếm qua vạch (phiên hiện tại)</strong>
          {counts ? (
            <span>
              Vào <b data-testid="ai-count-entry">{counts.entryCount}</b> · Ra <b data-testid="ai-count-exit">{counts.exitCount}</b> · Ròng {counts.netChange}
              <small> · cập nhật {formatRelativeTime(counts.recordedAt)}</small>
            </span>
          ) : (
            <span className="ai-muted">Chưa có số liệu đếm</span>
          )}
        </div>
      </div>
    </section>
  )
}

export default LiveCameraCard
