function severityLabel(severity) {
  return {
    CRITICAL: 'Nghiêm trọng',
    WARNING: 'Cảnh báo',
    INFO: 'Thông tin',
  }[severity]
}

function statusLabel(status) {
  return {
    OPEN: 'Chưa xử lý',
    INVESTIGATING: 'Đang kiểm tra',
    RESOLVED: 'Đã xử lý',
  }[status]
}

export default function AlertDetailPanel({ alert, onClose }) {
  if (!alert) return null

  return (
    <aside className="tech-alert-detail">
      <div className="tech-alert-detail-header">
        <div>
          <span className="tech-alert-detail-eyebrow">CẢNH BÁO KỸ THUẬT</span>
          <h2>{alert.title}</h2>
        </div>

        <button
          type="button"
          className="tech-alert-close"
          onClick={onClose}
          aria-label="Đóng"
        >
          ×
        </button>
      </div>

      <div className="tech-alert-detail-badges">
        <span className={`tech-severity ${alert.severity}`}>
          {severityLabel(alert.severity)}
        </span>
        <span className={`tech-status ${alert.status}`}>
          {statusLabel(alert.status)}
        </span>
      </div>

      <div className="tech-alert-detail-grid">
        <div>
          <span>Nhà yến</span>
          <strong>{alert.farm}</strong>
        </div>
        <div>
          <span>Khu vực</span>
          <strong>{alert.zone}</strong>
        </div>
        <div>
          <span>Thiết bị</span>
          <strong>{alert.device}</strong>
        </div>
        <div>
          <span>Thời điểm</span>
          <strong>{alert.occurredAt}</strong>
        </div>
      </div>

      <section className="tech-alert-detail-section">
        <span>Mô tả sự cố</span>
        <p>{alert.description}</p>
      </section>

      <section className="tech-alert-detail-section">
        <span>Chẩn đoán hệ thống</span>
        <p>{alert.diagnostic}</p>
      </section>

      <section className="tech-alert-detail-section recommendation">
        <span>Đề xuất kiểm tra</span>
        <p>{alert.recommendation}</p>
      </section>

      <div className="tech-alert-permission-note">
        Thao tác điều khiển thiết bị chỉ khả dụng khi Backend xác nhận quyền
        của Technician.
      </div>
    </aside>
  )
}