import { SEVERITY_LABELS, READ_STATE_LABELS as readStateLabels } from '../../../../features/notifications/notificationAdapter.js'

/**
 * INT03-R1: operational alerts list. "Trạng thái" here is the notification READ state only —
 * alert acknowledgement/resolution are not supported by the current backend and are not shown.
 */

function AlertList({ alerts, selectedAlertId, onViewDetail }) {
  if (alerts.length === 0) return null

  return (
    <div className="alerts-list" data-testid="alerts-list">
      {alerts.map((alert) => (
        <article
          key={alert.id}
          data-alert-id={alert.id}
          className={`alert-row severity-${alert.severity.toLowerCase()} ${selectedAlertId === alert.id ? 'alert-row--selected' : ''} ${alert.readState === 'UNREAD' ? 'alert-row--unread' : ''}`}
        >
          <div className="alert-row-severity">
            <span className={`alert-severity-badge ${alert.severity.toLowerCase()}`}>
              {SEVERITY_LABELS[alert.severity] || alert.severity}
            </span>
            <span className="alert-status-label">{readStateLabels[alert.status] || alert.status}</span>
          </div>

          <div className="alert-row-content">
            <div className="alert-row-heading">
              <div>
                <h3>{alert.title}</h3>
                <p>
                  {alert.source}
                  {alert.typeLabel ? ` · ${alert.typeLabel}` : ''}
                  {alert.device && alert.device !== '--' ? ` · ${alert.device}` : ''}
                  {` · ${alert.zoneName}`}
                </p>
              </div>
              <time dateTime={alert.timestamp || undefined} title={alert.timestamp ? new Date(alert.timestamp).toLocaleString('vi-VN', { hour12: false }) : ''}>
                {alert.time}
              </time>
            </div>

            <div className="alert-row-meta">
              {alert.description && <span>{alert.description}</span>}
              {alert.confidence !== null && alert.confidence !== undefined && (
                <span>Độ tin cậy <strong>{alert.confidence}%</strong></span>
              )}
            </div>
          </div>

          <button type="button" className="alert-detail-button" onClick={() => onViewDetail(alert)} data-testid={`alert-detail-${alert.id}`}>
            Xem chi tiết
            <span>→</span>
          </button>
        </article>
      ))}
    </div>
  )
}

export default AlertList
