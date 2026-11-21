import { SEVERITY_LABELS, READ_STATE_LABELS as readStateLabels } from '../../../../features/notifications/notificationAdapter.js'
import { useAuth } from '../../../../context/AuthContext'

function formatAbsolute(iso) {
  if (!iso) return '--'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '--' : d.toLocaleString('vi-VN', { hour12: false })
}

/**
 * INT03-R1: detail of ONE persisted notification (the row the user clicked, looked up by id).
 * Only "Đánh dấu đã đọc" is offered in real mode because that is what the backend supports.
 */
function AlertDetailPanel({ alert, onClose, onAcknowledge, onResolve, canResolve = false, acknowledgeLabel = 'Đánh dấu đã đọc', mock = false }) {
  const { user } = useAuth()
  if (!alert) return null
  const unread = alert.status === 'UNREAD' || alert.status === 'OPEN'

  return (
    <div className="alert-detail-backdrop" onMouseDown={onClose}>
      <aside className="alert-detail-panel" onMouseDown={(event) => event.stopPropagation()} data-testid="alert-detail" data-alert-id={alert.id}>
        <header className="alert-detail-header">
          <div>
            <span className={`alert-severity-badge ${alert.severity.toLowerCase()}`}>
              {SEVERITY_LABELS[alert.severity] || alert.severity}
            </span>
            <h2>{alert.title}</h2>
            <p>{alert.typeLabel || alert.type}</p>
          </div>
          <button type="button" className="alert-detail-close" onClick={onClose} aria-label="Đóng chi tiết cảnh báo">×</button>
        </header>

        <div className="alert-detail-body">
          <section>
            <span className="alert-detail-label">Trạng thái thông báo</span>
            <strong>{readStateLabels[alert.status] || alert.status}</strong>
            {alert.readAt && <small>Đọc lúc {formatAbsolute(alert.readAt)}</small>}
          </section>
          <section>
            <span className="alert-detail-label">Nguồn</span>
            <strong>{alert.source}</strong>
            <small>{alert.device && alert.device !== '--' ? alert.device : 'Không có thông tin thiết bị'}</small>
          </section>
          <section>
            <span className="alert-detail-label">Nhà yến</span>
            <strong>{alert.farmName || '--'}</strong>
          </section>
          <section>
            <span className="alert-detail-label">Khu vực</span>
            <strong>{alert.zoneName}</strong>
          </section>
          <section>
            <span className="alert-detail-label">Thời điểm</span>
            <strong>{formatAbsolute(alert.timestamp)}</strong>
            <small>{alert.time}</small>
          </section>

          <div className="alert-detail-description">
            <span className="alert-detail-label">Nội dung</span>
            <p>{alert.description || '--'}</p>
          </div>

          {(alert.value || alert.threshold || (alert.confidence !== null && alert.confidence !== undefined)) && (
            <div className="alert-detail-metrics">
              {alert.value && (<article><span>Giá trị</span><strong>{alert.value}</strong></article>)}
              {alert.threshold && (<article><span>Ngưỡng</span><strong>{alert.threshold}</strong></article>)}
              {alert.confidence !== null && alert.confidence !== undefined && (<article><span>Độ tin cậy AI</span><strong>{alert.confidence}%</strong></article>)}
            </div>
          )}

          {!mock && (
            <p className="alert-detail-note" style={{ fontSize: '12px', color: '#64748b' }}>
              Hệ thống hiện ghi nhận trạng thái đã đọc/chưa đọc của thông báo. Xác nhận và đóng sự cố chưa được backend hỗ trợ.
              {user?.role === 'FARM_OWNER' && ' Nếu cần kỹ thuật viên kiểm tra, hãy tạo "Yêu cầu kiểm tra" tại trang Nhà yến.'}
              {user?.role === 'TECHNICIAN' && ' Yêu cầu kiểm tra do chủ trại gửi nằm ở tab "Yêu cầu kiểm tra".'}
            </p>
          )}
        </div>

        {(unread || (mock && canResolve && alert.status !== 'RESOLVED')) && (
          <footer className="alert-detail-actions">
            {unread && (
              <button type="button" className="alert-secondary-action" onClick={() => onAcknowledge(alert.id)}>
                {acknowledgeLabel}
              </button>
            )}
            {mock && canResolve && alert.status !== 'RESOLVED' && (
              <button type="button" className="alert-primary-action" onClick={() => onResolve(alert.id)}>Đánh dấu đã xử lý</button>
            )}
          </footer>
        )}
      </aside>
    </div>
  )
}

export default AlertDetailPanel
