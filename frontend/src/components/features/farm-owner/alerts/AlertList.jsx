const statusLabels = {
  OPEN: 'Đang mở',
  ACKNOWLEDGED: 'Đã xác nhận',
  RESOLVED: 'Đã xử lý',
}

function EmptyAlerts() {
  return (
    <div className="alerts-empty">
      <div className="alerts-empty-icon">!</div>

      <strong>Không có cảnh báo nào</strong>

      <p>
        Không có cảnh báo phù hợp với bộ lọc hiện tại.
        Hãy thử chọn trạng thái, mức độ hoặc khu vực khác.
      </p>
    </div>
  )
}

function AlertList({ alerts, onViewDetail }) {
  if (alerts.length === 0) {
    return <EmptyAlerts />
  }

  return (
    <div className="alerts-list">
      {alerts.map((alert) => (
        <article
          key={alert.id}
          className={`alert-row severity-${alert.severity.toLowerCase()}`}
        >
          <div className="alert-row-severity">
            <span
              className={`alert-severity-badge ${alert.severity.toLowerCase()}`}
            >
              {alert.severity}
            </span>

            <span className="alert-status-label">
              {statusLabels[alert.status]}
            </span>
          </div>

          <div className="alert-row-content">
            <div className="alert-row-heading">
              <div>
                <h3>{alert.title}</h3>

                <p>
                  {alert.source} · {alert.device} ·{' '}
                  {alert.zoneName}
                </p>
              </div>

              <time>{alert.time}</time>
            </div>

            <div className="alert-row-meta">
              {alert.value && (
                <span>
                  Giá trị <strong>{alert.value}</strong>
                </span>
              )}

              {alert.threshold && (
                <span>{alert.threshold}</span>
              )}

              {alert.confidence !== null && (
                <span>
                  Độ tin cậy{' '}
                  <strong>{alert.confidence}%</strong>
                </span>
              )}
            </div>
          </div>

          <button
            type="button"
            className="alert-detail-button"
            onClick={() => onViewDetail(alert)}
          >
            Xem chi tiết
            <span>→</span>
          </button>
        </article>
      ))}
    </div>
  )
}

export default AlertList