const statusLabels = {
  OPEN: 'Đang mở',
  ACKNOWLEDGED: 'Đã xác nhận',
  RESOLVED: 'Đã xử lý',
}

function AlertDetailPanel({
  alert,
  onClose,
  onAcknowledge,
  onResolve,
}) {
  if (!alert) {
    return null
  }

  return (
    <div
      className="alert-detail-backdrop"
      onMouseDown={onClose}
    >
      <aside
        className="alert-detail-panel"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="alert-detail-header">
          <div>
            <span
              className={`alert-severity-badge ${alert.severity.toLowerCase()}`}
            >
              {alert.severity}
            </span>

            <h2>{alert.title}</h2>

            <p>{alert.id}</p>
          </div>

          <button
            type="button"
            className="alert-detail-close"
            onClick={onClose}
            aria-label="Đóng chi tiết cảnh báo"
          >
            ×
          </button>
        </header>

        <div className="alert-detail-body">
          <section>
            <span className="alert-detail-label">
              Trạng thái
            </span>

            <strong>
              {statusLabels[alert.status]}
            </strong>
          </section>

          <section>
            <span className="alert-detail-label">
              Nguồn phát hiện
            </span>

            <strong>{alert.source}</strong>
            <small>{alert.device}</small>
          </section>

          <section>
            <span className="alert-detail-label">
              Khu vực
            </span>

            <strong>{alert.zoneName}</strong>
          </section>

          <section>
            <span className="alert-detail-label">
              Thời gian
            </span>

            <strong>{alert.time}</strong>
          </section>

          <div className="alert-detail-description">
            <span className="alert-detail-label">
              Mô tả
            </span>

            <p>{alert.description}</p>
          </div>

          {(alert.value ||
            alert.threshold ||
            alert.confidence !== null) && (
            <div className="alert-detail-metrics">
              {alert.value && (
                <article>
                  <span>Giá trị</span>
                  <strong>{alert.value}</strong>
                </article>
              )}

              {alert.threshold && (
                <article>
                  <span>Ngưỡng</span>
                  <strong>{alert.threshold}</strong>
                </article>
              )}

              {alert.confidence !== null && (
                <article>
                  <span>Độ tin cậy AI</span>
                  <strong>{alert.confidence}%</strong>
                </article>
              )}
            </div>
          )}
        </div>

        {alert.status !== 'RESOLVED' && (
          <footer className="alert-detail-actions">
            {alert.status === 'OPEN' && (
              <button
                type="button"
                className="alert-secondary-action"
                onClick={() => onAcknowledge(alert.id)}
              >
                Xác nhận cảnh báo
              </button>
            )}

            <button
              type="button"
              className="alert-primary-action"
              onClick={() => onResolve(alert.id)}
            >
              Đánh dấu đã xử lý
            </button>
          </footer>
        )}
      </aside>
    </div>
  )
}

export default AlertDetailPanel