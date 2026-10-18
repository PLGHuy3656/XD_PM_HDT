import { devices } from './dashboardMockData'

function StatusDot({ status }) {
  return <span className={`technician-status-dot ${status}`} />
}

function DeviceStatusPanel() {
  return (
    <section className="technician-card technician-device-panel">
      <div className="technician-card-heading">
        <div>
          <span>DEVICE MANAGEMENT</span>
          <h3>Tr?ng th?i thi?t b?</h3>
          <p>
            Theo d?i controller v? sensor ?ang k?t n?i trong nh? y?n
          </p>
        </div>

        <button type="button" className="technician-link-button">
          Xem t?t c?
          <span>?</span>
        </button>
      </div>

      <div className="technician-device-list">
        <div className="technician-device-list__header">
          <span>Node</span>
          <span>Khu v?c</span>
          <span>Sensor</span>
          <span>Tr?ng th?i</span>
          <span>C?p nh?t</span>
        </div>

        {devices.map((device) => (
          <article className="technician-device-row" key={device.id}>
            <div className="technician-device-row__node">
              <span
                className={`technician-device-icon technician-device-icon--${device.status}`}
              >
                ?
              </span>

              <strong>{device.id}</strong>
            </div>

            <span>{device.zone}</span>

            <strong className="technician-device-row__sensor">
              {device.sensors}
            </strong>

            <span
              className={`technician-device-state technician-device-state--${device.status}`}
            >
              <StatusDot
                status={
                  device.status === 'online'
                    ? 'healthy'
                    : device.status === 'warning'
                      ? 'warning'
                      : 'danger'
                }
              />

              {device.status === 'online'
                ? 'Online'
                : device.status === 'warning'
                  ? 'Warning'
                  : 'Offline'}
            </span>

            <span className="technician-device-row__time">
              {device.lastSeen}
            </span>
          </article>
        ))}
      </div>
    </section>
  )
}

export default DeviceStatusPanel
