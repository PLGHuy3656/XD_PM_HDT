import {
  severityLabel,
  technicalStatusLabel,
} from './alertsMockData'

export default function TechnicalAlertsTab({
  alerts,
  selectedId,
  onSelect,
}) {
  return (
    <div className="tech-alert-list">
      {alerts.map((alert) => (
        <button
          type="button"
          key={alert.id}
          className={`tech-alert-row ${
            selectedId === alert.id ? 'active' : ''
          }`}
          onClick={() => onSelect(alert)}
        >
          <div className={`tech-alert-indicator ${alert.severity}`} />

          <div className="tech-alert-row-main">
            <div className="tech-alert-row-heading">
              <strong>{alert.title}</strong>

              <span className={`tech-severity ${alert.severity}`}>
                {severityLabel(alert.severity)}
              </span>
            </div>

            <div className="tech-alert-row-meta">
              <span>{alert.farm}</span>
              <span>{alert.zone}</span>
              <span>{alert.device}</span>
            </div>
          </div>

          <div className="tech-alert-row-side">
            <span className={`tech-status ${alert.status}`}>
              {technicalStatusLabel(alert.status)}
            </span>
            <small>{alert.occurredAt}</small>
          </div>
        </button>
      ))}

      {alerts.length === 0 && (
        <div className="tech-alert-empty">
          Không có cảnh báo phù hợp với bộ lọc.
        </div>
      )}
    </div>
  )
}