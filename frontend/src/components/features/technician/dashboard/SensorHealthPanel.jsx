import { sensorHealth } from './dashboardMockData'

function StatusDot({ status }) {
  return <span className={`technician-status-dot ${status}`} />
}

function SensorHealthPanel() {
  return (
    <section className="technician-card technician-health-panel">
      <div className="technician-card-heading">
        <div>
          <span>DIAGNOSTICS</span>
          <h3>Sensor Health</h3>
          <p>T?nh tr?ng c?m bi?n ?ang ???c gi?m s?t</p>
        </div>
      </div>

      <div className="technician-health-score">
        <div className="technician-health-ring">
          <div>
            <strong>92%</strong>
            <span>Healthy</span>
          </div>
        </div>

        <div className="technician-health-summary">
          {sensorHealth.map((item) => (
            <div
              className="technician-health-summary__item"
              key={item.label}
            >
              <span>
                <StatusDot status={item.status} />
                {item.label}
              </span>

              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
      </div>

      <div className="technician-health-footer">
        <span>26 sensor ???c ??ng k?</span>

        <button type="button">
          Ch?n ?o?n
          <span>?</span>
        </button>
      </div>
    </section>
  )
}

export default SensorHealthPanel
