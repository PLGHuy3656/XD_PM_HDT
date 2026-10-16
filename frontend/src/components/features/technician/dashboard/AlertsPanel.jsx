import { alerts } from './dashboardMockData'

function AlertsPanel() {
  return (
    <div className="technician-alert-list">
      {alerts.map((alert) => (
        <article
          className="technician-alert-item"
          key={alert.id}
        >
          <span
            className={`technician-alert-item__icon technician-alert-item__icon--${alert.level}`}
          >
            {alert.level === 'critical'
              ? '!'
              : alert.level === 'warning'
                ? '?'
                : 'i'}
          </span>

          <div>
            <strong>{alert.title}</strong>
            <p>{alert.description}</p>
          </div>

          <time>{alert.time}</time>
        </article>
      ))}
    </div>
  )
}

export default AlertsPanel
